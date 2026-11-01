# MetroMind: 2-hour interview prep (Capgemini, Mon 2 Nov 2026)

Everything here was run live against OpenAI on 1 Nov 2026 (gpt-6-luna + text-embedding-3-small + Decisions API).

## The 2-hour plan

| Time | Do this |
|---|---|
| 0:00-0:15 | Fresh start on your laptop: delete `backend/metromind.db`, `python -m scripts.seed_demo`, start backend + frontend, paste admin key. Check the header says `openai · gpt-6-luna`. |
| 0:15-0:45 | Run the demo script (docs/DEMO_SCRIPT.md) out loud twice, with a timer. Target 7 minutes. |
| 0:45-1:15 | Open these files and say what each does in one sentence: `orchestrator/ingest_flow.py`, `departments.py`, `actions/routing.py`, `llm/decisions.py`, `ingestion/redaction.py`, `ingestion/injection.py`, `knowledge/retrieval.py`, `llm/grounding.py`, `actions/gate.py`. |
| 1:15-1:50 | Cross-questions below: cover the answer, say yours, then check. |
| 1:50-2:00 | Run `python -m pytest -q` (51 pass) and leave the app open on the Upload tab. |

## 60-second pitch

"KMRL gets hundreds of documents a day: invoices, safety circulars, work orders, tenders, in English and
Malayalam. Each one has to reach the right department, and nobody should act on it blindly. MetroMind takes a
manual upload, masks personal data, quarantines prompt-injection lines, then classifies the document (Level 1),
extracts dates, amounts and references (Level 2), and routes it to a department. A cheap second model call gives
a real probability for every department; if it disagrees, a human reviews. You can ask questions and get answers
with citations or an honest 'Not found'. Every step is traced, and 'Show me how' opens the exact prompt, scores
and cost for any run. A document costs about $0.0005."

## Live numbers (gpt-6-luna, 1 Nov 2026)

- End to end: **30 / 30** API checks pass. UI click-through and layout checks at 1366×768, 1280×720, 1920×1080: see TEST_REPORT.md.
- Evals on 9 labelled documents, 27 questions (4 must be refused): Level 1 department accuracy **1.0**, gate accuracy **1.0**,
  Level 2 precision **0.84** / recall **0.98**, hybrid retrieval hit@1 **1.0**, answer accuracy **0.96** (1.0 with HyDE),
  refusal **1.0**, PII leaks **0**.
- Boundary documents (written to tempt the wrong department): fire-extinguisher tender → Procurement, extinguisher refill invoice → Finance,
  leave rules for station staff → HR, CMRS-ordered evacuation drill → Safety. All correct; Decisions API 0.97-1.00 sure.
- Cost: invoice upload 2,170 tokens in / 645 out ≈ **$0.0005**. The Decisions call is ~$0.0001 (output is free).
- Say this honestly: "9 documents is a small set. It proves the harness and catches regressions. It is not a benchmark."

## The routing story (your strongest 60 seconds)

1. **Definitions.** `departments.py`: 8 departments, each with what it *owns* and what it is *not*. One table feeds the prompt, the Decisions API, the offline rules and the UI.
2. **Rule.** Route to the department that must **act** on the document, not the one whose words appear most.
3. **Three pieces of evidence:**
   - chunk signals (ingestion, no LLM): keyword vote per chunk. Local view.
   - Level 1 (LLM): reads the whole document + definitions. **Decides.**
   - Decisions API: probability for every department. **Checks.**
4. **The trap.** The bogie overhaul work order: chunk #2 is the cost table (invoice x3, payment x4, GST), so it *looks like* Finance. The document is a repair order, so it goes to Maintenance. The drawer shows this in an amber box with the reason.
5. **Safety net.** If the Decisions API picks another department, or is under 0.6 sure, the document goes to review.
6. **Access follows the document.** A Finance viewer can't retrieve the work order, even though one chunk talks about money.

## Cross-questions and answers

**Architecture**

- *Why not LangChain / LlamaIndex?* Every step here is 20-80 lines I can show. A framework would hide the prompt, the retry and the retrieval scores, and those are what I need to defend and debug. I'd adopt one when the team needs its integrations.
- *Why layers?* `api → orchestrator → ingestion / knowledge / llm / actions`. The orchestrator is the only place that knows the order. Layers never import each other; `tests/test_layers.py` fails the build if they do. I can swap SQLite for Postgres inside `knowledge/` without touching anything else.
- *Why is the plan fixed in advance?* So a run can't loop or burn money: 19 steps, at most 21 with retries, at most 4 chat calls + 1 Decisions call. It's shown as the run plan before the steps.
- *What happens if OpenAI is down?* Embedding failure: the document is still stored and keyword search still works; it goes to review. Level 1/2 failure: retried once, then review. Decisions failure: the second opinion is a safety check, so the document goes to a reviewer (pending department) and the step shows "failed". Nothing is lost.
- *Why SQLite?* One file, FTS5 for BM25 built in, zero setup for a demo. For production: Postgres + pgvector, a job queue for uploads, object storage for files.

