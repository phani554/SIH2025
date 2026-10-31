"""Prompt-injection scan: quarantine lines that try to give the LLM instructions.

A quarantined line is removed before chunking, so it is never indexed and never
sent to the LLM, and the document goes to human review. Regex catches common
phrasings, not everything: it is one layer, next to the prompts telling the model
that documents are data.
"""
import re

from .extraction import Page

INJECTION_PATTERNS = re.compile(
    r"(ignore|disregard|forget) (all |any )?(previous|prior|above|earlier) (instructions|rules)"
    r"|disregard (the )?(system|previous) (prompt|instructions)"
    r"|you are now\b"
    r"|reveal (your|the) (system prompt|instructions)"
    r"|act as (an? )?(admin|developer|system)"
    r"|mark (this|every|all) .{0,40}(as )?(approved|paid)",
    re.IGNORECASE,
)


def find_injection(text: str) -> str | None:
    """Return the suspicious phrase, or None."""
    match = INJECTION_PATTERNS.search(text)
    return match.group(0) if match else None


def quarantine_injections(pages: list[Page]) -> tuple[list[Page], list[dict]]:
    clean, quarantined = [], []
    for page in pages:
        kept = []
        for line in page.text.splitlines():
            phrase = find_injection(line)
            if phrase:
                quarantined.append({"page": page.number, "line": line.strip()[:300], "matched": phrase})
            else:
                kept.append(line)
        clean.append(Page(page.number, "\n".join(kept)))
    return clean, quarantined
