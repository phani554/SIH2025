"""Department routing: definitions, chunk-vs-document disagreement, Decisions API check, cost in the trace."""
from fastapi.testclient import TestClient

from app.actions.routing import decide
from app.api.deps import get_llm
from app.departments import DEPARTMENTS, DEPARTMENT_DEFINITIONS
from app.llm.providers import OfflineProvider
from app.llm.schemas import Level1Result
from app.main import app
from conftest import SAMPLES

client = TestClient(app)
WORK_ORDER = "work_order_WO-RS-2025-0412_bogie_overhaul.txt"


def _l1(dept="Maintenance", why_not=""):
    return Level1Result(departments=[{"name": dept, "confidence": 0.9}], doc_type="Work Order",
                        urgency="Medium", summary="s", reasoning="It is a repair work order.", why_not=why_not)


def test_every_department_has_a_definition_and_boundary():
    for name in DEPARTMENTS:
        d = DEPARTMENT_DEFINITIONS[name]
        assert d["owns"] and d["not"] and d["keywords"]
    body = client.get("/departments").json()
    assert len(body["departments"]) == 8 and "ACT" in body["rule"]


def test_work_order_chunk_looks_like_finance_but_document_is_maintenance(keys):
    data = (SAMPLES / WORK_ORDER).read_bytes()
    res = client.post("/documents", files={"file": (WORK_ORDER, data, "text/plain")}, headers=keys["admin"]).json()
    trace = client.get(f"/runs/{res['run_id']}", headers=keys["admin"]).json()
    routing = trace["plan"]["routing"]
    assert routing["final_department"] == "Maintenance"
    assert not routing["agrees_with_chunks"]
    assert routing["disagreements"][0]["chunk_says"] == "Finance"
    assert "looks like Finance" in routing["explanation"] and "Maintenance" in routing["explanation"]
    assert res["status"] == "ANALYZED"            # a disagreeing chunk is explained, not escalated
    doc = client.get(f"/documents/{res['doc_id']}", headers=keys["admin"]).json()
    assert doc["routing"]["final_department"] == "Maintenance"
    # Access follows the document, not the chunk: the Finance viewer cannot retrieve it.
    ask = client.post("/ask", json={"question": "What is the total payable for the bogie overhaul spares?"},
                      headers=keys["finance"]).json()
    assert all(c["file_name"] != WORK_ORDER for c in ask.get("citations", []))


def test_decisions_api_disagreement_sends_to_review():
    signals = [{"chunk_no": 0, "signal": "Maintenance", "matched": "bogie x2"}]
    decision = {"choice": "Finance", "confidence": 0.7, "model": "gpt-6-luna",
                "probabilities": [{"value": "Finance", "probability": 0.7}, {"value": "Maintenance", "probability": 0.3}]}
    r = decide(signals, _l1(), decision)
    assert r["review_reason"].startswith("department unclear: Level 1 says Maintenance")


def test_decisions_api_low_confidence_sends_to_review_but_agreement_passes():
    signals = [{"chunk_no": 0, "signal": "Maintenance", "matched": "bogie x2"}]
    low = {"choice": "Maintenance", "confidence": 0.45, "model": "gpt-6-luna",
           "probabilities": [{"value": "Maintenance", "probability": 0.45}]}
    high = dict(low, confidence=0.97, probabilities=[{"value": "Maintenance", "probability": 0.97}])
    assert "only 0.45 sure" in decide(signals, _l1(), low)["review_reason"]
    ok = decide(signals, _l1(), high)
    assert ok["review_reason"] is None and ok["decisions_probability"] == 0.97


def test_openai_decide_posts_definitions(monkeypatch):
    from app.llm import providers as llm_module
    from app.llm.decisions import department_questions
    sent = {}

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"model": "gpt-6-luna", "answers": [], "usage": {"input_tokens": 300}}

    monkeypatch.setattr(llm_module.requests, "post", lambda url, json, timeout, headers: sent.update(url=url, body=json) or R())
    llm_module.OpenAIProvider("sk-test", "gpt-6-luna", "text-embedding-3-small").decide("doc", department_questions())
    assert sent["url"].endswith("/decisions") and sent["body"]["model"] == "gpt-6-luna"
    choices = sent["body"]["questions"][0]["choices"]
    assert len(choices) == 8 and "Not:" in choices[0]["description"]


def test_gpt6_uses_reasoning_effort_not_temperature(monkeypatch):
    from app.llm import providers as llm_module
    sent = {}

    class R:
        status_code = 200
        text = ""

        def json(self):
            return {"model": "gpt-6-luna", "choices": [{"message": {"content": "{}"}}], "usage": {}}

    monkeypatch.setattr(llm_module.requests, "post", lambda url, json, timeout, headers: sent.update(body=json) or R())
    llm_module.OpenAIProvider("sk", "gpt-6-luna", "e").generate("x", json_mode=True)
    assert "temperature" not in sent["body"] and sent["body"]["reasoning_effort"] == "low"


