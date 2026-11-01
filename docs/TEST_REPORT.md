# MetroMind v3: test report

Two kinds of numbers, never mixed:

- **Offline run (section 1–2)**: measured on 1 Nov 2026, 12:59–13:10 IST, Linux sandbox, Python 3.12, Node 20,
  provider **offline** (`offline-rules-v1`, rule-based, no API key). Code: commit `bc86aa1` (pending-review routing).
- **Live OpenAI run (section 3)**: the recorded run of 1 Nov 2026, 01:59–02:03 IST, on commit `2c35105`
  (before the pending-review change). Copied from its saved reports, not re-run.

Ingest pipeline: **19 planned steps, at most 21** (with retries), at most 4 chat-model calls + 1 Decisions API call,
max 1 retry per level.

## 1. Automated tests: `python -m pytest -q` → 62 passed, 0 failed

| Area | File | Tests | Passed | Failed |
|---|---|---|---|---|
| Core: chunking (3), RRF fusion, citation check, Level 1/Level 2 schemas (6), JSON retry and failure (3), offline provider, PII redaction + amounts not PII + injection detection (3), upload validation (4), OpenAI adapter with faked HTTP (2) | `tests/test_core.py` | 24 | 24 | 0 |
| API end to end: auth 401, clean invoice full trace, unclean letter blocked and redacted, duplicate, rejected uploads still traced (4), garbage text → review, provider down → review, ask trace scores, refusal, masked PII not retrievable, viewer limited to own department, review + audit, eval endpoint | `tests/test_api.py` | 16 | 16 | 0 |
| Layer rule: ingestion, knowledge, llm, actions import no other layer | `tests/test_layers.py` | 4 | 4 | 0 |
| Department routing and review: definitions, work-order trap (chunk says Finance, document is Maintenance), Decisions disagreement and low confidence → review, Decisions request body, gpt-6 uses `reasoning_effort`, cost in trace, **unsure → no department**, no chunk signals not called "agreement", **unclear memo waits for a human, reviewer decides, action items created only then**, **rejected document never searched** | `tests/test_routing.py` | 11 | 11 | 0 |
| Red-team fixes (1 Nov 2026): Decisions API down → review, held document invisible to its department until approved, original file admin/reviewer only, unsupported sentences removed, BM25 department filter inside the query, a reviewer's decision is final, an all-injection document doesn't crash | `tests/test_redteam_fixes.py` | 7 | 7 | 0 |
| **Total** | | **62** | **62** | **0** |

One warning, unrelated to MetroMind: a deprecation notice inside Starlette's test client.

Frontend: `eslint src` clean, `vite build` succeeds (same run).

## 2. Evals (offline provider): `python -m scripts.run_evals --answers`

**9 labelled documents, 27 questions (4 must be refused), k = 5.**

| L1 accuracy | Gate accuracy | L2 precision | L2 recall |
|---|---|---|---|
| 1.0 | 1.0 | 0.96 | 1.0 |

| Level 2 entity | precision | recall | extracted | gold |
|---|---|---|---|---|
| dates | 0.96 | 1.0 | 23 | 22 |
| amounts | 1.0 | 1.0 | 11 | 11 |
| reference ids | 0.92 | 1.0 | 13 | 12 |
| vendors | 1.0 | 1.0 | 4 | 4 |

| Retrieval | hit@1 | hit@5 | MRR |
|---|---|---|---|
| keyword | 1.0 | 1.0 | 1.0 |
| vector | 0.57 | 0.74 | 0.64 |
| hybrid | 0.74 | 1.0 | 0.82 |
| hybrid + HyDE | 0.74 | 1.0 | 0.82 |

| Answers | accuracy | refusal | PII leaks | faithfulness |
|---|---|---|---|---|
| hybrid | 0.70 | 0.75 | 0 | 0.96 |
| hybrid + HyDE | 0.70 | 0.75 | 0 | 0.96 |

**How to read these:** the offline rules were written next to this small labelled set, so L1/L2 mainly prove the
harness works. Offline vectors are hashed bag-of-words, so vector search trails keyword search, and offline HyDE
returns the question unchanged, so it can't change scores. Quote the live numbers below, not these, as model quality.

## 3. Live run with OpenAI (recorded 1 Nov 2026, 01:59–02:03 IST, commit `2c35105`)

