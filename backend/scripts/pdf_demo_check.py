"""Upload the two diagram PDFs to a FRESH database and print what each step did.

    DB_PATH=/tmp/pdfcheck.db UPLOAD_DIR=/tmp/pdfcheck_up OUT=/tmp/pdfcheck.json python -m scripts.pdf_demo_check

Uses whatever LLM_PROVIDER is in .env. Needs the tesseract binary for OCR.
"""
import json, os
from app.db import init_db, get_conn
from app.api.auth import create_api_key
init_db()
with get_conn() as conn:
    admin = create_api_key(conn, "demo-admin", "admin")
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app); H = {"X-API-Key": admin}
out = {}
for f in ["clean_rolling_stock_report_Q2_2025.pdf", "unclean_cctv_bid_sentinel_vision.pdf"]:
    r = c.post("/documents", headers=H, files={"file": (f, open("sample_docs/" + f, "rb"), "application/pdf")})
    j = r.json(); print(f, r.status_code, j)
    run = c.get(f"/runs/{j['run_id']}", headers=H).json()
    steps = {s["name"]: s for s in run["steps"]}
    for n in ["extract_text", "pii_redaction", "injection_scan", "chunking", "level1_classification", "department_decision", "department_routing", "review_gate", "create_action_items"]:
        s = steps.get(n); 
        if s: print(f"  {n}: [{s['status']}] {s['output_summary']}")
    d = c.get(f"/documents/{j['doc_id']}", headers=H).json()
    print("  status", d.get("status"), "reasons", d.get("review_reasons"), "summary", (d.get("summary") or "")[:200])
    out[f] = {"upload": j, "steps": run["steps"], "doc": d}
json.dump(out, open(os.environ["OUT"], "w"), indent=1, default=str)
for q in ["Who approved the Q2 maintenance report and on what date?", "What is the MDBF target?"]:
    r = c.post("/ask", headers=H, json={"question": q}).json()
    print("Q:", q, "\nA:", r.get("answer"), "\n cites:", [(x.get("file_name"), x.get("page")) for x in r.get("citations", r.get("sources", []))][:3], r.get("faithfulness"))
