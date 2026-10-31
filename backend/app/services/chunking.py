"""Three chunking strategies. Pick one with CHUNK_STRATEGY in .env.

fixed      Overlapping windows of N words. Simple baseline; may cut mid-sentence,
           the overlap makes up for it.
recursive  Split on the biggest natural boundary first (blank line -> line -> sentence),
           only falling back to smaller ones when a piece is still too long, then
           pack pieces up to N words. Keeps paragraphs and clauses whole.
sentence   One chunk per group of K sentences, plus a "window" of neighbouring
           sentences stored as context. Precise matching, enough context to answer.

Every chunk keeps its page number, so citations can say "file, p.3".
The eval script (scripts/run_evals.py) compares them on the same questions.
"""
import re
from dataclasses import dataclass

from .extraction import Page

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    chunk_no: int
    page: int
    text: str


# ---------- fixed ----------

def chunk_words(text: str, size: int = 200, overlap: int = 40) -> list[str]:
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    words = text.split()
    if not words:
        return []
    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
    return chunks


# ---------- recursive ----------

SEPARATORS = [r"\n\s*\n", r"\n", SENTENCE_END.pattern]


def _split(text: str, size: int, level: int = 0) -> list[str]:
    """Split text into pieces of at most `size` words, using the coarsest separator possible."""
    if len(text.split()) <= size:
        return [text.strip()] if text.strip() else []
    if level == len(SEPARATORS):                       # no boundary left: hard cut
        return chunk_words(text, size, 0)
    pieces = []
    for part in re.split(SEPARATORS[level], text):
        pieces += _split(part, size, level + 1)
    return pieces


def chunk_recursive(text: str, size: int = 200, overlap: int = 40) -> list[str]:
    pieces = _split(text, size)
    chunks, current = [], []
    for piece in pieces:                               # pack small pieces together
        if current and len("\n".join(current + [piece]).split()) > size:
            chunks.append("\n".join(current))
            tail = " ".join(current).split()[-overlap:] if overlap else []
            current = [" ".join(tail)] if tail else []
        current.append(piece)
    if current:
        chunks.append("\n".join(current))
    return chunks                                      # line breaks kept: headings stay separate


# ---------- sentence window ----------

def chunk_sentences(text: str, sentences_per_chunk: int = 3, window: int = 1) -> list[str]:
    """Group sentences; each chunk also carries `window` sentences before and after."""
    sentences = [" ".join(s.split()) for s in SENTENCE_END.split(text) if s.strip()]
    chunks = []
    for start in range(0, len(sentences), sentences_per_chunk):
        lo = max(0, start - window)
        hi = min(len(sentences), start + sentences_per_chunk + window)
        chunks.append(" ".join(sentences[lo:hi]))
    return chunks


STRATEGIES = {
    "fixed": lambda text, size, overlap: chunk_words(text, size, overlap),
    "recursive": lambda text, size, overlap: chunk_recursive(text, size, overlap),
    "sentence": lambda text, size, overlap: chunk_sentences(text),
}


def chunk_pages(pages: list[Page], size: int, overlap: int, strategy: str = "recursive") -> list[Chunk]:
    """Chunk each page separately so every chunk keeps its page number (for citations)."""
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown chunk strategy {strategy!r}; choose from {list(STRATEGIES)}")
    split = STRATEGIES[strategy]
    result: list[Chunk] = []
    for page in pages:
        for text in split(page.text, size, overlap):
            result.append(Chunk(chunk_no=len(result), page=page.number, text=text))
    return result