Models actually used: **gpt-6-luna** for Level 1, Level 2 and answers (`reasoning_effort: low`),
**text-embedding-3-small** for embeddings, **Decisions API** (`POST /v1/decisions`, gpt-6-luna) for the department
second opinion. Fresh database for each phase.

| Check | Result | Source |
|---|---|---|
| Evals: 9 docs, 27 questions (4 refusals) | L1 **1.0**, gate **1.0**, L2 P/R **0.84 / 0.98**, hybrid hit@1 **1.0**, answers **0.96** (HyDE **1.0**), refusal **1.0**, PII leaks **0** | `evals/latest_openai.json` |
| `scripts/interview_checks.py`: 4 boundary documents, 4 tricky questions, 1 access check | **9 / 9** | `evals/interview_checks_openai.md` |
| `scripts/e2e_check.py`: API end to end | **30 / 30** | earlier report (no saved artifact) |
| `scripts/ui_check.py`: headless Chrome click-through | **34 / 35**; the miss was the script expecting the offline label on the Evals tab. Script fixed, **not re-run** | earlier report |
| `scripts/ui_layout_check.py` at 1366×768, 1280×720, 1920×1080 | no overflowing text | earlier report |

Boundary documents: fire-extinguisher tender → Procurement (Decisions 1.00), extinguisher refill invoice → Finance
(0.97), leave rules → HR (1.00), CMRS evacuation drill → Safety (0.99). Cost per upload about $0.0005.

## 4. Not tested yet

- **The pending-review change live, partly.** One live API check (1 Nov 2026, ~13:15 IST, gpt-6-luna,
  `evals/live_pending_review_check.md`): unclear memo → NEEDS_REVIEW with no department (Decisions API 0.52 sure,
  under 0.6), Operations viewer 403, approve without a department 400, reviewer picks Operations → APPROVED,
  2 held action items created, viewer 200. Work order still ANALYZED as Maintenance (1.00). Live headless-Chrome click-through (before the red-team fixes; 1 Nov 2026, ~13:10 IST, gpt-6-luna, `scripts/ui_check.py`): **43/43 UI checks
  passed**, including the review queue (reasons + Decisions %, Approve disabled until a department is picked,
  reviewer's decision in the audit). Reject was tested offline only.
- `ui_check.py` re-run live: 43/43. `e2e_check.py` includes unclear-memo checks; the live API flow was checked separately (see above).
- Your laptop's browser, OCR for images (needs Tesseract), Malayalam-only documents, concurrent users.

## Live re-test after the red-team fixes (1 Nov 2026, ~14:15 IST, OpenAI gpt-6-luna + Decisions API, fresh database)

| Check | Result |
|---|---|
| `scripts.e2e_check` (API end to end) | **34 / 34 passed** |
| `scripts.interview_checks` | **9 / 9 passed** (`evals/interview_checks_openai.md`) |
| `scripts.ui_check` (headless Chrome click-through, fresh database) | **43 / 43 passed**, no browser console errors |
| `pytest` (offline) | **62 / 62 passed** |

## Diagram PDFs, image OCR and the Level 2 source check (1 Nov 2026, ~19:00 IST)
- New: OCR of images inside PDFs (charts, diagrams, scanned pages), the unreadable-page review rule, whole-sentence injection quarantine, the `v_chunk_lineage` view, and the Level 2 source check (every extracted date, amount, ID or vendor must appear in the document text, otherwise it is dropped and listed in the trace).
- Offline: **66 passed** (pytest). Offline evals are unchanged.
- Live (gpt-6-luna + Decisions API, fresh DB): the clean report was ANALYZED, Maintenance, 3 of 3 images read. The unclean bid went to NEEDS_REVIEW with 3 injection lines quarantined (one from inside a diagram), Aadhaar/PAN/phone/email masked from a scanned page, and page 4 unreadable. See `docs/PDF_IMAGES_AND_CHUNKS.md`.
- Live evals rerun with the source check (`backend/evals/report_openai.md`): L1 1.0, gate 1.0, L2 precision 0.84 → 0.87, recall 0.98; by type: dates 0.81 → 0.85, amounts 0.73 → 0.85, reference IDs 1.0 → 0.92 (one run-to-run change), vendors 1.0. Retrieval hybrid 1.0 / 1.0 / 1.0. Answers (hybrid): accuracy 1.0, refusal 1.0, PII leaks 0, faithfulness 0.98.
