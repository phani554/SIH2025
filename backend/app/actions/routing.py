"""Department routing: three pieces of evidence, one decision, one plain-English explanation.

  1. chunk signals  (ingestion)  cheap keyword vote per chunk. Local view: one chunk at a time.
  2. Level 1        (llm)        reads the whole document + department definitions. DECIDES.
  3. Decisions API  (llm)        probability for every department. CHECKS how sure we are.

Rules (all in this file, easy to change):
  - The document goes to Level 1's primary department.
  - A chunk that points elsewhere does NOT move the document. We record it and explain it
    ("chunk #2 looks like Finance, but the document is Maintenance because ..."), because
    one paragraph about money does not make a repair order a Finance document.
  - If the Decisions API picks a different department, or is less than THRESHOLD sure,
    the document goes to human review with that reason.
  - Access control follows the document's department, never one chunk's words.
"""


def decide(signals: list[dict], level1, decision: dict | None, threshold: float = 0.6) -> dict:
    final = level1.primary.name
    votes: dict[str, int] = {}
    for s in signals:
        if s["signal"]:
            votes[s["signal"]] = votes.get(s["signal"], 0) + 1
    disagreements = [{"chunk_no": s["chunk_no"], "chunk_says": s["signal"], "matched": s["matched"],
                      "document_says": final} for s in signals if s["signal"] and s["signal"] != final]

    # 1. chunks vs document
    if disagreements:
        d = disagreements[0]
        explanation = (f"Chunk #{d['chunk_no']} looks like {d['chunk_says']}, but the document as a whole "
                       f"is {final}. {level1.reasoning}")
        if level1.why_not:
            explanation += f" Why not another department: {level1.why_not}"
    else:
        explanation = f"Every chunk with a signal points to {final}."

    # 2. Level 1 vs Decisions API
    review_reason = None
    if decision:
        p_final = next((p["probability"] for p in decision["probabilities"] if p["value"] == final), 0.0)
        if decision["choice"] != final:
            review_reason = (f"department unclear: Level 1 says {final}, "
                             f"Decisions API says {decision['choice']} ({decision['confidence']:.2f})")
        elif decision["confidence"] < threshold and not str(decision.get("model", "")).startswith("offline"):
            # offline "shares" are keyword ratios, not probabilities, so the threshold only applies online
            review_reason = f"department unclear: Decisions API only {decision['confidence']:.2f} sure of {final}"
        check = (f"Decisions API agrees: {final} with probability {p_final:.2f}." if not review_reason
                 else review_reason + ".")
    else:
        p_final = None
        check = "Decisions API not used; Level 1 decides alone."

    headline = (f"{final}" + (f" (chunk #{disagreements[0]['chunk_no']} looked like "
                              f"{disagreements[0]['chunk_says']})" if disagreements else "")
                + ("; sent to review" if review_reason else ""))
    return {
        "final_department": final,
        "headline": headline,
        "explanation": explanation,
        "reason": level1.reasoning + (f" Why not another department: {level1.why_not}" if level1.why_not else ""),
        "decisions_check": check,
        "decisions_probability": p_final,
        "decisions": decision,
        "chunk_votes": votes,
        "agrees_with_chunks": not disagreements,
        "disagreements": disagreements,
        "review_reason": review_reason,
        "threshold": threshold,
    }
