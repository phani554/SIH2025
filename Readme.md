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
| Ingest from upload or Gmail | FastAPI endpoint + Gmail API (OAuth2, offline refresh token) |
| No duplicate processing | SHA-256 of the file bytes, enforced by a `UNIQUE` column |
| Text extraction | pypdf for digital PDFs; Tesseract OCR (eng+hin+mal) for images |
| Classify, summarise, extract actions | **One** LLM call in JSON mode, validated by a Pydantic schema, one retry on failure |
| Human-in-the-loop | Confidence below 0.6 or "Critical" urgency → review queue |
| Ask questions (RAG) | Chunk (200 words, 40 overlap) → embed → **hybrid search: BM25 (SQLite FTS5) + vector cosine, merged with Reciprocal Rank Fusion** → grounded prompt → answer with `[n]` citations |
| Department-level access | Department filter applied **before** retrieval |
| Traceability | Every citation links to the chunk, page and original file; every action is in `audit_log` |
| Works offline | `LLM_PROVIDER=offline` swaps Gemini for a keyword classifier + hashed embeddings |

## Architecture

```
React (Vite) ──HTTP──> FastAPI
                        ├── /documents  upload → ingestion pipeline
                        │      sha256 dedupe → extract → chunk → embed → store
                        │      → LLM analysis (JSON) → Pydantic validation → departments, actions
                        ├── /ask        hybrid retrieval (BM25 + vector, RRF) → grounded answer + citations
                        ├── /documents/{id}/review   human approval / correction
                        ├── /audit      audit trail
                        └── /gmail      OAuth connect + sync attachments into the same pipeline
                     SQLite: documents, chunks (+FTS5), departments, document_departments,
                             action_items, audit_log, gmail_accounts
                     LLM: Gemini 2.5 Flash + gemini-embedding-001 (server-side key only)
```

Production path: SQLite → Postgres with pgvector (HNSW index), a job queue for ingestion, JWT + roles.

## Project layout

```
backend/
  app/
    main.py              FastAPI app, CORS, routers
    config.py            all settings from environment variables
    db.py                schema + connection helpers + audit()
    schemas.py           Pydantic models (LLM contract + API)
    services/
      extraction.py      file → pages of text
      chunking.py        overlapping word windows
      llm.py             GeminiProvider / OfflineProvider
      analysis.py        one structured LLM call + validation + retry
      ingestion.py       the full pipeline for one file
      retrieval.py       BM25, vector search, RRF
      rag.py             grounded answer with citations
      gmail.py           Gmail OAuth + attachment sync
    routers/             documents, ask, review, gmail
  tests/                 pytest: chunking, RRF, schema, end-to-end API
  sample_docs/           5 KMRL-style documents for the demo
  scripts/seed_demo.py   loads the samples
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
python -m scripts.seed_demo       # optional: load sample documents
uvicorn app.main:app --reload     # API on http://localhost:8000, docs at /docs

# Frontend (new terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173

# Tests (always offline)
cd backend && python -m pytest -q
```

If you switch provider after seeding, delete `metromind.db` and the `uploads/` folder and seed again:
embeddings from different providers can't be compared.

## Team

Built for SIH 2025 by our team. v2 refactor by Venkat Phaneendra Nittala.
