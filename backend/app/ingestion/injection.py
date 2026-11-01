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
        kept, carry = [], 0
        for line in page.text.splitlines():
            phrase = find_injection(line)
            if phrase or carry:
                quarantined.append({"page": page.number, "line": line.strip()[:300],
                                    "matched": phrase or "(rest of the flagged sentence)"})
                # PDFs wrap a sentence over several lines: if the flagged sentence has not ended,
                # quarantine the next line too (at most 2 more), so no half-instruction is indexed.
                ended = line.rstrip().endswith((".", "!", "?"))
                carry = 0 if ended else (2 if phrase else carry - 1)
            else:
                kept.append(line)
        clean.append(Page(page.number, "\n".join(kept)))
    return clean, quarantined
