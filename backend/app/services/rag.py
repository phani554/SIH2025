"""Grounded question answering with citations.

    question -> hybrid_search -> numbered context -> LLM (answer ONLY from context)
             -> keep only citations the answer actually used -> audit log
"""
import json
import re

from ..db import audit
from ..schemas import AskResponse, Citation
from .retrieval import hybrid_search

NOT_FOUND = "Not found in the documents."

PROMPT = """You answer questions for KMRL staff using ONLY the numbered context below.
Put the source number like [1] after every claim. If the context does not contain
the answer, reply exactly: "{not_found}" Do not use outside knowledge.

CONTEXT:
{context}

QUESTION: {question}
ANSWER:"""


def build_context(chunks: list[dict]) -> str:
    lines = []
    for n, c in enumerate(chunks, start=1):
        page = f", p.{c['page']}" if c.get("page") else ""
        lines.append(f"[{n}] ({c['file_name']}{page})\n{c['text']}")
    return "\n".join(lines)


def answer_question(conn, llm, question: str, department: str | None = None,
                    top_k: int = 5, actor: str = "user") -> AskResponse:
    chunks = hybrid_search(conn, llm, question, department, top_k)
    if not chunks:
        audit(conn, "QUERY", json.dumps({"q": question, "chunks": []}), actor=actor)
        return AskResponse(answer=NOT_FOUND, citations=[], grounded=False)

    prompt = PROMPT.format(not_found=NOT_FOUND, context=build_context(chunks), question=question)
    answer = llm.generate_text(prompt)

    # Grounding check: only cite numbers that exist and that the answer used.
    used = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer) if 1 <= int(n) <= len(chunks)})
    grounded = NOT_FOUND not in answer and bool(used)
    citations = [
        Citation(n=n, chunk_id=chunks[n - 1]["chunk_id"], doc_id=chunks[n - 1]["doc_id"],
                 file_name=chunks[n - 1]["file_name"], page=chunks[n - 1]["page"],
                 snippet=chunks[n - 1]["text"][:300])
        for n in used
    ]
    if not grounded:
        answer, citations = NOT_FOUND, []

    audit(conn, "QUERY", json.dumps({"q": question, "chunks": [c.chunk_id for c in citations]}),
          actor=actor)
    return AskResponse(answer=answer, citations=citations, grounded=grounded)
