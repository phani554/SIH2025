"""Second opinion on the department, from the OpenAI Decisions API (POST /v1/decisions).

Why a second call when Level 1 already names a department?
  - Level 1's "confidence" is a number the model WRITES in its JSON. It is often 1.0. It is not measured.
  - The Decisions API returns a probability for every department (a real distribution), so
    "how sure are we?" becomes a number we can put a threshold on.
  - It is cheap: about 300-1,500 input tokens at $0.10 per 1M, output is free (~$0.0001 per document).

We send the same department definitions the Level 1 prompt uses, as the choice descriptions.
The orchestrator compares this answer with Level 1 and with the per-chunk signals (actions/routing.py).
"""
from ..departments import DEPARTMENT_DEFINITIONS, ROUTING_RULE

MAX_CHARS = 8_000


def department_questions() -> list[dict]:
    return [{
        "type": "choice",
        "name": "department",
        "instructions": f"Which KMRL department must act on this document? {ROUTING_RULE}",
        "choices": [{"value": name, "description": f"{d['owns']} Not: {d['not']}"}
                    for name, d in DEPARTMENT_DEFINITIONS.items()],
    }]


def department_decision(llm, tracer, text: str) -> dict | None:
    """One traced call. Returns {"choice", "confidence", "probabilities"} or None if unavailable."""
    with tracer.step("department_decision", "llm") as s:
        questions = department_questions()
        s.input = f"{min(len(text), MAX_CHARS):,} chars + {len(questions[0]['choices'])} department definitions"
        s.detail = {"endpoint": "POST /v1/decisions" if llm.name == "openai" else "offline keyword shares",
                    "questions": questions}
        try:
            data = llm.decide(text[:MAX_CHARS], questions)
        except Exception as exc:          # Decisions down: routing sends the document to a reviewer
            s.status, s.output = "failed", f"Decisions API unavailable: {str(exc)[:200]}"
            return None
        answer = data["answers"][0]
        if answer.get("type") != "choice":
            s.status, s.output = "failed", f"no choice returned ({answer.get('type')})"
            return None
        probs = sorted(answer["probabilities"], key=lambda p: -p["probability"])
        s.output = f"{answer['choice']} (confidence {answer['confidence']:.2f})"
        s.detail.update(model=data.get("model"), probabilities=probs, confidence=answer["confidence"],
                        tokens={"prompt": data.get("usage", {}).get("input_tokens"), "completion": 0},
                        raw_response=data)
        return {"choice": answer["choice"], "confidence": answer["confidence"], "probabilities": probs,
                "model": data.get("model")}
