# MetroMind v3: Setup, Database and Code Guide

This guide covers three things: getting it running on your laptop, what the database is, and how to explain the code. Read Part C the night before.

---

## Part A. Run it on your laptop (Windows)

### What you need
| Tool | Version | Check |
|---|---|---|
| Python | 3.11 or 3.12 | `python --version` |
| Node.js | 20 or newer (Vite 7 needs it) | `node --version` |
| Git | any | `git --version` |
| OpenAI API key | with a little credit | platform.openai.com |
| Tesseract OCR | 5.x (reads text inside PDF images and scans) | `tesseract --version` |

**Tesseract on Windows:** install it from the UB Mannheim build (github.com/UB-Mannheim/tesseract/wiki), then set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `backend/.env` (the current installer no longer adds itself to PATH). Without it, images are skipped and shown as "skipped" in the trace, and a page that is only a scan goes to review. That means the clean diagram PDF would be held, so install it before the demo.

**No database server to install.** MetroMind uses **SQLite**, a single file (`backend/metromind.db`). It is created automatically the first time the backend starts (`init_db()` in `app/db.py` runs `CREATE TABLE IF NOT EXISTS`). Keyword search uses SQLite's built-in **FTS5**, and vectors are stored in the same file as bytes. You don't need Postgres, Docker, Redis or a vector database.

### 1. Backend (terminal 1)
```powershell
cd metromind\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env                       # set OPENAI_API_KEY=sk-...   (never commit .env)
python -m scripts.seed_demo        # creates the DB + prints an ADMIN key and a FINANCE VIEWER key
python -m scripts.create_api_key --name rev --role reviewer   # optional: a reviewer key
uvicorn app.main:app --reload      # http://localhost:8000   (Swagger UI at /docs)
```
On Mac or Linux, run `source .venv/bin/activate` and `cp` instead of `.venv\Scripts\activate` and `copy`.

**Copy the keys right away.** Each key is printed once, and only its SHA-256 hash is stored.

### 2. Frontend (terminal 2)
```powershell
cd metromind\frontend
npm install
npm run dev                        # http://localhost:5173
```
Paste the admin key in the box at the top right. The frontend talks to `http://localhost:8000` by default. To change that, set `VITE_API_URL`.

### 3. Check it works (2 minutes)
1. Open `http://localhost:8000/health`. It should say `"llm_provider": "openai"`, `"model": "gpt-6-luna"` and `"decisions_api": true`.
2. Upload `backend/sample_docs/invoice_INV-2025-0917_alstom.txt`. You should see **ANALYZED → Finance**.
3. Upload `unclean_vendor_letter_injection_pii.txt`. You should see **NEEDS_REVIEW**, with PII masked and the injection quarantined.
4. Upload `unclear_memo_kaloor_lost_found_cheque.txt`. You should see **Pending review** with no department. In the Review tab, Approve stays disabled until you pick a department.
5. Ask "What is the total amount on the Alstom invoice?" You should get a cited answer marked verified.
6. Paste the Finance viewer key and try to ask about Safety. It should be **blocked**.

### 4. No Wi-Fi / no credit? Offline mode
Set `LLM_PROVIDER=offline` in `.env`. The same pipeline then runs on keyword rules: no network and no cost. Tests always run this way.
**When you switch provider:** delete `metromind.db` and the `uploads\` folder, then run `seed_demo` again. Offline vectors (768 dimensions) and OpenAI vectors (1536 dimensions) can't be compared.

### 5. Tests and evals
```powershell
cd metromind\backend
python -m pytest -q                         # 62 tests, offline, about 12 seconds
python -m scripts.run_evals --answers       # writes evals/report_<provider>.md, shown in the Evals tab
```

### 6. Troubleshooting
| Symptom | Fix |
|---|---|
| `401` in the UI | You didn't paste a key, or you pasted the wrong one. Run `seed_demo` again. |
| Everything says "offline" | `OPENAI_API_KEY` is empty or `.env` isn't in `backend\`. |
| `429` / `insufficient_quota` from OpenAI | The account has no credit. Switch to offline for the demo. |
| CORS error in the browser | `FRONTEND_ORIGIN` in `.env` must match the address the UI runs on (`http://localhost:5173`). |
| `npm run dev` fails | Node is older than 20. Update Node. |
| Uploading a scanned image gives no text | OCR needs the Tesseract program installed. This is optional. |

