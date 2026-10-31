# MetroMind v2: Demo and Defence Guide

## 1. The 5-minute laptop demo

1. **Before the panel arrives:** backend and frontend running, sample docs seeded, browser on the Upload tab. Header badge shows `LLM: gemini` (or `offline` if there is no Wi-Fi).
2. **Problem, 20 s:** "KMRL gets thousands of mixed documents a day, some in Malayalam. Managers lose time finding them and compliance notices get buried."
3. **Upload, 40 s:** drop `invoice_INV-2025-0917_alstom.txt`. It comes back `ANALYZED`. Drop it again: "duplicate of #N". Say: "SHA-256 of the bytes, enforced by a UNIQUE column, so a PDF forwarded five times is processed once."
4. **Documents tab, 60 s:** open the invoice: department, confidence, reasoning, summary, amounts, deadline. "One LLM call in JSON mode, validated against a Pydantic schema. If the model returns a department that doesn't exist, validation fails, we retry once with the error, then send it to human review."
5. **Ask tab, 90 s:** ask "When is the Alstom invoice payment due?" and point at the `[1]` citation and the "open" link. Then ask something that isn't there ("What is the canteen menu?") and show "Not found in the documents." Say: "Hybrid search: BM25 for exact things like invoice numbers, vectors for meaning, merged with Reciprocal Rank Fusion. The prompt only allows answers from the numbered context."
6. **Department filter, 20 s:** ask about door sensors with the filter set to Finance: no safety chunks come back. "Access filter runs before retrieval, not after."
7. **Review & Audit, 40 s:** the safety circular is in the queue because it's Critical. Approve it. Show the audit rows: INGEST, ANALYZE, QUERY, REVIEW.
8. **Close, 20 s:** "Next steps: Postgres with pgvector, a job queue for Gmail ingestion, JWT login with roles."

Have `http://localhost:8000/docs` (Swagger) in a second tab in case they want the API.

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
| No tests | 12 pytest tests, run offline | Deterministic thanks to the offline provider |

## 3. Trace one request (they love "walk me through the code")

**Upload** → `routers/documents.py: upload()` → `services/ingestion.py: ingest_file()`:
1. `sha256_bytes()`; `SELECT ... WHERE sha256 = ?` → return early if it's a duplicate
2. save the original to `uploads/` (for traceability)
3. `extraction.extract_pages()` → `chunking.chunk_pages()` (each chunk keeps its page number)
4. `llm.embed()` → store float32 bytes in `chunks.embedding`; a trigger fills the FTS5 index
5. `analysis.analyze_document()` → `DocumentAnalysis.model_validate()`
6. `save_analysis()` → status `ANALYZED`, or `NEEDS_REVIEW` if confidence < 0.6 or urgency is Critical → `audit()`

**Ask** → `routers/ask.py` → `services/rag.py: answer_question()`:
1. `retrieval.hybrid_search()`: department filter → `keyword_search()` (FTS5 `bm25()`) and `vector_search()` (numpy dot product on normalised vectors) → `reciprocal_rank_fusion()` → top 5
2. `build_context()` numbers the chunks `[1]..[5]` with file and page
3. LLM answers; we keep only the `[n]` it actually used; no valid citation → "Not found in the documents."
4. `audit("QUERY", chunk ids)`

## 4. Likely questions, with answers

**Why one LLM call instead of four?** Fewer round trips, lower cost, one schema to validate. The four-step chain made sense for debugging prompts in the hackathon.

**How do you stop hallucination?** Retrieval quality (hybrid + fusion), a prompt that only allows the numbered context, a fixed "Not found" reply, citation checking in code, temperature 0.1, and schema validation for the analysis.

**Why SQLite? Will it scale?** It's the right size for a demo with thousands of chunks, and the vector scan is a single numpy matrix multiply. Production: Postgres with pgvector and an HNSW index, the same tables, and FTS becomes a GIN index on `to_tsvector`.

**What is RRF?** score = Σ 1/(60 + rank) across the result lists. It uses only ranks, so BM25 scores and cosine scores, which are on different scales, combine without tuning.

**Why chunk overlap?** A sentence cut at a boundary still appears whole in the neighbouring chunk.

**Why 200 words?** Small enough to be precise, big enough to hold a full clause. It's in `.env` and would be tuned on a set of real questions.

**What does the offline provider do?** Keyword rules for the department, feature-hashed bag-of-words vectors, and an extractive answer (the context sentence with the most question words). It keeps the demo alive without internet and makes tests deterministic. Same interface as Gemini: the strategy pattern.

**Why is sha256 UNIQUE in the DB and not just checked in code?** The database enforces it even if two uploads race each other.

**What happens if Gemini is down?** Embedding failure → HTTP 502 with a clear message. Analysis failure → the document is stored and indexed, then marked NEEDS_REVIEW, so the pipeline never loses a file.

**Security?** No key in the browser, upload size limit, file-type allowlist, filename sanitising, CORS locked to the frontend origin, verified Google id_token. Still to add: JWT login with roles, encrypting refresh tokens at rest, malware scan on uploads.

**How would you evaluate it?** A set of real questions with known source chunks: recall@5 and MRR for retrieval; faithfulness and citation accuracy for answers; accuracy against reviewer corrections for classification.

**How would Gmail scale?** Gmail push notifications (Pub/Sub watch) instead of polling, a job queue with workers, batch embedding, and idempotent jobs keyed by SHA-256.

## 5. Be honest about these

- It's a hackathon project, refactored afterwards. It isn't deployed and has no real users, so don't quote a review-time saving as measured.
- The offline mode is a fallback, not the real model.
- There's no app login yet; the department filter shows where role-based access would plug in.
- Scanned PDF pages are skipped (images are OCR'd); per-page OCR for PDFs is the next step.
