# MetroMind v3: test report

Two kinds of numbers, never mixed:

- **Offline run (section 1–2)**: measured on 1 Nov 2026, 12:59–13:10 IST, Linux sandbox, Python 3.12, Node 20,
  provider **offline** (`offline-rules-v1`, rule-based, no API key). Code: commit `bc86aa1` (pending-review routing).
- **Live OpenAI run (section 3)**: the recorded run of 1 Nov 2026, 01:59–02:03 IST, on commit `2c35105`
  (before the pending-review change). Copied from its saved reports, not re-run.

Ingest pipeline: **19 planned steps, at most 21** (with retries), at most 4 chat-model calls + 1 Decisions API call,
max 1 retry per level.

## 1. Automated tests: `python -m pytest -q` → 55 passed, 0 failed

| Area | File | Tests | Passed | Failed |
|---|---|---|---|---|
| Core: chunking (3), RRF fusion, citation check, Level 1/Level 2 schemas (6), JSON retry and failure (3), offline provider, PII redaction + amounts not PII + injection detection (3), upload validation (4), OpenAI adapter with faked HTTP (2) | `tests/test_core.py` | 24 | 24 | 0 |
| API end to end: auth 401, clean invoice full trace, unclean letter blocked and redacted, duplicate, rejected uploads still traced (4), garbage text → review, provider down → review, ask trace scores, refusal, masked PII not retrievable, viewer limited to own department, review + audit, eval endpoint | `tests/test_api.py` | 16 | 16 | 0 |
| Layer rule: ingestion, knowledge, llm, actions import no other layer | `tests/test_layers.py` | 4 | 4 | 0 |
| Department routing and review: definitions, work-order trap (chunk says Finance, document is Maintenance), Decisions disagreement and low confidence → review, Decisions request body, gpt-6 uses `reasoning_effort`, cost in trace, **unsure → no department**, no chunk signals not called "agreement", **unclear memo waits for a human, reviewer decides, action items created only then**, **rejected document never searched** | `tests/test_routing.py` | 11 | 11 | 0 |
| **Total** | | **55** | **55** | **0** |

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

- **The pending-review change live.** The unclear memo, "no department until a reviewer decides", the new review
  queue and Reject were tested offline only (section 1). The live run above predates them.
- `ui_check.py` and `e2e_check.py` were not re-run in this pass.
- Your laptop's browser, OCR for images (needs Tesseract), Malayalam-only documents, concurrent users.