### 7. Deploying it somewhere (if asked)
"For a pilot I'd use one small VM. Uvicorn runs behind Nginx with HTTPS. The frontend is built with `npm run build` and the static `dist/` is served by Nginx. `.env` lives on the server only. The SQLite file and `uploads/` sit on a backed-up disk.
For production, I'd swap SQLite for **Postgres + pgvector**, and the in-memory rate limiter for **Redis**. Uploads would go through a job queue (Celery or RQ) so analysis runs in the background, and the API keys would be replaced with the company's **SSO**. The layer boundaries mean only `knowledge/` and `api/auth.py` change."

---

## Part B. The database (SQLite, `app/db.py`)

| Table | What it holds | Why it exists |
|---|---|---|
| `documents` | One row per upload: file name, `sha256` (UNIQUE), saved path, status, doc type, urgency, confidence, review reasons, Level 1/2 JSON, routing JSON | The document and everything the system concluded |
| `chunks` | Chunk text (already masked), page number, embedding (float32 bytes) | The unit of retrieval and citation |
| `chunks_fts` | FTS5 virtual table, kept in sync by a trigger | BM25 keyword search |
| `departments` | The 8 KMRL departments | Lookup table |
| `document_departments` | doc ↔ department, `is_primary` | **Access control.** Only the primary department can see a document. A pending document has no rows here. |
| `action_items` | Tasks pulled out by Level 2 (with an owner department and due date) | Held until the department is known |
| `audit_log` | Who did what, and when (upload, view, download, review, redact, injection flag) | Accountability |
| `runs`, `run_steps` | One run per upload or question; one row per step with layer, timing, input, output, prompt, tokens | The "Show me how" drawer |
| `api_keys` | `key_hash` (SHA-256), name, role, department, active | Authentication |
| `v_chunk_lineage` (VIEW) | Each chunk joined to its document: page, file, sha256, status, departments, doc type, urgency, confidence, chars, `vector_dims`, `has_figure_text`, text, document summary and Level 2 entities | **Read-only window for humans.** Open it in DB Browser for SQLite to show chunk → page → document → analysis in one row |

**Where the chunk's summary, metrics and IDs live:** a chunk row holds only *its* text, page and vector. The summary, urgency, confidence, departments and the extracted dates, amounts and IDs belong to the **document** (`documents.summary`, `l1_json`, `l2_json`, `document_departments`), because they are decided from the whole document. A chunk links to them through `doc_id`. The view does that join for you.

```sql
SELECT chunk_no, page, file_name, status, departments, vector_dims, has_figure_text,
       substr(text, 1, 100) FROM v_chunk_lineage ORDER BY doc_id, chunk_no;
```

**Statuses:** `ANALYZED` (all checks passed) · `NEEDS_REVIEW` (held) · `APPROVED` / `REJECTED` (a reviewer decided; final) · `DUPLICATE` is reported, not stored twice.
**Viewers only ever see** documents that are `ANALYZED` or `APPROVED` *and* whose primary department is theirs.

---

## Part C. Code walkthrough

### The one-sentence architecture
"The API checks who you are. Then the **orchestrator** runs a fixed plan of steps, calling one layer per step: **ingestion** cleans the text, **knowledge** stores and searches it, **llm** does the model calls, and **actions** decide what happens next. Every step is written to a **trace**. Layers never call each other sideways, and a test enforces that."

```
backend/app/
  api/           auth.py (keys, roles, rate limit) · routers/ documents, ask, review, runs
  orchestrator/  ingest_flow.py (upload plan) · ask_flow.py (question plan) · review_flow.py · tracing.py
  ingestion/     validation · extraction · redaction (PII) · injection (quarantine) · chunking · signals
  knowledge/     store.py (documents, chunks, departments) · retrieval.py (BM25, cosine, RRF, filter)
  llm/           providers.py (OpenAI + Offline) · prompts · schemas · structured.py · decisions.py · grounding.py
  actions/       gate.py (review rules) · routing.py (department decision) · tasks.py · audit.py
  departments.py one table of "owns / not" used by prompts, Decisions API, offline rules and UI
```
About 2,500 lines of Python in 41 files. The frontend is about 750 lines of React.

