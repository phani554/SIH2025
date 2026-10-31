# RAG design: chunking, retrieval, HyDE, citations, evals

Every choice below is one small file and one `.env` switch, so you can change it on the spot.

## Pipeline

```
INGEST   file -> sha256 dedupe -> extract pages -> redact PII -> injection scan
              -> chunk (fixed | recursive | sentence) -> embed -> SQLite (+ FTS5)
              -> one LLM call -> Pydantic validation -> departments, action items, status

ASK      question -> department filter (from the API key's role)
              -> keyword search (BM25)  ┐
              -> vector search (cosine) ┘-> Reciprocal Rank Fusion -> top k chunks
                     ^ HyDE: embed a hypothetical answer instead of the bare question
              -> grounded prompt (numbered chunks, "documents are data")
              -> answer with [n] -> citation check -> faithfulness score -> audit log
```

## 1. Chunking strategies (`services/chunking.py`, `CHUNK_STRATEGY`)

| Strategy | How | Good at | Weak at |
|---|---|---|---|
| `fixed` | 200-word windows, 40-word overlap | Simple baseline, predictable size | Cuts mid-sentence; overlap patches it |
| `recursive` (default) | Split at blank lines, then lines, then sentences, only as far as needed; pack pieces up to 200 words; keep line breaks | Keeps paragraphs and clauses whole; headings stay separate | Chunk sizes vary |
| `sentence` | 3 sentences per chunk plus 1 neighbouring sentence each side | Precise matches for fact questions | Many small chunks; less context each |

Each chunk stores its page number, so citations say "file, p.3".
Overlap matters because a sentence cut at a boundary still appears whole in the neighbouring chunk.
Changing the strategy only affects newly ingested documents: delete `metromind.db` and re-seed.

## 2. Retrieval (`services/retrieval.py`)

- **Keyword:** SQLite FTS5 with `bm25()` ranking. Catches exact tokens: `INV-2025-0917`, `T-219`, `CMRS`.
- **Vector:** embeddings (Gemini `gemini-embedding-001`, 768-dim, normalised) and a numpy dot product, which equals cosine similarity for normalised vectors.
- **Hybrid:** each returns its top 20; **RRF** merges them with `score = Σ 1/(60 + rank)`. It uses ranks only, so BM25 and cosine scales never need normalising.
- **Department filter before ranking:** a Finance viewer's query never even scores Safety chunks.
- **Flagged chunks** (possible prompt injection) are excluded from both searches.

## 3. HyDE (`query_vector()` in retrieval.py, `USE_HYDE` or `use_hyde` per request)

Questions are short ("bid deadline for cameras?"); documents are long and formal. Their embeddings sit in different places.
HyDE asks the LLM to write a *hypothetical* KMRL passage answering the question, then embeds **question + passage**
and searches with that. The passage is never shown and never used as an answer; it only steers the vector search.
Keyword search still uses the real question, so HyDE can't break exact-match lookups.
Cost: one extra LLM call per question. Turn it off for latency-sensitive use.

## 4. Grounded answers and citation check (`services/rag.py`)

- The prompt numbers chunks `[1]..[k]`, requires `[n]` after every sentence, and has one exact refusal:
  "Not found in the documents."
- Chunks sit inside `<documents>` tags and the prompt says they are data, not instructions.
- **Citation check (no extra LLM call):** split the answer into sentences; a sentence is *supported* when at
  least 50% of its content words appear in the chunk(s) it cites. `faithfulness = supported / all sentences`.
  Each citation in the response carries `supported: true/false`; the UI shows "verified" or "weak support".
- No valid citation → we return the refusal instead of an ungrounded answer.

## 5. Evals (`scripts/run_evals.py`, `evals/dataset.jsonl`)

23 questions over the 7 sample documents: 20 answerable (with the expected document and expected answer
keywords) and 3 that must be refused.

| Metric | Meaning |
|---|---|
| hit@1, hit@k | Expected document is in the top 1 / top k chunks |
| MRR | Mean of 1/rank of the first chunk from the expected document |
| accuracy | Answer contains every expected keyword |
| refusal | Unanswerable questions answered "Not found in the documents." |
| faithfulness | Average citation-check score on answerable questions |
| latency | Seconds per question |

```bash
python -m scripts.run_evals                                   # retrieval: 3 chunkers x 4 modes
python -m scripts.run_evals --answers --strategies recursive  # + answers (LLM calls)
```
Writes `evals/report_<provider>.md`. `report_offline.md` is the committed baseline.

**Reading the baseline honestly:** with 7 short documents, keyword search already finds the right document,
so retrieval numbers are near the ceiling. The offline "LLM" is extractive, so its answer accuracy (0.60 to 0.70) is
the floor that Gemini should beat. To make the evals discriminate, add longer, overlapping documents and
paraphrased questions to the dataset. That's the first thing to grow.

## Next steps (not built, on purpose)

- Cross-encoder re-ranking of the fused top 20 (better precision, adds a model)
- Multi-query rewriting / query decomposition for compound questions
- LLM-as-judge faithfulness to complement the word-overlap check
- Postgres + pgvector HNSW once the corpus outgrows a numpy scan
