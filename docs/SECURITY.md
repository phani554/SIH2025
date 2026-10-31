# Security

All of it lives in `backend/app/security.py` (about 150 lines) plus a few lines in the routers.

| Threat | Control | Where |
|---|---|---|
| Leaked LLM key | Key only in backend `.env`, sent as `x-goog-api-key` header (not in URLs or logs); browser never calls the LLM | `config.py`, `llm.py` |
| Anyone can call the API | `X-API-Key` on every request; keys stored as SHA-256 hashes, shown once at creation | `current_user()`, `scripts/create_api_key.py` |
| Over-broad access | Roles: **admin** (everything), **reviewer** (all departments, approve, audit), **viewer** (read/ask in own department only) | `require_role()`, `allowed_department()` |
| Cross-department leaks via RAG | Department filter applied **before** retrieval; viewer's department comes from their key, not the request | `ask.py`, `retrieval.search()` |
| Abuse / cost blow-up | 30 requests per minute per key (sliding window) | `check_rate_limit()` |
| Malicious uploads | 15 MB limit, extension allowlist, **magic-byte check** (a `.pdf` must start with `%PDF`), filename sanitised | `validate_upload()`, `safe_file_name()` |
| Personal data sent to the LLM | Aadhaar, PAN, phone and email masked (`[PHONE]`) **before** chunking, embedding and analysis | `redact_pii()`, `ingestion.py` |
| Prompt injection inside documents | Pattern scan at ingest; flagged chunks excluded from retrieval and analysis, document sent to review; prompt marks documents as data | `looks_like_injection()`, `rag.py` |
| OAuth CSRF on Gmail connect | Random `state` issued and checked on callback; Google `id_token` signature verified | `routers/gmail.py`, `services/gmail.py` |
| Server details leaking | `saved_path` removed from API responses; security headers (`nosniff`, `DENY` framing, `no-referrer`); CORS limited to the frontend origin, methods and headers | `documents.py`, `main.py` |
| No accountability | `audit_log` for INGEST, REDACT, INJECTION_FLAG, ANALYZE, VIEW, DOWNLOAD, QUERY, REVIEW, DELETE, with the key's name; rows survive document deletion | `db.audit()` |

## Known gaps (say these before they ask)

- Rate limiter and OAuth states are in memory: they reset on restart and don't work across several servers (use Redis).
- Gmail refresh tokens are stored unencrypted in SQLite (encrypt with Fernet or a KMS).
- Regex PII and injection detection catch common patterns, not everything. It's defence in depth, not a guarantee.
- API keys suit a demo or service-to-service use. Staff would log in with SSO and get short-lived JWTs.
- The old Gemini key is still in this repo's git history. It has been revoked; rewriting history wouldn't un-leak it.