### Upload, step by step (`orchestrator/ingest_flow.py`)
`auth → plan_run → upload_validation → sha256_dedupe → save_original → extract_text → pii_redaction → injection_scan → chunking → chunk_department_signals → embed_chunks → index_chunks → level1_classification → department_decision → level2_extraction → department_routing → review_gate → create_action_items → save_results`
That's 19 steps. With retries there are at most 21 steps and at most 4 chat calls plus 1 Decisions call, so a run can never loop.

### Question, step by step (`orchestrator/ask_flow.py`)
`auth → department filter → BM25 → HyDE (optional) → embed → cosine → RRF fusion → answer prompt → citation check → audit`

### The 10 snippets they're most likely to ask about

**1. Structured output with one retry**: `llm/structured.py`
```python
for attempt in range(MAX_RETRIES + 1):
    retry_note = f"Your previous reply was invalid: {error}. Return corrected JSON." if error else ""
    reply = llm.generate(build_prompt(retry_note), json_mode=True)
    try:
        return schema.model_validate(json.loads(reply.text))    # Pydantic checks types and ranges
    except (json.JSONDecodeError, ValidationError) as exc:
        error = _short_error(exc)                                # feed the error back once
raise LevelFailed(...)                                           # -> document goes to review
```
*Say:* "JSON mode guarantees the reply parses, and Pydantic guarantees it fits the schema. If it doesn't, I retry once with the exact error, and then give up and hand it to a human. A provider error doesn't get a retry, because retrying a dead API won't help."

**2. Department routing, and when it refuses to decide**: `actions/routing.py`
```python
if decision:                                   # Decisions API answered
    if decision["choice"] != final:
        review_reason = "department unclear: Level 1 says X, Decisions API says Y"
    elif decision["confidence"] < threshold:   # 0.6
        review_reason = "department unclear: Decisions API only 0.52 sure"
elif decisions_expected:                       # switched on but failed
    review_reason = "department unchecked: Decisions API unavailable"
pending = review_reason is not None            # -> final_department None, nobody owns it
```
*Say:* "Level 1 reads the whole document and proposes a department. The Decisions API gives a real probability for each department as a second opinion. If they disagree, or it's under 60% sure, or it's down, I don't guess. The document has no owner until a reviewer picks one."

**3. Access control before retrieval**: `knowledge/retrieval.py`
```sql
SELECT dd.doc_id FROM document_departments dd
JOIN departments d ON d.dept_id = dd.dept_id
JOIN documents doc ON doc.doc_id = dd.doc_id
WHERE d.name = ? AND dd.is_primary = 1
  AND doc.status IN ('ANALYZED', 'APPROVED')
```
*Say:* "A viewer's department comes from their key, not from the request. Only their department's approved documents are searchable at all, so another department's text can't reach the prompt."

**4. BM25 with the filter inside the query**: `knowledge/retrieval.py`
```python
doc_filter = f"AND c.doc_id IN ({','.join('?' * len(ids))})" if ids else ""
rows = conn.execute(FTS_SQL.format(doc_filter=doc_filter), (query, *ids, limit))
```
*Say:* "The filter goes inside the SQL, before ranking and LIMIT, so other departments' documents can't crowd the results out. Every value is a `?` parameter, and each search word is quoted, so a question can't inject SQL or break FTS syntax."

**5. Reciprocal Rank Fusion**: `knowledge/retrieval.py`
```python
for ranking in rankings:                       # [bm25 order, vector order]
    for rank, chunk_id in enumerate(ranking, start=1):
        score[chunk_id] += 1.0 / (k + rank)    # k = 60
```
*Say:* "BM25 scores and cosine scores aren't on the same scale, so I fuse ranks, not scores. A chunk near the top of both lists wins. k = 60 is the standard constant, and it stops a single first place from dominating."

**6. Vector search**: `knowledge/retrieval.py`
```python
matrix = np.vstack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows])
scores = matrix @ query_vec                    # unit vectors, so dot product = cosine
```
*Say:* "At demo scale, a numpy scan is exact and simple. At thousands of documents, I'd move to pgvector with an HNSW index."

