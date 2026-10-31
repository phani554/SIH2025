"""Split page text into overlapping word windows.

Why overlap: a sentence cut at a chunk boundary still appears whole in the
neighbouring chunk, so retrieval doesn't lose it.
Why words, not tokens: simple, no tokenizer dependency; ~200 words ≈ 260 tokens.
"""
from dataclasses import dataclass

from .extraction import Page


@dataclass
class Chunk:
    chunk_no: int
    page: int
    text: str


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


def chunk_pages(pages: list[Page], size: int, overlap: int) -> list[Chunk]:
    """Chunk each page separately so every chunk keeps its page number (for citations)."""
    result: list[Chunk] = []
    for page in pages:
        for text in chunk_words(page.text, size, overlap):
            result.append(Chunk(chunk_no=len(result), page=page.number, text=text))
    return result
