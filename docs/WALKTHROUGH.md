# MetroMind v3: Walkthrough and Defence Guide

The demo itself is in `DEMO_SCRIPT.md`. This file is for "walk me through the code" and the questions after.

## 1. What changed from the hackathon version, and why

| Hackathon | v3 | Why |
|---|---|---|
| LLM called from the browser with a hard-coded key | All LLM calls on the server; key in `.env` | The key was public |
| Four chained prompts, JSON scraped with a regex | Two levels, each one JSON-mode call + Pydantic + one retry | Fewer calls, validated output, bounded cost |
| No retrieval | BM25 + vector + RRF, HyDE, cited answers, citation check | Answers come only from the documents |
| One big pipeline file | Layers: api, orchestrator, ingestion, knowledge, llm, actions | Each part testable and swappable; a test enforces no sideways imports |
| No visibility | Every step traced; "Show me how" drawer | You can see what happened and why |
| No tests or evals | pytest (offline) + eval harness | Deterministic thanks to the offline provider |

## 2. Trace one upload through the code

`api/routers/documents.py: upload()` (role admin/reviewer) → `orchestrator/ingest_flow.py: process_upload()`
1. `auth` and `plan_run`: the plan (`RUN_PLAN`) is fixed: 16 steps, max 18, max 4 LLM calls, 1 retry per level
2. `ingestion/validation.py: validate_upload()` → rejected files raise `UploadRejected`; the trace is still saved
3. `sha256_bytes()` + `knowledge/store.find_by_sha256()` → a HIT ends the run as DUPLICATE
4. `store.save_original()` → `ingestion/extraction.extract_pages()` (fewer than 5 words → review)
5. `ingestion/redaction.redact_pages()` → `ingestion/injection.quarantine_injections()` → `ingestion/chunking.chunk_pages()`
6. `llm.embed()` (failure → keep text, keyword search only) → `store.add_chunks()` (a trigger fills FTS5)
7. `llm/structured.level1()` → `level2()`: each `run_level()` builds the prompt, calls the provider in JSON mode,
   `json.loads` + `model_validate`, retries once with the error, then raises `LevelFailed`
8. `actions/gate.review_gate()` → `actions/tasks.create_action_items()` → `store.save_analysis()` → audit
9. `tracer.save()` writes `runs` + `run_steps`

## 3. Trace one question

`api/routers/ask.py` (auth, `allowed_department()` pins viewers, schema check) → `orchestrator/ask_flow.py`
→ `knowledge/retrieval`: `docs_in_department()`, `keyword_search()` (FTS5 `bm25()`), then `llm`: HyDE passage
and `embed()`, then `vector_search()` (numpy dot product = cosine), `reciprocal_rank_fusion()` → `llm`: answer
with `ANSWER_PROMPT`, `grounding.check_citations()` → audit.

## 4. Likely questions

**Why two levels instead of one call?** Level 1 is cheap and decides routing and urgency; it's the preliminary
analysis a person sees first. Level 2 needs that context (it's told the document type) and works on the chunks,
so extraction is focused. Two calls, each bounded and validated.

**What stops it looping or burning money?** The plan is fixed before the run: at most 4 chat calls for an
upload (2 levels × 1 retry), 2 for a question. There's no agent loop.

**What happens when the model returns bad JSON?** JSON mode makes it parse; Pydantic checks the shape and values
(known departments, confidence 0 to 1, allowed urgency). On failure we retry once and tell the model the exact
error. Second failure → NEEDS_REVIEW. The trace shows both attempts and the errors.

**How do you stop prompt injection?** Lines that look like instructions are removed before chunking, so the
model never sees them and they're never retrieved. The document goes to review. Every prompt also says
documents are data. And the model can't act: it only returns JSON or text.

**Where does PII go?** It's masked before chunking, so it isn't in the index, the prompts, or the traces.
The original file is kept on disk for traceability, behind the API's role checks.

**What is HyDE and when does it hurt?** The model writes a hypothetical answer passage; we embed question +
passage for the vector search. It helps short questions match formal documents. It costs a call and can drift,
so BM25 still uses the real question and RRF balances the two.

**How does the citation check work?** For each answer sentence, the share of its content words found in the
chunk it cites; 50% or more means supported. No supported sentence → we refuse. Weakness: paraphrase.

**Why layers?** Ingestion, knowledge, LLM and actions change for different reasons. The orchestrator is the
only place that knows the order. `tests/test_layers.py` fails if one layer imports another.

**Why SQLite?** Right size for a laptop demo. Production: Postgres + pgvector (HNSW), same tables.

**What do the evals show?** Name the provider. Offline numbers come from rules written alongside the set,
so they test the harness. With OpenAI, quote what it produced, and say the set is small.

**Where are Gmail and WhatsApp?** Not built. They'd be new sources calling the same `process_upload()`.

## 5. Change it live

| Ask | Change |
|---|---|
| Different model | `.env` `OPENAI_MODEL=` |
| Offline / online | `.env` `LLM_PROVIDER=offline` or `openai` (then delete `metromind.db` + `uploads/`, re-seed) |
| Chunking | `.env` `CHUNK_STRATEGY=fixed|recursive|sentence`, `CHUNK_SIZE_WORDS`, `CHUNK_OVERLAP_WORDS` |
| HyDE default | `.env` `USE_HYDE=false`, or untick it in the Ask tab |
| Review threshold | `.env` `REVIEW_CONFIDENCE_THRESHOLD=0.8` |
| Another review rule | one `if` in `actions/gate.py` |
| More retries | `MAX_RETRIES` in `llm/structured.py` (the run plan updates itself) |
| New PII type | one regex in `ingestion/redaction.py` |
| New injection phrase | one alternative in `ingestion/injection.py` |
| Stricter citations | `SUPPORT_THRESHOLD` in `llm/grounding.py` |
| New Level 2 field | add it to `Level2Result` in `llm/schemas.py` and to `LEVEL2_PROMPT` in `llm/prompts.py` |
| New user | `python -m scripts.create_api_key --name x --role viewer --department HR` |
| New eval question | one JSON line in `evals/dataset.jsonl` |

After any change: `python -m pytest -q`.

## 6. Be honest about these

- The hackathon version had no RAG; v3 adds it.
- No production deployment, no real users, no measured time savings.
- The committed eval numbers are offline; quote OpenAI numbers only after running them.
- API keys, not SSO; in-memory rate limit; regex-based PII and injection checks.
