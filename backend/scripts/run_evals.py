"""Evaluate the pipeline on the small labelled set. Offline by default when no key is set.

    python -m scripts.run_evals                      # classification + retrieval
    python -m scripts.run_evals --answers            # + generated answers (LLM calls)

Inputs
  sample_docs/ + evals/corpus/   9 documents
  evals/labels.jsonl             gold Level 1 department, gate status, Level 2 entities
  evals/dataset.jsonl            questions: expected document + answer keywords,
                                 or expected_doc=null for questions that must be refused

Metrics
  L1 accuracy        primary department == gold department
  gate accuracy      ANALYZED / NEEDS_REVIEW == gold (where labelled)
  L2 precision       extracted values that match a gold value / all extracted
  L2 recall          gold values that were extracted / all gold values
  hit@1, hit@k, MRR  is the right document in the retrieved chunks, and how high
  answer accuracy    answer contains every expected keyword
  refusal            unanswerable questions answered "Not found in the documents."
  no PII leak        answer never contains the raw PII string
  faithfulness       average citation-check score

Writes evals/report_<provider>.md and evals/latest_<provider>.json (shown in the UI).
"""
import argparse
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from app.db import connect, init_db
from app.api.auth import User
from app.llm.grounding import NOT_FOUND
from app.llm.providers import get_provider
from app.orchestrator.ask_flow import answer_question, search
from app.orchestrator.ingest_flow import process_upload
from app.orchestrator.tracing import Tracer

ROOT = Path(__file__).resolve().parents[1]
MODES = {"keyword": ("keyword", False), "vector": ("vector", False),
         "hybrid": ("hybrid", False), "hybrid+hyde": ("hybrid", True)}
ENTITY_TYPES = ["dates", "amounts", "reference_ids", "vendors"]
EVAL_USER = User("eval", "admin", None)


def read_jsonl(name: str) -> list[dict]:
    return [json.loads(line) for line in (ROOT / "evals" / name).read_text().splitlines() if line.strip()]


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower().replace("m/s", ""))


def matches(a: str, b: str) -> bool:
    a, b = norm(a), norm(b)
    return bool(a and b) and (a == b or a in b or b in a)


def build_index(llm, workdir: Path, strategy: str | None = None):
    db = str(workdir / "eval.db")
    init_db(db)
    conn = connect(db)
    doc_ids = {}
    for label in read_jsonl("labels.jsonl"):
        path = ROOT / label["file"]
        result = process_upload(conn, llm, EVAL_USER, path.name, path.read_bytes(),
                                strategy=strategy, upload_dir=str(workdir / "uploads"))
        doc_ids[label["file"]] = result.doc_id
    conn.commit()
    return conn, doc_ids


def classification_metrics(conn, doc_ids: dict) -> tuple[dict, list]:
    labels = read_jsonl("labels.jsonl")
    l1_ok = gate_ok = gate_n = 0
    counts = {t: {"tp_pred": 0, "pred": 0, "tp_gold": 0, "gold": 0} for t in ENTITY_TYPES}
    rows = []
    for label in labels:
        doc = conn.execute("SELECT status, l1_json, l2_json FROM documents WHERE doc_id = ?",
                           (doc_ids[label["file"]],)).fetchone()
        l1 = json.loads(doc["l1_json"] or "null")
        l2 = json.loads(doc["l2_json"] or "null") or {}
        predicted_dept = l1["departments"][0]["name"] if l1 else None
        l1_ok += predicted_dept == label["department"]
        if "expected_status" in label:
            gate_n += 1
            gate_ok += doc["status"] == label["expected_status"]
        for t in ENTITY_TYPES:
            predicted = [e["value"] for e in l2.get(t, [])]
            gold = label[t]
            c = counts[t]
            c["pred"] += len(predicted)
            c["gold"] += len(gold)
            c["tp_pred"] += sum(any(matches(p, g) for g in gold) for p in predicted)
            c["tp_gold"] += sum(any(matches(p, g) for p in predicted) for g in gold)
        rows.append({"document": Path(label["file"]).name, "gold": label["department"],
                     "predicted": predicted_dept, "status": doc["status"]})
    entity = {t: {"precision": c["tp_pred"] / c["pred"] if c["pred"] else 1.0,
                  "recall": c["tp_gold"] / c["gold"] if c["gold"] else 1.0,
                  "extracted": c["pred"], "gold": c["gold"]} for t, c in counts.items()}
    all_pred = sum(c["pred"] for c in counts.values())
    all_gold = sum(c["gold"] for c in counts.values())
    summary = {
        "l1_accuracy": l1_ok / len(labels),
        "gate_accuracy": gate_ok / gate_n if gate_n else None,
        "l2_precision": sum(c["tp_pred"] for c in counts.values()) / all_pred if all_pred else 1.0,
        "l2_recall": sum(c["tp_gold"] for c in counts.values()) / all_gold if all_gold else 1.0,
        "entity": entity,
    }
    return summary, rows


