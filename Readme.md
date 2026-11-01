# MetroMind: Document Intelligence for KMRL

*Smart India Hackathon 2025 · Problem ID 25080 · Kochi Metro Rail Limited*

KMRL receives invoices, safety circulars, tenders and notices every day, in English and Malayalam.
MetroMind takes an uploaded document, routes it to the right department (Level 1), pulls out the
dates, amounts, ids, vendors and actions (Level 2), holds anything risky for a human, and answers
staff questions **only from the documents, with citations**. Every step of every run is traced and
can be replayed in the UI with **Show me how**.

> v3 is a refactor of our hackathon prototype. The hackathon demo classified documents in the browser.
> v3 moves all AI to a layered FastAPI backend and adds the two-level analysis, RAG, tracing and evals.

## Architecture: separate layers, one orchestrator

```
 Ingestion sources                     FastAPI  (api/)
 ┌──────────────────────────────┐      auth: hashed API keys, roles, rate limit
 │ Manual upload        BUILT   │──┐   schema-validated requests
 │ Gmail                planned │  │          │
 │ WhatsApp             planned │  │          ▼
 │ SharePoint / Drive   planned │  └──▶ ORCHESTRATOR (orchestrator/)
 │ (planned = not built)        │      runs the steps in order, owns the run plan
 └──────────────────────────────┘      (max steps, max LLM calls), writes the trace
                                          │ calls one layer per step; layers never call each other
        ┌──────────────────┬──────────────┼───────────────────┬──────────────────┐
        ▼                  ▼              ▼                   ▼                  ▼
   INGESTION          KNOWLEDGE          LLM               ACTIONS            TRACE
   validate upload    sha256 dedupe      OpenAI gpt-6-luna  review gate           runs + run_steps
   extract text       documents/chunks   (or offline rules) action items       → "Show me how"
   redact PII         FTS5 (BM25)        prompts            audit log
   quarantine         vectors (cosine)   L1 / L2 schemas
     injections       RRF fusion         validate + 1 retry
   chunk              dept filter        Decisions API       department routing
   chunk signals                         (dept probabilities)
                                         HyDE, answers,
                                         citation check
```

Only **manual upload** exists today. Gmail, WhatsApp and SharePoint/Drive are shown in the diagram as
planned sources that would feed the same orchestrator; there is no code for them.

### Upload flow (19 planned steps, at most 21 with retries, at most 4 chat calls + 1 Decisions call)

| Layer | Steps |
|---|---|
| api | auth |
| orchestrator | plan_run (the bounded plan shown as "Preliminary analysis") |
| ingestion | upload_validation, extract_text, pii_redaction, injection_scan, chunking, chunk_department_signals |
| knowledge | sha256_dedupe, save_original, index_chunks, save_results |
| llm | embed_chunks, level1_classification, department_decision (Decisions API), level2_extraction (L1/L2 retried once if invalid) |
| actions | department_routing, review_gate, create_action_items |

### Question flow

api auth → orchestrator plan → knowledge department filter → BM25 → llm HyDE → embed → knowledge cosine
→ RRF → llm answer → citation check → actions audit.

## What each feature is

