"""End to end through the API: offline provider, auth on, traces checked step by step."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_llm
from app.main import app
from app.llm.providers import LLMError, OfflineProvider
from conftest import SAMPLES

client = TestClient(app)
INVOICE = "invoice_INV-2025-0917_alstom.txt"
SAFETY = "safety_circular_SC-14_platform_screen_doors.txt"
UNCLEAN = "unclean_vendor_letter_injection_pii.txt"


def upload(name, headers, data=None):
    body = data if data is not None else (SAMPLES / name).read_bytes()
    return client.post("/documents", files={"file": (name, body, "text/plain")}, headers=headers)


def run(run_id, headers):
    return client.get(f"/runs/{run_id}", headers=headers).json()


def step(trace, prefix):
    return next(s for s in trace["steps"] if s["name"].startswith(prefix))


@pytest.fixture(scope="module", autouse=True)
def demo_docs(keys):
    return {name: upload(name, keys["admin"]).json() for name in (INVOICE, SAFETY, UNCLEAN)}


def test_no_key_is_rejected():
    assert client.get("/documents").status_code == 401
    assert client.get("/documents", headers={"X-API-Key": "mm_wrong"}).status_code == 401


def test_clean_invoice_full_trace(demo_docs, keys):
    res = demo_docs[INVOICE]
    assert res["status"] == "ANALYZED"
    trace = run(res["run_id"], keys["admin"])
    names = [s["name"] for s in trace["steps"]]
    assert names == ["auth", "plan_run", "upload_validation", "sha256_dedupe", "save_original", "extract_text",
                     "pii_redaction", "injection_scan", "chunking", "embed_chunks", "index_chunks",
                     "level1_classification (attempt 1)", "level2_extraction (attempt 1)",
                     "review_gate", "create_action_items", "save_results"]
    layers = {s["name"]: s["layer"] for s in trace["steps"]}
    assert (layers["upload_validation"], layers["sha256_dedupe"], layers["embed_chunks"], layers["review_gate"]) == \
        ("ingestion", "knowledge", "llm", "actions")
    # Preliminary analysis: Level 1 result + the bounded run plan
    assert trace["plan"]["level1"]["departments"][0]["name"] == "Finance"
    assert trace["plan"]["plan"]["max_llm_calls"] == 4 and trace["plan"]["plan"]["max_retries"] == 1
    assert trace["plan"]["used"]["llm_calls"] == 2
    l1 = step(trace, "level1")
    assert "LEVEL 1" in l1["detail"]["prompt"] and l1["detail"]["validation"]["passed"]
    assert "[EMAIL]" in l1["detail"]["prompt"]           # the LLM only ever saw redacted text
    l2 = step(trace, "level2")["detail"]["validated"]
    assert {"value": "Rs. 21,71,200", "confidence": 0.9} in l2["amounts"]


def test_unclean_document_is_blocked_and_redacted(demo_docs, keys):
    res = demo_docs[UNCLEAN]
    assert res["status"] == "NEEDS_REVIEW"
    trace = run(res["run_id"], keys["admin"])
    pii = step(trace, "pii_redaction")
    assert pii["detail"]["counts"] == {"AADHAAR": 1, "PAN": 1, "PHONE": 1, "EMAIL": 1}
    inj = step(trace, "injection_scan")["detail"]["quarantined_lines"]
    assert inj[0]["matched"].lower().startswith("ignore all previous instructions")
    prompt = step(trace, "level1")["detail"]["prompt"]
    assert "Ignore all previous" not in prompt and "9847012345" not in prompt
    assert "prompt injection" in step(trace, "review_gate")["output_summary"]
    doc = client.get(f"/documents/{res['doc_id']}", headers=keys["admin"]).json()
    assert "4521 8890 1234" not in str(doc) and doc["review_reasons"]
    for raw in ("4521 8890 1234", "ABKPN4521K", "9847012345", "sreekumar.nair@"):
        assert raw not in json.dumps(trace)                  # no raw PII anywhere in the trace


def test_duplicate_reupload(demo_docs, keys):
    again = upload(INVOICE, keys["admin"]).json()
    assert again["status"] == "DUPLICATE" and again["doc_id"] == demo_docs[INVOICE]["doc_id"]
    trace = run(again["run_id"], keys["admin"])
    assert step(trace, "sha256_dedupe")["output_summary"].startswith("HIT")
    assert step(trace, "level1")["status"] == "skipped"     # no LLM spend on a duplicate


@pytest.mark.parametrize("name,data,code", [
    ("empty.txt", b"", 400), ("layout.dwg", b"AC1015", 400), ("fake.pdf", b"hello", 400),
    ("huge.txt", b"a" * (16 * 1024 * 1024), 413),
])
def test_rejected_uploads_still_leave_a_trace(name, data, code, keys):
    res = upload(name, keys["admin"], data)
    assert res.status_code == code
    trace = run(res.json()["detail"]["run_id"], keys["admin"])
    assert trace["status"] == "REJECTED" and step(trace, "upload_validation")["status"] == "failed"


def test_garbage_text_goes_to_review(keys):
    res = upload("garbage.txt", keys["admin"], b"@@@ ### %%% 1234 ~~~ ^^^").json()
    assert res["status"] == "NEEDS_REVIEW"
    assert step(run(res["run_id"], keys["admin"]), "level1")["status"] == "skipped"


class DownProvider(OfflineProvider):
    def generate(self, prompt, json_mode=False):
        raise LLMError("OpenAI unreachable")

    def embed(self, texts):
        raise LLMError("OpenAI unreachable")


def test_provider_down_means_needs_review(keys):
    app.dependency_overrides[get_llm] = DownProvider
    try:
        res = upload("down.txt", keys["admin"], b"Invoice for payment of Rs. 1,000 due by 1 May 2026 from vendor.").json()
    finally:
        app.dependency_overrides.clear()
    assert res["status"] == "NEEDS_REVIEW"
    trace = run(res["run_id"], keys["admin"])
    assert step(trace, "embed_chunks")["status"] == "failed"
    assert step(trace, "index_chunks")["status"] == "ok"          # text kept for keyword search
    assert step(trace, "level1")["status"] == "failed" and step(trace, "level2")["status"] == "skipped"


def test_ask_trace_shows_queries_and_scores(keys):
    res = client.post("/ask", headers=keys["admin"],
                      json={"question": "What is the total payable amount on the Alstom invoice?", "use_hyde": True}).json()
    assert res["grounded"] and "21,71,200" in res["answer"] and res["citations"][0]["supported"]
    trace = run(res["run_id"], keys["admin"])
    names = [s["name"] for s in trace["steps"]]
    assert names == ["auth", "query_received", "plan_run", "department_filter", "keyword_search_bm25",
                     "hyde_generation", "embed_query", "vector_search_cosine", "rrf_fusion", "llm_answer",
                     "citation_check", "audit_query"]
    assert names == trace["plan"]["plan"]["steps"]                 # it did exactly what it planned
    kw = step(trace, "keyword_search_bm25")["detail"]
    assert '"alstom"' in kw["match"] and "bm25" in kw["top"][0]
    assert "cosine" in step(trace, "vector_search_cosine")["detail"]["top"][0]
    assert step(trace, "rrf_fusion")["detail"]["fused"][0]["file"] == INVOICE


def test_question_with_no_answer_is_refused(keys):
    res = client.post("/ask", headers=keys["admin"], json={"question": "What is on the canteen menu today?"}).json()
    assert res["answer"] == "Not found in the documents." and res["citations"] == []
    assert run(res["run_id"], keys["admin"])["status"] == "REFUSED"


def test_pii_cannot_be_retrieved(keys):
    res = client.post("/ask", headers=keys["admin"], json={"question": "What is the vendor's Aadhaar number for KYC?"}).json()
    assert "4521" not in res["answer"]


def test_viewer_limited_to_own_department(demo_docs, keys):
    safety_id = demo_docs[SAFETY]["doc_id"]
    assert client.get(f"/documents/{safety_id}", headers=keys["finance"]).status_code == 403
    assert client.post("/ask", headers=keys["finance"],
                       json={"question": "door sensors", "department": "Safety"}).status_code == 403
    res = client.post("/ask", headers=keys["finance"], json={"question": "door sensor inspection"}).json()
    assert all(not c["file_name"].startswith("safety") for c in res["citations"])
    trace = run(res["run_id"], keys["finance"])
    assert step(trace, "department_filter")["detail"]["department"] == "Finance"
    assert client.get(f"/runs/{demo_docs[SAFETY]['run_id']}", headers=keys["finance"]).status_code == 403
    assert upload("x.txt", keys["finance"], b"hello").status_code == 403


def test_review_and_audit(demo_docs, keys):
    doc_id = demo_docs[UNCLEAN]["doc_id"]
    res = client.post(f"/documents/{doc_id}/review", json={"department": "Finance"}, headers=keys["reviewer"])
    assert res.json()["status"] == "APPROVED"
    assert client.get("/audit", headers=keys["finance"]).status_code == 403
    actions = {r["action"] for r in client.get("/audit?limit=500", headers=keys["admin"]).json()}
    assert {"INGEST", "REDACT", "INJECTION_FLAG", "ANALYZE", "DUPLICATE", "QUERY", "REVIEW"} <= actions


def test_eval_report_endpoint(keys):
    res = client.get("/evals/latest", headers=keys["admin"])
    assert res.status_code in (200, 404)
    if res.status_code == 200:
        assert res.json()["tables"]