def retrieval_metrics(conn, llm, questions, mode, hyde, k):
    answerable = [q for q in questions if q["expected_doc"]]
    hit1 = hitk = rr = 0.0
    for q in answerable:
        files = [c["file_name"] for c in search(conn, llm, q["question"], None, k, mode, hyde, Tracer("adhoc"))]
        if q["expected_doc"] in files:
            rank = files.index(q["expected_doc"]) + 1
            hit1 += rank == 1
            hitk += 1
            rr += 1 / rank
    n = len(answerable)
    return {"hit@1": hit1 / n, f"hit@{k}": hitk / n, "MRR": rr / n}


def answer_metrics(conn, llm, questions, mode, hyde, k):
    answerable = [q for q in questions if q["expected_doc"]]
    refusals = [q for q in questions if not q["expected_doc"]]
    correct = refused = faith = leaks = 0.0
    started = time.time()
    for q in questions:
        res = answer_question(conn, llm, q["question"], top_k=k, use_hyde=hyde, mode=mode,
                              tracer=Tracer("adhoc"))
        if q["expected_doc"]:
            correct += all(kw.lower() in res["answer"].lower() for kw in q["answer_keywords"])
            faith += res["faithfulness"]
        else:
            refused += res["answer"] == NOT_FOUND
        leaks += any(s in res["answer"] for s in q.get("must_not_contain", []))
    return {"answer_accuracy": correct / len(answerable), "refusal": refused / len(refusals),
            "pii_leaks": int(leaks), "faithfulness": faith / len(answerable),
            "latency_s": (time.time() - started) / len(questions)}


def table(title, rows):
    cols = list(rows[0].keys())
    return {"title": title, "columns": cols,
            "rows": [[round(v, 2) if isinstance(v, float) else v for v in r.values()] for r in rows]}


def to_markdown(t):
    lines = [f"### {t['title']}", "", "| " + " | ".join(t["columns"]) + " |", "|" + "---|" * len(t["columns"])]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in t["rows"]]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", action="store_true", help="also generate answers (LLM calls)")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    llm = get_provider()
    questions = read_jsonl("dataset.jsonl")
    with tempfile.TemporaryDirectory() as tmp:
        conn, doc_ids = build_index(llm, Path(tmp))
        cls, cls_rows = classification_metrics(conn, doc_ids)
        retrieval_rows, answer_rows = [], []
        for name, (mode, hyde) in MODES.items():
            retrieval_rows.append({"retrieval": name, **retrieval_metrics(conn, llm, questions, mode, hyde, args.k)})
            if args.answers and name in ("hybrid", "hybrid+hyde"):
                answer_rows.append({"retrieval": name, **answer_metrics(conn, llm, questions, mode, hyde, args.k)})
        conn.close()

    tables = [
        table("Level 1 and gate", [{"L1 accuracy": cls["l1_accuracy"], "gate accuracy": cls["gate_accuracy"],
                                    "L2 precision": cls["l2_precision"], "L2 recall": cls["l2_recall"]}]),
        table("Level 2 by entity type", [{"entity": t, **v} for t, v in cls["entity"].items()]),
        table("Level 1 per document", cls_rows),
        table("Retrieval", retrieval_rows),
    ]
    if answer_rows:
        tables.append(table("Answers", answer_rows))
    report = {"provider": llm.name, "model": llm.model,
              "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "documents": len(doc_ids), "questions": len(questions),
              "refusal_questions": sum(1 for q in questions if not q["expected_doc"]),
              "tables": tables}
    (ROOT / "evals" / f"latest_{llm.name}.json").write_text(json.dumps(report, indent=2))
    md = [f"# MetroMind eval report ({llm.name}: {llm.model})", "",
          f"Generated {report['generated_at']} - {len(doc_ids)} documents - {len(questions)} questions "
          f"({report['refusal_questions']} must be refused) - k = {args.k}", ""]
    md += [to_markdown(t) + "\n" for t in tables]
    (ROOT / "evals" / f"report_{llm.name}.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
