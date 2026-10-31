"""End-to-end through the API with the offline provider."""
from fastapi.testclient import TestClient

from app.main import app
from conftest import SAMPLES

client = TestClient(app)


def upload(name):
    path = SAMPLES / name
    return client.post("/documents", files={"file": (name, path.read_bytes(), "text/plain")})


def test_upload_classifies_and_dedupes():
    first = upload("invoice_INV-2025-0917_alstom.txt").json()
    assert first["duplicate"] is False
    again = upload("invoice_INV-2025-0917_alstom.txt").json()
    assert again == {**first, "duplicate": True}      # same bytes -> same document

    doc = client.get(f"/documents/{first['doc_id']}").json()
    assert doc["departments"][0]["name"] == "Finance"
    assert doc["chunk_count"] >= 1


def test_ask_returns_cited_answer():
    upload("safety_circular_SC-14_platform_screen_doors.txt")
    res = client.post("/ask", json={"question": "Which stations need door sensor inspection?"}).json()
    assert res["grounded"] is True
    assert res["citations"][0]["file_name"].startswith("safety_circular")


def test_department_filter_limits_retrieval():
    upload("tender_notice_cctv_upgrade.txt")
    res = client.post("/ask", json={"question": "door sensor inspection", "department": "Finance"}).json()
    assert all(c["file_name"].startswith("invoice") for c in res["citations"])


def test_unsupported_file_is_rejected():
    res = client.post("/documents", files={"file": ("virus.exe", b"MZ...", "application/octet-stream")})
    assert res.status_code == 400


def test_review_and_audit_trail():
    doc_id = upload("hr_notice_training_malayalam_signage.txt").json()["doc_id"]
    res = client.post(f"/documents/{doc_id}/review", json={"department": "HR", "reviewer": "phani"})
    assert res.json()["status"] == "APPROVED"
    actions = [row["action"] for row in client.get("/audit").json()]
    assert {"INGEST", "ANALYZE", "QUERY", "REVIEW"} <= set(actions)