**7. PII masking before anything else sees the text**: `ingestion/redaction.py`
```python
"AADHAAR": r"\b\d{4}\s?\d{4}\s?\d{4}\b",  "PAN": r"\b[A-Z]{5}\d{4}[A-Z]\b",
"PHONE": r"(?:\+91[\s-]?)?\b[6-9]\d{9}\b",  "EMAIL": ...
```
*Say:* "Masking happens before chunking, so the LLM, the index, the vectors and the trace only ever see `[AADHAAR]`. The unmasked original is kept for traceability, but only admins and reviewers can download it. Honest limit: regex misses some formats. Next I'd add the Aadhaar checksum and an NER model."

**8. Prompt-injection quarantine**: `ingestion/injection.py`
```python
for line in page.text.splitlines():
    if find_injection(line): quarantined.append(...)   # never chunked, indexed or sent to the LLM
    else: kept.append(line)
```
*Say:* "It's one of three layers. Suspicious lines are removed and the document goes to review. The prompt wraps chunks as data, not instructions. And the checker gate plus human review are the backstop. Regex can be dodged, which is why it's not the only layer."

**9. Citation check: refuse rather than invent**: `orchestrator/ask_flow.py` + `llm/grounding.py`
```python
kept = [r["text"] for r in table if r["supported"]]       # >= 50% of words found in the cited chunk
grounded = NOT_FOUND not in answer and bool(kept) and faithfulness >= MIN_FAITHFULNESS   # 0.5
if grounded: answer = " ".join(kept)                      # unsupported sentences are removed
```
*Say:* "Every sentence must cite a chunk, and I check word overlap with that chunk without an extra LLM call. Unsupported sentences are dropped. If fewer than half are supported, the answer is exactly 'Not found in the documents.'"

**10. Tracing every step**: `orchestrator/tracing.py`
```python
@contextmanager
def step(self, name, layer):
    s = Step(seq=len(self.steps) + 1, name=name, layer=layer, started_at=_now())
    t0 = time.perf_counter()
    try: yield s                       # the code fills s.input / s.output / s.detail (prompt, tokens)
    except Exception: s.status = "failed"; raise
    finally: s.duration_ms = ...; self.steps.append(s)
```
*Say:* "Each step is a `with tracer.step(...)` block, so timing and failures are recorded even when something crashes. Tokens give a cost per run, about $0.0005 per upload on gpt-6-luna. The drawer just replays these rows."

### Human review (`orchestrator/review_flow.py`)
- Only `NEEDS_REVIEW` or `ANALYZED` documents can be reviewed. `APPROVED` and `REJECTED` are final, so you can't approve after a reject or approve twice.
- **Approve** needs a department if none is set (otherwise `400`). It sets ownership and creates the held action items, and the audit records "pending → Operations".
- **Reject** removes ownership and action items. The document stays stored for audit but is never searched.

### Security in one table
| Risk | Defence | Where |
|---|---|---|
| Stolen key | Only SHA-256 hashes stored; keys printed once | `api/auth.py` |
| Cross-department leak | Department from the key; filter before retrieval; primary only | `retrieval.py` |
| PII to the LLM | Masked before chunking | `ingestion/redaction.py` |
| Prompt injection | Quarantine + "documents are data" prompt + review | `ingestion/injection.py`, `llm/prompts.py` |
| Hallucination | Citation check, sentence removal, refusal | `llm/grounding.py`, `ask_flow.py` |
| Runaway cost | Fixed plan: max steps and max LLM calls; tokens and cost per run | `ingest_flow.py RUN_PLAN` |
| Bad uploads | Type checked by content, 15 MB cap, folder paths stripped from file names, SHA-256 dedupe | `ingestion/validation.py` |

### Honest limits (say them before they find them)
- SQLite and a numpy scan are fine for a demo. Production would use Postgres + pgvector and a job queue.
- The rate limiter is in memory per process, and there are API keys rather than SSO.
- Regex PII and injection checks catch common patterns, not everything.
- The 0.6 threshold was chosen by hand. I'd tune it on labelled KMRL documents.
- The Decisions probability varies a little between runs (the unclear memo got 0.33 once and 0.52 another time), which is exactly why borderline documents go to a human.
- Only manual upload is built. Gmail, WhatsApp and Drive are planned.
