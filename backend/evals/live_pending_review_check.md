# Live check: unsure department waits for a human (openai: gpt-6-luna)

Run 1 Nov 2026, ~13:15 IST, fresh database, real OpenAI (gpt-6-luna chat, text-embedding-3-small, Decisions API).

| document | status | department | why | action items | access |
|---|---|---|---|---|---|
| unclear_memo_kaloor_lost_found_cheque.txt | NEEDS_REVIEW | none (pending review); Level 1 said Operations | Decisions API only 0.52 sure of Operations (< 0.6) | 0 until review | Operations viewer 403 |
| after review | APPROVED | Operations (picked by reviewer) | approve with no department refused (400) | 2 created on approval | Operations viewer 200 |
| work_order_WO-RS-2025-0412_bogie_overhaul.txt | ANALYZED | Maintenance | Decisions API agrees, 1.00 | 5 | - |

Cost: unclear memo $0.00057 (1,954 in / 764 out), work order $0.00094 (3,887 in / 1,207 out).
Note: an earlier Decisions-only probe on the same memo gave Operations 0.33; the probability varies between runs but stayed under 0.6 both times.