def test_trace_has_cost_estimate(keys):
    class PricedOffline(OfflineProvider):
        def generate(self, prompt, json_mode=False):
            reply = super().generate(prompt, json_mode)
            reply.model, reply.prompt_tokens, reply.completion_tokens = "gpt-6-luna-2026", 1000, 200
            return reply
    app.dependency_overrides[get_llm] = PricedOffline
    try:
        res = client.post("/documents", files={"file": ("priced.txt", b"Invoice payment of Rs. 500 for bogie repair "
                                                 b"work at the depot, due by 12 October 2025, unique 98765.",
                                                 "text/plain")}, headers=keys["admin"]).json()
        cost = client.get(f"/runs/{res['run_id']}", headers=keys["admin"]).json()["plan"]["cost"]
        assert cost["input_tokens"] >= 2000 and cost["usd_estimate"] > 0
    finally:
        app.dependency_overrides.clear()


# ---------- unsure -> the machine does not decide; a human does ----------

UNCLEAR = "unclear_memo_kaloor_lost_found_cheque.txt"


class UnsureProvider(OfflineProvider):
    """Offline LLM, but the Decisions API answers like the live run did on the unclear memo."""
    def decide(self, text, questions):
        probs = [{"value": "Operations", "probability": 0.41}, {"value": "Finance", "probability": 0.27},
                 {"value": "Engineering", "probability": 0.20}]
        return {"model": "gpt-6-luna", "usage": {"input_tokens": 900},
                "answers": [{"type": "choice", "name": "department", "choice": "Operations",
                             "confidence": 0.33, "probabilities": probs}]}


def test_unsure_decision_has_no_department():
    r = decide([], _l1("Finance"), {"choice": "Operations", "confidence": 0.33, "model": "gpt-6-luna",
                                    "probabilities": [{"value": "Operations", "probability": 0.41},
                                                      {"value": "Finance", "probability": 0.27}]})
    assert r["final_department"] is None and r["pending_review"]
    assert r["candidates"] == ["Finance", "Operations"] and r["level1_department"] == "Finance"
    assert "Pending review" in r["headline"]


def test_no_chunk_signals_is_not_called_agreement():
    r = decide([{"chunk_no": 0, "signal": None, "matched": ""}], _l1(), None)
    assert "No chunk had department keywords" in r["explanation"]


def test_unclear_memo_waits_for_a_human_then_reviewer_decides(keys):
    app.dependency_overrides[get_llm] = UnsureProvider
    try:
        data = (SAMPLES / UNCLEAR).read_bytes()
        res = client.post("/documents", files={"file": (UNCLEAR, data, "text/plain")}, headers=keys["admin"]).json()
    finally:
        app.dependency_overrides.pop(get_llm, None)
    assert res["status"] == "NEEDS_REVIEW"
    doc_id = res["doc_id"]
    doc = client.get(f"/documents/{doc_id}", headers=keys["admin"]).json()
    assert doc["routing"]["pending_review"] and doc["departments"] == [] and doc["action_items"] == []
    trace = client.get(f"/runs/{res['run_id']}", headers=keys["admin"]).json()
    held = next(s for s in trace["steps"] if s["name"] == "create_action_items")
    assert held["status"] == "skipped" and "held" in (held.get("output") or held.get("output_summary") or "")
    # nobody's department can see it yet
    assert client.get(f"/documents/{doc_id}", headers=keys["finance"]).status_code == 403
    # approving without a department is refused: the human must decide
    assert client.post(f"/documents/{doc_id}/review", json={}, headers=keys["reviewer"]).status_code == 400
    ok = client.post(f"/documents/{doc_id}/review", json={"department": "Finance"}, headers=keys["reviewer"]).json()
    assert ok["status"] == "APPROVED" and ok["department"] == "Finance"
    doc = client.get(f"/documents/{doc_id}", headers=keys["finance"]).json()      # Finance can see it now
    assert doc["routing"]["reviewed_by"] and doc["routing"]["final_department"] == "Finance"
    assert ok["action_items_created"] == len(doc["action_items"])


def test_rejected_document_is_never_searched(keys):
    body = b"NOTICE: Kaloor parking tariff pilot. Parking fee Rs. 25 per hour from 1 December 2025 at Kaloor."
    res = client.post("/documents", files={"file": ("parking.txt", body, "text/plain")}, headers=keys["admin"]).json()
    rej = client.post(f"/documents/{res['doc_id']}/review", json={"approve": False}, headers=keys["reviewer"]).json()
    assert rej["status"] == "REJECTED"
    ask = client.post("/ask", json={"question": "What is the Kaloor parking fee per hour?"}, headers=keys["admin"]).json()
    assert all(c["file_name"] != "parking.txt" for c in ask.get("citations", []))
