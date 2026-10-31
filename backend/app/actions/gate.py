"""Review gate: decide whether a human must look at a document before anyone relies on it."""
from ..config import settings

RULES = [f"Level 1 confidence < {settings.review_threshold}", "urgency is Critical",
         "prompt injection was quarantined", "an LLM level failed validation twice",
         "no readable text", "embedding provider was down",
         "department unclear: Decisions API disagrees with Level 1, or is below the agreement threshold"]


def review_gate(level1, earlier_reasons: list[str]) -> tuple[str, list[str]]:
    """Returns (status, reasons). earlier_reasons come from ingestion (injection, no text...)."""
    reasons = list(earlier_reasons)
    if level1:
        if level1.primary.confidence < settings.review_threshold:
            reasons.append(f"low confidence {level1.primary.confidence:.2f} < {settings.review_threshold}")
        if level1.urgency == "Critical":
            reasons.append("urgency is Critical")
    return ("NEEDS_REVIEW" if reasons else "ANALYZED"), reasons
