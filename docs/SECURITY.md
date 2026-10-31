# Security (basic, and every control is visible in the trace)

| Threat | Control | Code | Trace step |
|---|---|---|---|
| Leaked LLM key | Key only in `backend/.env`, sent in the `Authorization` header from the server; the browser never calls the LLM | `config.py`, `llm/providers.py` | (none: nothing to show) |
| Anyone can call the API | `X-API-Key` on every request; only the SHA-256 of each key is stored; keys shown once | `api/auth.py`, `scripts/create_api_key.py` | `auth` (api) |
| Over-broad access | Roles: admin (all), reviewer (all departments, approve, audit), viewer (own department only) | `require_role()` | `auth` |
| Cross-department leaks through RAG | Viewer's department comes from their key, and the filter runs **before** retrieval | `allowed_department()`, `knowledge/retrieval.docs_in_department()` | `department_filter` (knowledge) |
| Abuse / cost | 120 requests per minute per key (set in .env), sliding window | `check_rate_limit()` | `auth` detail shows "n of 120 this minute" |
| Malicious or junk uploads | 15 MB limit, empty-file check, extension allowlist, magic bytes (`.pdf` must start with `%PDF`), safe file names | `ingestion/validation.py` | `upload_validation` (rejected uploads are traced too) |
| Duplicate processing | SHA-256 of the bytes, `UNIQUE` column; no LLM spend on a duplicate | `ingestion/validation.sha256_bytes`, `knowledge/store.find_by_sha256` | `sha256_dedupe` |
| Personal data sent to the LLM or stored | Aadhaar, PAN, phone, email masked before chunking, embedding and analysis | `ingestion/redaction.py` | `pii_redaction` (counts + preview after masking) |
| Prompt injection inside documents | Lines matching injection patterns are quarantined (removed before chunking), the document goes to review, and every prompt says documents are data | `ingestion/injection.py`, `llm/prompts.py` | `injection_scan` (the exact line and phrase), `review_gate` |
| Bad LLM output | JSON mode + Pydantic schema; one retry with the error; still bad → review queue | `llm/structured.py`, `llm/schemas.py` | `level1_classification (attempt n)` with validation errors |
| Ungrounded answers | Citation check per sentence; no supported citation → "Not found in the documents." | `llm/grounding.py` | `citation_check` (per-sentence table) |
| No accountability | Audit log (INGEST, DUPLICATE, REDACT, INJECTION_FLAG, ANALYZE, QUERY, REVIEW, DELETE) + full run traces | `actions/audit.py`, `orchestrator/tracing.py` | `audit_query` |
| Server details leaking | No server paths in responses; `nosniff`, `X-Frame-Options: DENY`, `no-referrer`; CORS limited to the frontend origin | `api/routers/documents.py`, `main.py` | (none) |

## Known gaps (say these before they ask)

- Rate limiter is in memory: it resets on restart and doesn't work across several servers (use Redis).
- Regex PII and injection detection catch common patterns, not everything. It's one layer of several.
- API keys suit a demo. Staff would log in with SSO and short-lived JWTs.
- Traces store the (already redacted) prompts. In production they'd have a retention period.
- The old hackathon Gemini key is still in this repo's git history. It must be revoked; rewriting history won't un-leak it.
