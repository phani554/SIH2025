# MetroMind v2: Demo and Defence Guide

## 1. The 6-minute laptop demo

1. **Before the panel arrives:** run `python -m scripts.seed_demo`, start backend and frontend, paste the admin key (top right). Header shows `LLM: gemini` (or `offline` without Wi-Fi). Keep the Finance viewer key in a note.
2. **Problem, 20 s:** "KMRL gets thousands of mixed documents a day, some in Malayalam. Managers lose time finding them and compliance notices get buried."
3. **Upload, 40 s:** drop `invoice_INV-2025-0917_alstom.txt`, then drop it again: "duplicate". Say: "SHA-256 of the bytes, enforced by a UNIQUE column."
4. **Documents tab, 60 s:** open the invoice: department, confidence, summary, amounts, then scroll to **Chunks**. "One LLM call in JSON mode validated by Pydantic. The vendor's email was masked before anything went to the LLM; you can see [EMAIL] in the chunk."
5. **Ask tab, 90 s:** "When is the Alstom invoice payment due?" Point at `[1]`, the **verified** badge and the faithfulness line. "Hybrid search: BM25 for exact things like invoice numbers, vectors for meaning, merged with Reciprocal Rank Fusion. HyDE embeds a hypothetical answer so short questions match long documents. Then I check every sentence against the chunk it cites." Ask "What is the canteen menu?" and show the refusal.
6. **Security, 45 s:** paste the Finance viewer key. Documents tab shows only Finance. Ask about door sensors: nothing from Safety. "The department comes from the key, and the filter runs before retrieval." Switch back to admin.
7. **Review & Audit, 30 s:** approve a queued document; show the audit rows (INGEST, REDACT, QUERY, REVIEW).
8. **Evals, 30 s:** open `backend/evals/report_*.md`. "23 questions, 3 must be refused. I compare three chunkers and four retrieval modes on hit@k, MRR, accuracy, refusal and faithfulness."
9. **Close, 15 s:** "Next: cross-encoder re-ranking, Postgres + pgvector, SSO."

Have `http://localhost:8000/docs` (Swagger) in another tab, and VS Code open at `services/` in case they want code.

## 2. What changed from the hackathon version, and why

| Hackathon (v1) | v2 | Why |
|---|---|---|
| Gemini key in front-end JS | Key only in backend `.env`, sent as a header | Anyone could read the key from the browser |
| 4 chained prompts from the browser | 1 structured call on the server | 4× latency and cost; one schema is easier to validate |
| Regex grabbed the first `{...}` | JSON mode + Pydantic + 1 retry + review fallback | Never trust unvalidated LLM output |
| PDF text by regex on raw bytes | pypdf, per page | Old method failed on compressed PDFs; pages give citations |
| No vector search | Chunk → embed → hybrid BM25 + vector + RRF | The RAG layer we had only designed |
| Analysis not stored | `documents`, `document_departments`, `action_items` | Results must be queryable and reviewable |
| No audit | `audit_log` with `ON DELETE SET NULL` | Audit must outlive the document it records |
| Hard-coded sender email in the Gmail worker | Configurable query, same pipeline as uploads | One ingestion path for every source |
| id_token base64-decoded | id_token signature verified | Decoding doesn't prove it came from Google |
| No retrieval tuning | 3 chunkers, keyword/vector/hybrid, HyDE, all switchable | So you can measure instead of guess |
| No answer checking | Citation check + faithfulness score | Catch "cites [2] but [2] doesn't say that" |
| Open API | Hashed API keys, roles, department filter, rate limit | Least privilege, per-user audit |
| Raw text to the LLM | PII redaction + prompt-injection quarantine | Privacy and safety of a document pipeline |
| No tests or evals | 22 pytest tests + eval harness | Deterministic thanks to the offline provider |

## 3. Trace one request (they love "walk me through the code")

**Upload** → `routers/documents.py: upload()` (`require_role("admin","reviewer")`, `validate_upload()`) → `services/ingestion.py: ingest_file()`:
1. `sha256_bytes()`; `SELECT ... WHERE sha256 = ?` → return early if it's a duplicate
2. save the original to `uploads/` (for traceability)
3. `extraction.extract_pages()` → `_redact_pages()` (PII masked)
4. `chunking.chunk_pages(strategy)` → `llm.embed()` → `looks_like_injection()` per chunk → insert; a trigger fills FTS5
5. `analysis.analyze_document()` on the non-flagged text → `DocumentAnalysis.model_validate()`
6. `save_analysis()` → `ANALYZED`, or `NEEDS_REVIEW` if confidence < 0.6, Critical, or flagged → `audit()`

**Ask** → `routers/ask.py` (`allowed_department()` pins viewers) → `services/rag.py: answer_question()`:
1. `retrieval.search()`: department filter → `keyword_search()` (FTS5 `bm25()`) and `vector_search(query_vector(use_hyde))` → `reciprocal_rank_fusion()` → top 5 (flagged chunks excluded)
2. `build_context()` numbers the chunks `[1]..[5]` inside `<documents>` tags
3. LLM answers → `check_citations()` → faithfulness + `supported` per citation; nothing valid → "Not found in the documents."
4. `audit("QUERY", chunk ids, hyde, faithfulness)`

## 4. Likely questions, with answers

**What is HyDE and when does it hurt?** Hypothetical Document Embeddings: the LLM writes a fake answer passage, and we embed question + passage for the vector search. It helps short or vague questions match formal documents. It costs an extra LLM call, and if the model invents the wrong topic it can pull the wrong chunks; that's why I embed it together with the real question and keep BM25 on the real question.

