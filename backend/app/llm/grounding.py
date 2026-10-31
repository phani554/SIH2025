"""Grounding: build the numbered context and check that the answer is backed by it.

Citation check (no extra LLM call): a sentence is "supported" when at least
SUPPORT_THRESHOLD of its content words appear in the chunk(s) it cites.
faithfulness = supported sentences / all sentences. Cheap and explainable, and it
catches the common failure where the model cites [2] but the fact isn't in [2].
"""
import re

NOT_FOUND = "Not found in the documents."
SUPPORT_THRESHOLD = 0.5
STOPWORDS = {"the", "and", "for", "are", "was", "were", "with", "that", "this", "from", "has",
             "have", "will", "shall", "must", "not", "all", "any", "its", "per", "under", "into"}

# Split after . ! ? (but not "Rs." / "No.", and not right before a [n]) or after a [n].
SENTENCE_SPLIT = re.compile(r"(?<!Rs\.)(?<!No\.)(?<=[.!?])\s+(?!\[)|(?<=\])\s+")


def build_context(chunks: list[dict]) -> str:
    lines = []
    for n, c in enumerate(chunks, start=1):
        page = f", p.{c['page']}" if c.get("page") else ""
        lines.append(f"[{n}] ({c['file_name']}{page})\n{c['text']}")
    return "\n".join(lines)


def content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in STOPWORDS}


def check_citations(answer: str, chunks: list[dict]) -> tuple[float, dict[int, bool], list[dict]]:
    """Return (faithfulness 0-1, {citation number: supported?}, per-sentence table)."""
    sentences = [s for s in SENTENCE_SPLIT.split(answer.strip()) if content_words(s)]
    supported_count, per_citation, table = 0, {}, []
    for sentence in sentences:
        cited = [int(n) for n in re.findall(r"\[(\d+)\]", sentence) if 1 <= int(n) <= len(chunks)]
        words = content_words(re.sub(r"\[\d+\]", "", sentence))
        source_words = set().union(*(content_words(chunks[n - 1]["text"]) for n in cited)) if cited else set()
        overlap = len(words & source_words) / max(len(words), 1)
        ok = bool(cited) and overlap >= SUPPORT_THRESHOLD
        supported_count += ok
        for n in cited:
            per_citation[n] = per_citation.get(n, False) or ok
        table.append({"sentence": sentence[:200], "cites": cited, "word_overlap": round(overlap, 2),
                      "supported": ok})
    faithfulness = supported_count / len(sentences) if sentences else 0.0
    return faithfulness, per_citation, table
