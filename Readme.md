# MetroMind: Document Intelligence for KMRL

*Smart India Hackathon 2025 · Problem ID 25080 · Kochi Metro Rail Limited*

KMRL receives a flood of emails, scanned circulars, invoices and tenders every day, in English and Malayalam.
MetroMind ingests them, routes each one to the right department with a summary and action items,
and lets staff ask questions that are answered **only from the documents, with citations**.

> v2.0 is a refactor of our hackathon prototype. The hackathon demo did classification in the browser;
> v2 moves all AI to a FastAPI backend and adds the retrieval (RAG) layer we had designed.

## What it does

| Feature | How |
|---|---|
| Ingest from upload or Gmail | FastAPI endpoint + Gmail API (OAuth2 with `state`, verified id_token) |
| No duplicate processing | SHA-256 of the file bytes, enforced by a `UNIQUE` column |
| Text extraction | pypdf for digital PDFs; Tesseract OCR (eng+hin+mal) for images |
| Privacy | Aadhaar / PAN / phone / email masked before anything reaches the LLM or the index |
| Classify, summarise, extract actions | **One** LLM call in JSON mode, validated by Pydantic, one retry, review fallback |
| Chunking | Three strategies: `fixed`, `recursive` (default), `sentence` window |
| Retrieval | **Hybrid**: BM25 (SQLite FTS5) + vector cosine, merged with Reciprocal Rank Fusion |
| HyDE | Embed a hypothetical answer passage for the vector search (toggle per question) |
| Grounded answers | `[n]` citations, exact refusal "Not found in the documents.", **citation check** with a faithfulness score |
| Security | Hashed API keys with admin / reviewer / viewer roles, department filter before retrieval, rate limit, magic-byte upload checks, prompt-injection quarantine, audit log |
| Human-in-the-loop | Confidence < 0.6, Critical urgency or injection flag → review queue |
| Evals | 23-question dataset; hit@k, MRR, answer accuracy, refusal, faithfulness, latency across chunkers and retrieval modes |
| Works offline | `LLM_PROVIDER=offline`: keyword classifier, hashed embeddings, extractive answers |

Deeper notes: [docs/RAG_DESIGN.md](docs/RAG_DESIGN.md) · [docs/SECURITY.md](docs/SECURITY.md) · [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md)

## Architecture

```
React (Vite) --HTTP + X-API-Key--> FastAPI
                        |-- /documents  upload -> validate -> ingestion pipeline
                        |      sha256 dedupe -> extract -> redact PII -> injection scan -> chunk -> embed
                        |      -> LLM analysis (JSON) -> Pydantic validation -> departments, actions
                        |-- /ask        [HyDE] -> hybrid retrieval (BM25 + vector, RRF) -> grounded answer
                        |               -> citation check -> faithfulness score
                        |-- /documents/{id}/review   human approval / correction
                        |-- /audit      audit trail
                        |-- /gmail      OAuth connect + sync attachments into the same pipeline
                     SQLite: documents, chunks (+FTS5), departments, document_departments,
                             action_items, audit_log, api_keys, gmail_accounts
                     LLM: Gemini 2.5 Flash + gemini-embedding-001 (server-side key only)
```

Production path: SQLite -> Postgres with pgvector (HNSW index), a job queue for ingestion, SSO + JWT.

## Project layout

```
backend/
  app/
    main.py              FastAPI app, CORS, security headers, routers
    config.py            all settings from environment variables
    db.py                schema + connection helpers + audit()
    schemas.py           Pydantic models (LLM contract + API)
    security.py          API keys, roles, rate limit, upload checks, PII redaction, injection scan
    services/
      extraction.py      file -> pages of text
      chunking.py        fixed / recursive / sentence-window chunkers
      llm.py             GeminiProvider / OfflineProvider
      analysis.py        one structured LLM call + validation + retry
      ingestion.py       the full pipeline for one file
      retrieval.py       BM25, vector, RRF, HyDE
      rag.py             grounded answer + citation check
      gmail.py           Gmail OAuth + attachment sync
    routers/             documents, ask, review, gmail
  evals/dataset.jsonl    eval questions; report_offline.md is the baseline
  scripts/               seed_demo, create_api_key, run_evals
  tests/                 22 pytest tests (core logic, security, end-to-end API)
  sample_docs/           7 KMRL-style documents
frontend/
  src/api.js             the only place that talks to the backend
  src/components/        UploadPanel, DocumentList, AskPanel, ReviewPanel
```

## Run it

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # add GEMINI_API_KEY, or set LLM_PROVIDER=offline
python -m scripts.seed_demo       # loads samples, prints an admin key and a Finance viewer key
uvicorn app.main:app --reload     # API on http://localhost:8000, docs at /docs

# Frontend (new terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173, paste the admin key top right

# Tests and evals
cd backend
python -m pytest -q
python -m scripts.run_evals --answers
```

If you change `LLM_PROVIDER` or `CHUNK_STRATEGY` after seeding, delete `metromind.db` and `uploads/` and seed again:
embeddings from different providers can't be compared, and old chunks keep the old strategy.

## Team

Built for SIH 2025 by our team. v2 refactor by Venkat Phaneendra Nittala.
