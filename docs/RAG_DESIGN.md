# RAG design: chunking, retrieval, HyDE, citations, evals

Every choice below is one small file and one `.env` switch, so you can change it on the spot.

## Pipeline

```
INGEST   file -> validate -> sha256 dedupe -> extract pages -> redact PII -> quarantine injections
              -> chunk (fixed | recursive | sentence) -> embed -> SQLite (+ FTS5)
              -> Level 1 call -> Level 2 call (each Pydantic-validated, 1 retry) -> review gate

ASK      question -> department filter (from the API key's role)
              -> keyword search (BM25)  ┐
              -> vector search (cosine) ┘-> Reciprocal Rank Fusion -> top k chunks
                     ^ HyDE: embed a hypothetical answer instead of the bare question
              -> grounded prompt (numbered chunks, "documents are data")
              -> answer with [n] -> citation check -> faithfulness score -> audit log
```

## 1. Chunking strategies (`ingestion/chunking.py`, `CHUNK_STRATEGY`)

| Strategy | How | Good at | Weak at |
|---|---|---|---|
| `fixed` | 200-word windows, 40-word overlap | Simple baseline, predictable size | Cuts mid-sentence; overlap patches it |
| `recursive` (default) | Split at blank lines, then lines, then sentences, only as far as needed; pack pieces up to 200 words; keep line breaks | Keeps paragraphs and clauses whole; headings stay separate | Chunk sizes vary |
| `sentence` | 3 sentences per chunk plus 1 neighbouring sentence each side | Precise matches for fact questions | Many small chunks; less context each |

Each chunk stores its page number, so citations say "file, p.3".
Overlap matters because a sentence cut at a boundary still appears whole in the neighbouring chunk.
Changing the strategy only affects newly ingested documents: delete `metromind.db` and re-seed.

## 2. Retrieval (`knowledge/retrieval.py`)

- **Keyword:** SQLite FTS5 with `bm25()` ranking. Catches exact tokens: `INV-2025-0917`, `T-219`, `CMRS`.
- **Vector:** embeddings (OpenAI `text-embedding-3-small`, 1536-dim, normalised; offline: 768-dim hashed bag of words) and a numpy dot product, which equals cosine similarity for normalised vectors.
- **Hybrid:** each returns its top 20; **RRF** merges them with `score = Σ 1/(60 + rank)`. It uses ranks only, so BM25 and cosine scales never need normalising.
- **Department filter before ranking:** a Finance viewer's query never even scores Safety chunks.
- **Flagged chunks** (possible prompt injection) are excluded from both searches.

## 3. HyDE (`orchestrator/ask_flow.py: search()`, `USE_HYDE` or `use_hyde` per request)

Questions are short ("bid deadline for cameras?"); documents are long and formal. Their embeddings sit in different places.
HyDE asks the LLM to write a *hypothetical* KMRL passage answering the question, then embeds **question + passage**
and searches with that. The passage is never shown and never used as an answer; it only steers the vector search.
Keyword search still uses the real question, so HyDE can't break exact-match lookups.
Cost: one extra LLM call per question. Turn it off for latency-sensitive use.

## 4. Grounded answers and citation check (`llm/grounding.py`)

- The prompt numbers chunks `[1]..[k]`, requires `[n]` after every sentence, and has one exact refusal:
  "Not found in the documents."
- Chunks sit inside `<documents>` tags and the prompt says they are data, not instructions.
- **Citation check (no extra LLM call):** split the answer into sentences; a sentence is *supported* when at
  least 50% of its content words appear in the chunk(s) it cites. `faithfulness = supported / all sentences`.
  Each citation in the response carries `supported: true/false`; the UI shows "verified" or "weak support".
- Unsupported sentences are removed from the answer; if none are supported, or fewer than half (`MIN_FAITHFULNESS = 0.5` in `orchestrator/ask_flow.py`), we return the refusal instead.

## 5. Evals (`scripts/run_evals.py`)

Inputs: `evals/labels.jsonl` (gold department, gate status and Level 2 entities for 8 documents: the 3 demo
documents + 5 in `evals/corpus/`) and `evals/dataset.jsonl` (25 questions: 21 with an expected document and
answer keywords, 4 that must be refused, one of which asks for a masked Aadhaar number).

| Metric | Meaning |
|---|---|
| L1 accuracy | primary department == gold |
| gate accuracy | ANALYZED / NEEDS_REVIEW == gold (demo documents) |
| L2 precision / recall | extracted values matching a gold value / gold values that were extracted, per entity type |
| hit@1, hit@k, MRR | the expected document's rank among retrieved chunks |
| answer accuracy | answer contains every expected keyword |
| refusal | unanswerable questions answered "Not found in the documents." |
| PII leaks | answers containing a raw PII string (must be 0) |
| faithfulness | average citation-check score |

```bash
python -m scripts.run_evals              # classification + retrieval
python -m scripts.run_evals --answers    # + answers (LLM calls)
```
Writes `evals/report_<provider>.md` and `evals/latest_<provider>.json` (the Evals tab shows the newest).

**Read the committed numbers honestly.** They come from the offline rules, which were written alongside
this small labelled set, so L1/L2 scores near 1.0 prove the harness works, not that the approach generalises.
Run it with `LLM_PROVIDER=openai` to get OpenAI (gpt-6-luna) numbers, and grow the labelled set before quoting any.

## Next steps (not built, on purpose)

- Cross-encoder re-ranking of the fused top 20 (better precision, adds a model)
- Multi-query rewriting / query decomposition for compound questions
- LLM-as-judge faithfulness to complement the word-overlap check
- Postgres + pgvector HNSW once the corpus outgrows a numpy scan
