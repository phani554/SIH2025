"""Per-chunk department signals: a cheap keyword vote for every chunk, BEFORE any LLM call.

Why: one chunk can look like one department while the document belongs to another
(a repair work order with a cost table: that chunk "looks like" Finance).
We keep these signals so the Show me how drawer can put them next to the Level 1
decision and say plainly where they disagree and why.
"""
from ..departments import keyword_scores


def chunk_signals(chunks) -> list[dict]:
    out = []
    for c in chunks:
        scores = keyword_scores(c.text)
        if scores:
            top = max(scores, key=lambda d: scores[d]["score"])
            out.append({"chunk_no": c.chunk_no, "signal": top, "score": scores[top]["score"],
                        "matched": ", ".join(f"{w} x{n}" for w, n in scores[top]["words"].items()),
                        "preview": c.text[:90]})
        else:
            out.append({"chunk_no": c.chunk_no, "signal": None, "score": 0, "matched": "", "preview": c.text[:90]})
    return out
