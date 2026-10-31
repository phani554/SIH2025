"""PII redaction: mask Aadhaar / PAN / phone / email BEFORE text reaches the LLM or the index."""
import re

from .extraction import Page

PII_PATTERNS = {
    "AADHAAR": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "PAN": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "PHONE": re.compile(r"(?:\+91[\s-]?)?\b[6-9]\d{9}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
}


def redact_pii(text: str) -> tuple[str, dict[str, int]]:
    """Replace PII with [AADHAAR], [PAN], ... and return how many of each were found."""
    counts = {}
    for label, pattern in PII_PATTERNS.items():
        text, n = pattern.subn(f"[{label}]", text)
        if n:
            counts[label] = n
    return text, counts


def redact_pages(pages: list[Page]) -> tuple[list[Page], dict[str, int]]:
    clean, totals = [], {}
    for page in pages:
        text, counts = redact_pii(page.text)
        clean.append(Page(page.number, text))
        for label, n in counts.items():
            totals[label] = totals.get(label, 0) + n
    return clean, totals
