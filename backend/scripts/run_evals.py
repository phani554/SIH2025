"""Evaluate retrieval and answers on evals/dataset.jsonl.

    python -m scripts.run_evals                      # all chunkers x all retrieval modes
    python -m scripts.run_evals --answers            # also generate answers (uses LLM calls)
    python -m scripts.run_evals --strategies recursive --modes hybrid hybrid+hyde --answers

Each chunking strategy gets its own temporary database with the sample docs.

Retrieval metrics (answerable questions only)
  hit@1, hit@k   is the right document in the top 1 / top k chunks?
  MRR            mean of 1/rank of the first chunk from the right document
Answer metrics (--answers)
  accuracy       answer contains every expected keyword
  refusal        unanswerable questions correctly get "Not found in the documents."
  faithfulness   average share of answer sentences backed by their cited chunk
  latency        average seconds per question (retrieval + generation)
"""
import argparse
import json
import tempfile
import time
from pathlib import Path

from app.db import connect, init_db
from app.services.chunking import STRATEGIES
from app.services.ingestion import ingest_file
from app.services.llm import get_provider
from app.services.rag import NOT_FOUND, answer_question
from app.services.retrieval import search

ROOT = Path(__file__).resolve().parents[1]
MODES = {"keyword": ("keyword", False), "vector": ("vector", False),
         "hybrid": ("hybrid", False), "hybrid+hyde": ("hybrid", True)}


def load_dataset() -> list[dict]:
    lines = (ROOT / "evals" / "dataset.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def build_index(llm, strategy: str, workdir: Path):
    db_path = str(workdir / f"eval_{strategy}.db")
    init_db(db_path)
    conn = connect(db_path)
    for path in sorted((ROOT / "sample_docs").iterdir()):
        ingest_file(conn, llm, path.name, path.read_bytes(), strategy=strategy,
                    upload_dir=str(workdir / "uploads"))
    conn.commit()
    return conn


def retrieval_metrics(conn, llm, dataset, mode: str, use_hyde: bool, k: int) -> dict:
    answerable = [q for q in dataset if q["expected_doc"]]
    hit1 = hitk = rr = 0.0
    for q in answerable:
        files = [c["file_name"] for c in search(conn, llm, q["question"], top_k=k,
                                                mode=mode, use_hyde=use_hyde)]
        if q["expected_doc"] in files:
            rank = files.index(q["expected_doc"]) + 1
            hit1 += rank == 1
            hitk += 1
            rr += 1 / rank
    n = len(answerable)
    return {"hit@1": hit1 / n, f"hit@{k}": hitk / n, "MRR": rr / n}


def answer_metrics(conn, llm, dataset, mode: str, use_hyde: bool, k: int) -> tuple[dict, list]:
    correct = refused = faith = 0.0
    answerable = [q for q in dataset if q["expected_doc"]]
    unanswerable = [q for q in dataset if not q["expected_doc"]]
    rows, started = [], time.time()
    for q in dataset:
        res = answer_question(conn, llm, q["question"], top_k=k, use_hyde=use_hyde,
                              mode=mode, actor="eval")
        if q["expected_doc"]:
            ok = all(kw.lower() in res.answer.lower() for kw in q["answer_keywords"])
            correct += ok
            faith += res.faithfulness
        else:
            ok = res.answer == NOT_FOUND
            refused += ok
        rows.append({"id": q["id"], "ok": ok, "faithfulness": res.faithfulness,
                     "answer": res.answer[:160]})
    return {
        "accuracy": correct / len(answerable),
        "refusal": refused / max(len(unanswerable), 1),
        "faithfulness": faith / len(answerable),
        "latency_s": (time.time() - started) / len(dataset),
    }, rows


def to_markdown(title: str, results: list[dict]) -> str:
    cols = list(results[0].keys())
    lines = [f"### {title}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in results:
        lines.append("| " + " | ".join(f"{v:.2f}" if isinstance(v, float) else str(v)
                                        for v in r.values()) + " |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategies", nargs="+", default=list(STRATEGIES), choices=list(STRATEGIES))
    parser.add_argument("--modes", nargs="+", default=list(MODES), choices=list(MODES))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--answers", action="store_true", help="also evaluate generated answers")
    args = parser.parse_args()

    llm = get_provider()
    dataset = load_dataset()
    retrieval_rows, answer_rows, details = [], [], {}

    with tempfile.TemporaryDirectory() as tmp:
        for strategy in args.strategies:
            conn = build_index(llm, strategy, Path(tmp))
            chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            for mode_name in args.modes:
                mode, hyde = MODES[mode_name]
                row = {"chunking": strategy, "chunks": chunks, "retrieval": mode_name}
                row.update(retrieval_metrics(conn, llm, dataset, mode, hyde, args.k))
                retrieval_rows.append(row)
                print(row)
                if args.answers:
                    metrics, rows = answer_metrics(conn, llm, dataset, mode, hyde, args.k)
                    answer_rows.append({"chunking": strategy, "retrieval": mode_name, **metrics})
                    details[f"{strategy}/{mode_name}"] = rows
                    print("  answers:", metrics)
            conn.close()

    report = [f"# MetroMind eval report", "",
              f"Provider: **{llm.name}** · questions: {len(dataset)} "
              f"({sum(1 for q in dataset if q['expected_doc'])} answerable) · k = {args.k}", "",
              to_markdown("Retrieval", retrieval_rows)]
    if answer_rows:
        report += ["", to_markdown("Answers", answer_rows)]
    out = ROOT / "evals" / f"report_{llm.name}.md"
    out.write_text("\n".join(report) + "\n")
    (ROOT / "evals" / f"answers_{llm.name}.json").write_text(json.dumps(details, indent=2))
    print(f"\nReport written to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