**LLM choices**

- *Why gpt-6-luna?* It's OpenAI's current small model, and the cheapest one listed ($0.10 per 1M input tokens, $0.50 output). gpt-4o-mini is now marked deprecated. The model is one `.env` line.
- *What's the Decisions API and why use it?* `POST /v1/decisions` returns typed answers: a choice from a fixed list with a probability for each option. Level 1's "confidence" is a number the model *writes* in its JSON, often 1.0. The Decisions API gives a distribution I can put a threshold on. Output tokens are free, so it's about $0.0001 per document.
- *Why not use Decisions for everything?* It answers fixed-choice, score or yes/no questions. It can't write a summary or extract amounts, so Level 1 and Level 2 stay as JSON calls.
- *How do you stop bad JSON?* JSON mode, then Pydantic validation, then one retry with the validation error in the prompt. If it still fails, review.
- *Why `reasoning_effort: low`?* gpt-6 models only allow the default temperature; low effort keeps the hidden thinking short, so it stays fast and cheap.
- *How did you write the urgency scale?* It's in the prompt: Critical = danger now, act within 24 hours; High = within 7 days or after an incident; Medium = within 30 days; Low = information. Before I added it, the model called a 48-hour inspection "Critical" and the gate held it. Now it's High and the test is stable.

**RAG**

- *Chunking?* Recursive: split on sections, then paragraphs, then sentences, 200 words with 40 words of overlap. Fixed and sentence chunking are one `.env` switch.
- *Why hybrid search?* BM25 nails exact tokens like "INV-2025-0917"; vectors catch paraphrases. Reciprocal Rank Fusion (k = 60) merges the two lists by rank, so I don't have to normalise different score scales.
- *What is HyDE?* The model writes a fake answer passage; I embed question + passage. It helps vague questions; it costs one extra call (latency 1.4 s → 3.1 s here). It's on by default and one `.env` switch (`USE_HYDE`).
- *How do you know an answer is grounded?* Every sentence must cite `[n]`; `citation_check` measures word overlap between each sentence and the chunk it cites. Unsupported sentences are removed; if fewer than half are supported, we refuse. If nothing relevant is retrieved, the exact answer is "Not found in the documents."

**Security**

- *PII?* Aadhaar, PAN, phone, email are masked with regexes **before** chunking, indexing, the LLM and the trace. The original file is unmasked, so only admins and reviewers can download it; viewers only ever see masked chunks.
- *Prompt injection?* Lines like "ignore all previous instructions" are quarantined at ingestion: never indexed, never sent to the model, and the document goes to review. Questions are also answered only from retrieved chunks with a fixed refusal.
- *Is regex enough?* No. It's a first line. Next: a classifier (the Decisions API's predicate question fits), and treating every document as untrusted data in the prompt, which I already do.
- *Access control?* Hashed API keys, roles admin/reviewer/viewer. A viewer is pinned to their department **before** retrieval, so other departments' chunks are never even scored. Wrong department → 403.
- *Where's the key?* Only in `backend/.env`, which is git-ignored. The frontend never sees it.

**Testing**

- *How did you test?* 51 pytest tests (offline, deterministic), 30 live end-to-end API checks, a headless-Chrome click-through, a layout check for overflow at three laptop sizes, and evals with labelled data.
- *What failed along the way?* With gpt-4o-mini and no definitions, the contract amendment went to Procurement. It's correct after I added department definitions with "not" boundaries; and the safety circular was held as Critical until I added the urgency scale.
- *Why does offline mode score 1.0?* The offline rules were written alongside this small set, so they prove the harness, not intelligence. I only quote the OpenAI numbers.

**Scale and next steps**

- *1,000 documents a day?* About $0.50 a day in model cost at today's numbers. Add a job queue, batch embeddings, Postgres + pgvector, and prompt caching for the shared prefix (department definitions).
- *Malayalam?* The model reads it and Level 1 reports the language. Retrieval for Malayalam needs a multilingual embedding check and more labelled data. I'd say that plainly.
- *What would you build next?* A second source (email) into the same orchestrator, SSO, a reviewer queue with SLAs, and a bigger labelled set from real KMRL documents.

## If something breaks during the demo

- Header shows `offline`: the key isn't loaded. Check `backend/.env`, restart the backend.
- 401 everywhere: paste the admin key again (top right).
- A document says NEEDS_REVIEW unexpectedly: open Show me how → `review_gate`. The reason is there, and that *is* the feature.
- No internet: set `LLM_PROVIDER=offline`; the whole demo runs on rules. Say so.
