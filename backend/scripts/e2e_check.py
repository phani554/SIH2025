"""End-to-end check against a RUNNING backend (and optionally the Vite dev server).

    python -m scripts.e2e_check --admin-key mm_... --viewer-key mm_...

Uploads the three demo documents, re-uploads one, sends bad files, asks questions,
checks the traces and role limits, and prints PASS/FAIL per check.
"""
import argparse
import json
from pathlib import Path

import requests

SAMPLES = Path(__file__).resolve().parents[1] / "sample_docs"
INVOICE = "invoice_INV-2025-0917_alstom.txt"
SAFETY = "safety_circular_SC-14_platform_screen_doors.txt"
UNCLEAN = "unclean_vendor_letter_injection_pii.txt"
WORK_ORDER = "work_order_WO-RS-2025-0412_bogie_overhaul.txt"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--frontend", default="http://localhost:5173")
    p.add_argument("--admin-key", required=True)
    p.add_argument("--viewer-key", required=True, help="a Finance viewer key")
    args = p.parse_args()
    B, A, F = args.api, {"X-API-Key": args.admin_key}, {"X-API-Key": args.viewer_key}
    results = []

    def check(name, ok, info=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {info}")

    def up(name, data, headers=A):
        return requests.post(f"{B}/documents", headers=headers, files={"file": (name, data)})

    def run(run_id, headers=A):
        return requests.get(f"{B}/runs/{run_id}", headers=headers)

    h = requests.get(f"{B}/health").json()
    check("health", h["status"] == "ok", f"{h['llm_provider']} / {h['model']}")
    check("no key -> 401", requests.get(f"{B}/documents").status_code == 401)

    res = {f: up(f, (SAMPLES / f).read_bytes()).json() for f in (INVOICE, SAFETY, UNCLEAN)}
    check("clean invoice -> ANALYZED", res[INVOICE]["status"] == "ANALYZED")
    check("clean safety circular -> ANALYZED", res[SAFETY]["status"] == "ANALYZED")
    check("unclean letter -> NEEDS_REVIEW", res[UNCLEAN]["status"] == "NEEDS_REVIEW")

    inv = run(res[INVOICE]["run_id"]).json()
    check("invoice trace: preliminary analysis + plan",
          inv["plan"]["level1"]["departments"][0]["name"] == "Finance" and inv["plan"]["plan"]["max_steps"] == 21,
          f"{len(inv['steps'])} steps, {inv['plan']['used']['llm_calls']} LLM calls")

    wo = up(WORK_ORDER, (SAMPLES / WORK_ORDER).read_bytes()).json()
    routing = run(wo["run_id"]).json()["plan"].get("routing") or {}
    check("work order: chunk says Finance, document routed to Maintenance",
          routing.get("final_department") == "Maintenance" and not routing.get("agrees_with_chunks", True),
          routing.get("headline", ""))
    check("work order: Decisions API agrees (or offline)", wo["status"] == "ANALYZED", routing.get("decisions_check", ""))
    cost = inv["plan"].get("cost", {})
    check("trace shows tokens and cost estimate", "usd_estimate" in cost,
          f"{cost.get('input_tokens')} in / {cost.get('output_tokens')} out, ${cost.get('usd_estimate')}")

    trace = run(res[UNCLEAN]["run_id"]).json()
    steps = {s["name"]: s for s in trace["steps"]}
    check("unclean: PII masked", steps["pii_redaction"]["detail"]["counts"] == {"AADHAAR": 1, "PAN": 1, "PHONE": 1, "EMAIL": 1},
          steps["pii_redaction"]["output_summary"])
    check("unclean: injection line quarantined", len(steps["injection_scan"]["detail"]["quarantined_lines"]) == 1,
          steps["injection_scan"]["detail"]["quarantined_lines"][0]["line"][:70])
    check("unclean: no raw PII anywhere in the trace",
          not any(x in json.dumps(trace) for x in ("9847012345", "4521 8890 1234", "ABKPN4521K")))

    dup = up(INVOICE, (SAMPLES / INVOICE).read_bytes()).json()
    check("re-upload -> DUPLICATE", dup["status"] == "DUPLICATE" and dup["doc_id"] == res[INVOICE]["doc_id"])
    for name, data, code in [("drawing.dwg", b"AC1015", 400), ("empty.txt", b"", 400),
                             ("fake.pdf", b"hello", 400), ("big.txt", b"a" * (16 * 1024 * 1024), 413)]:
        r = up(name, data)
        check(f"reject {name} -> {code}, traced", r.status_code == code and r.json()["detail"]["run_id"] is not None)
    check("garbage text -> NEEDS_REVIEW", up("garbage.txt", b"@@@ ### %%% ~~~").json()["status"] == "NEEDS_REVIEW")

    a = requests.post(f"{B}/ask", headers=A, json={"question": "What is the total payable amount on the Alstom invoice?"}).json()
    check("ask: grounded, cited, verified", a["grounded"] and a["citations"][0]["supported"], a["answer"])
    layers = [s["layer"] for s in run(a["run_id"]).json()["steps"]]
    check("ask trace walks the layers in order", layers == ["api", "api", "orchestrator", "knowledge", "knowledge", "llm",
                                                          "llm", "knowledge", "knowledge", "llm", "llm", "actions"])
    r = requests.post(f"{B}/ask", headers=A, json={"question": "What is on the canteen menu today?"}).json()
    check("no answer in documents -> refused", r["answer"] == "Not found in the documents.")
    r = requests.post(f"{B}/ask", headers=A, json={"question": "What is the vendor's Aadhaar number for KYC?"}).json()
    check("masked PII cannot be retrieved", "4521" not in r["answer"], r["answer"][:80])

    check("viewer asks another department -> 403",
          requests.post(f"{B}/ask", headers=F, json={"question": "door sensors", "department": "Safety"}).status_code == 403)
    r = requests.post(f"{B}/ask", headers=F, json={"question": "door sensor inspection"}).json()
    check("viewer only gets own-department chunks", all(not c["file_name"].startswith("safety") for c in r["citations"]))
    check("viewer cannot upload", up("x.txt", b"some words in a text file", F).status_code == 403)
    check("viewer cannot open someone else's run", run(res[UNCLEAN]["run_id"], F).status_code == 403)
    check("reviewer approves the held document",
          requests.post(f"{B}/documents/{res[UNCLEAN]['doc_id']}/review", headers=A,
                        json={"department": "Finance"}).json()["status"] == "APPROVED")
    check("eval report endpoint", "tables" in requests.get(f"{B}/evals/latest", headers=A).json())
    pre = requests.options(f"{B}/ask", headers={"Origin": args.frontend, "Access-Control-Request-Method": "POST",
                                                 "Access-Control-Request-Headers": "x-api-key,content-type"})
    check("CORS preflight from the frontend origin", pre.status_code == 200)
    try:
        check("frontend dev server responds", requests.get(args.frontend, timeout=5).status_code == 200)
    except requests.RequestException:
        check("frontend dev server responds", False, "not running")

    print(f"\n{sum(results)} / {len(results)} checks passed")


if __name__ == "__main__":
    main()