| Feature | How |
|---|---|
| Level 1 (preliminary analysis) | Department(s) with confidence, doc type, urgency, language, L1 summary. One JSON-mode call, Pydantic-validated, one retry |
| Level 2 (KPI extraction) | Dates, amounts, reference ids, vendors, action items, each with a confidence. Input: the L1 result + the chunks |
| Departments | Eight departments, each with what it **owns** and what it is **not**, in `backend/app/departments.py`. The same table feeds the L1 prompt, the Decisions API, the offline rules and the UI ("What each department owns"). Rule: route to the department that must **act** on the document |
| Department routing | Per-chunk keyword signals (local view) vs Level 1 (whole document, decides) vs Decisions API (probability per department, checks). A chunk that disagrees is explained, not obeyed; if the Decisions API disagrees with Level 1 or is under 0.6 sure, the document goes to review |
| Cost | Every LLM step records tokens; each run shows tokens and an estimated USD cost (prices in `config.py`) |
| Review gate | Confidence < 0.6, Critical urgency, department unclear (Decisions API), prompt injection, a failed LLM level, no readable text, or embeddings down → NEEDS_REVIEW |
| Dedupe | SHA-256 of the bytes, enforced by a `UNIQUE` column |
| Privacy | Aadhaar / PAN / phone / email masked before the LLM or the index sees the text |
| Prompt injection | Matching lines are quarantined (never indexed, never sent to the LLM) and the document goes to review |
| Retrieval | BM25 (SQLite FTS5) + vector cosine, fused with Reciprocal Rank Fusion (k = 60); optional HyDE |
| Grounded answers | `[n]` citations, exact refusal "Not found in the documents.", sentence-level citation check |
| Access control | Hashed API keys; admin / reviewer / viewer; viewers pinned to their department **before** retrieval |
| Tracing | Every step stored with layer, timing, input/output, prompt, raw reply, validation, tokens, SQL, scores |
| Evals | L1 accuracy, gate accuracy, L2 precision/recall, hit@k, MRR, answer accuracy, refusal, PII leaks, faithfulness |
| Offline mode | `LLM_PROVIDER=offline`: regex/keyword rules with the same interface, for tests and no-Wi-Fi demos |

## Project layout

```
backend/app/
  main.py, config.py, db.py      app, settings from .env, SQLite schema
  api/          auth.py (keys, roles, rate limit), models.py, routers/ (documents, ask, review, runs)
  orchestrator/ ingest_flow.py, ask_flow.py, tracing.py
  ingestion/    validation.py, extraction.py, redaction.py, injection.py, chunking.py
  knowledge/    store.py (documents, chunks, vectors), retrieval.py (BM25, cosine, RRF, dept filter)
  llm/          providers.py (OpenAI, Offline), prompts.py, schemas.py, structured.py (validate + retry),
                grounding.py (context + citation check)
  actions/      gate.py, tasks.py, audit.py
backend/sample_docs/   demo documents: 3 clean (invoice, safety circular, bogie work order),
                       1 blocked (vendor letter with PII + prompt injection),
                       1 unclear memo (department unsure -> waits for a reviewer)
backend/evals/         labels.jsonl, dataset.jsonl, corpus/ (5 more labelled docs), latest report
backend/tests/         pytest: core, API end to end, layer rule, department routing + review
frontend/src/          api.js + Upload, Documents, Ask, Review & Audit, Evals, ShowMeHow (drawer)
docs/                  DEMO_SCRIPT.md, WALKTHROUGH.md, RAG_DESIGN.md, SECURITY.md, TEST_REPORT.md
```

## Run it

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # put your OPENAI_API_KEY in .env (or set LLM_PROVIDER=offline)
python -m scripts.seed_demo     # prints an admin key and a Finance viewer key
uvicorn app.main:app --reload   # http://localhost:8000  (Swagger at /docs)

# Frontend (second terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173, paste the admin key top right

# Tests and evals
cd backend
python -m pytest -q
python -m scripts.run_evals --answers     # writes evals/report_<provider>.md, shown in the Evals tab
```

Switching provider (offline ↔ openai) or chunking strategy after documents are loaded: delete
`metromind.db` and `uploads/`, then seed again. Vectors from different embedding models can't be compared.

## Honest limits

- Demo scale: SQLite and a numpy vector scan. Production would be Postgres + pgvector and a job queue.
- API keys, not SSO. Rate limiter is in memory.
- Regex PII and injection checks catch common patterns, not everything.
- The committed eval numbers are from the offline rules on a small set written alongside them;
  re-run with your OpenAI key to get model numbers.

## Team

Built for SIH 2025 by our team. v2/v3 refactor by Venkat Phaneendra Nittala.