**Which chunking strategy did you pick and why?** Recursive by default: it splits on paragraph, then line, then sentence boundaries, so clauses and table rows stay whole. The eval script compares all three. On our 7 short sample documents they're close (offline baseline accuracy: fixed 0.70, recursive 0.65, sentence 0.60), because most documents fit in one chunk; recursive pays off on long, structured documents. Quote the Gemini numbers once you've run them.

**How does the citation check work?** For each answer sentence, take its content words and see what share appear in the chunk it cites. At least 50% means supported. Faithfulness is the share of supported sentences. It's cheap and explainable; its weakness is paraphrase, so the next step is an LLM-as-judge or an NLI model.

**What do your evals show?** Run it and read the table. Honest framing: 23 questions, 7 documents, so retrieval is near the ceiling; the dataset is the thing to grow. The offline baseline is 0.60 to 0.70 answer accuracy; Gemini should clearly beat it.

**How do you stop prompt injection?** Three layers: a pattern scan at ingest that quarantines chunks and sends the document to review; flagged chunks never reach the LLM; and the prompt wraps documents in tags and says they're data. Plus the LLM can't take actions, it only writes text, so the blast radius is small.

**Why hash API keys with SHA-256 and not bcrypt?** The keys are 32 random characters, so brute force is hopeless and a fast hash is fine. Human passwords are guessable, so they need a slow hash like bcrypt.

**Why one LLM call instead of four?** Fewer round trips, lower cost, one schema to validate. The four-step chain made sense for debugging prompts in the hackathon.

**How do you stop hallucination?** Retrieval quality (hybrid + fusion), a prompt that only allows the numbered context, a fixed "Not found" reply, citation checking in code, temperature 0.1, and schema validation for the analysis.

**Why SQLite? Will it scale?** It's the right size for a demo with thousands of chunks, and the vector scan is a single numpy matrix multiply. Production: Postgres with pgvector and an HNSW index, the same tables, and FTS becomes a GIN index on `to_tsvector`.

**What is RRF?** score = Σ 1/(60 + rank) across the result lists. It uses only ranks, so BM25 scores and cosine scores, which are on different scales, combine without tuning.

**Why chunk overlap?** A sentence cut at a boundary still appears whole in the neighbouring chunk.

**Why 200 words?** Small enough to be precise, big enough to hold a full clause. It's in `.env` and would be tuned on a set of real questions.

**What does the offline provider do?** Keyword rules for the department, feature-hashed bag-of-words vectors, and an extractive answer (the context sentence with the most question words). It keeps the demo alive without internet and makes tests deterministic. Same interface as Gemini: the strategy pattern.

**Why is sha256 UNIQUE in the DB and not just checked in code?** The database enforces it even if two uploads race each other.

**What happens if Gemini is down?** Embedding failure → HTTP 502 with a clear message. Analysis failure → the document is stored and indexed, then marked NEEDS_REVIEW, so the pipeline never loses a file.

**Security?** Hashed API keys with three roles, department filter before retrieval, rate limit, magic-byte upload checks, PII redaction, injection quarantine, OAuth state + verified id_token, security headers, audit log. Gaps I'd name: in-memory rate limiter, unencrypted refresh tokens, regex-based detection. (docs/SECURITY.md)

**How would you evaluate classification?** Reviewer corrections become labels; track accuracy and the share sent to review per department.

**How would Gmail scale?** Gmail push notifications (Pub/Sub watch) instead of polling, a job queue with workers, batch embedding, and idempotent jobs keyed by SHA-256.

## 5. Change it live (if they say "now make it do X")

| Ask | Change | Then |
|---|---|---|
| Bigger / smaller chunks | `.env`: `CHUNK_SIZE_WORDS`, `CHUNK_OVERLAP_WORDS` | delete `metromind.db` + `uploads/`, re-seed |
| Another chunking strategy | `.env`: `CHUNK_STRATEGY=sentence` (or `fixed`) | re-seed |
| HyDE off by default | `.env`: `USE_HYDE=false` (or untick it in the UI) | restart |
| Keyword-only or vector-only | Ask tab dropdown, or `"mode"` in the `/ask` body | nothing |
| More / fewer chunks in the prompt | `top_k` in `AskRequest` (`schemas.py`) | restart |
| Stricter citation check | `SUPPORT_THRESHOLD` in `services/rag.py` | restart |
| Send more to human review | `.env`: `REVIEW_CONFIDENCE_THRESHOLD=0.8` | new uploads |
| New department | add it to `DEPARTMENTS` in `config.py` (+ keywords in `llm.py` for offline) | re-seed |
| New PII type (e.g. passport) | one regex in `PII_PATTERNS` in `security.py` | new uploads |
| New injection phrase | add an alternative to `INJECTION_PATTERNS` in `security.py` | new uploads |
| Another eval question | one JSON line in `evals/dataset.jsonl` | `python -m scripts.run_evals` |
| New user | `python -m scripts.create_api_key --name x --role viewer --department HR` | nothing |
| RRF constant | `k=60` in `reciprocal_rank_fusion()` | restart |

After any code change: `python -m pytest -q` (about 1 second).

## 6. Be honest about these

- It's a hackathon project, refactored afterwards. It isn't deployed and has no real users, so don't quote a review-time saving as measured.
- The offline mode is a fallback, not the real model.
- API keys, not SSO. Fine for a demo; staff would log in with SSO and short-lived JWTs.
- The evals use our own small dataset; the numbers show the method, not production quality.
- Scanned PDF pages are skipped (images are OCR'd); per-page OCR for PDFs is the next step.
