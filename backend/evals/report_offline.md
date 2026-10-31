# MetroMind eval report (offline: offline-rules-v1)

Generated 2026-10-31T20:20:00+00:00 - 9 documents - 27 questions (4 must be refused) - k = 5

### Level 1 and gate

| L1 accuracy | gate accuracy | L2 precision | L2 recall |
|---|---|---|---|
| 1.0 | 1.0 | 0.96 | 1.0 |

### Level 2 by entity type

| entity | precision | recall | extracted | gold |
|---|---|---|---|---|
| dates | 0.96 | 1.0 | 23 | 22 |
| amounts | 1.0 | 1.0 | 11 | 11 |
| reference_ids | 0.92 | 1.0 | 13 | 12 |
| vendors | 1.0 | 1.0 | 4 | 4 |

### Level 1 per document

| document | gold | predicted | status |
|---|---|---|---|
| invoice_INV-2025-0917_alstom.txt | Finance | Finance | ANALYZED |
| safety_circular_SC-14_platform_screen_doors.txt | Safety | Safety | ANALYZED |
| unclean_vendor_letter_injection_pii.txt | Finance | Finance | NEEDS_REVIEW |
| cmrs_inspection_letter_vyttila_extension.txt | Safety | Safety | ANALYZED |
| contract_amendment_housekeeping_services.txt | Legal | Legal | ANALYZED |
| hr_notice_training_malayalam_signage.txt | HR | HR | ANALYZED |
| maintenance_report_muttom_depot_sept.txt | Maintenance | Maintenance | ANALYZED |
| tender_notice_cctv_upgrade.txt | Procurement | Procurement | ANALYZED |
| work_order_WO-RS-2025-0412_bogie_overhaul.txt | Maintenance | Maintenance | ANALYZED |

### Retrieval

| retrieval | hit@1 | hit@5 | MRR |
|---|---|---|---|
| keyword | 1.0 | 1.0 | 1.0 |
| vector | 0.57 | 0.74 | 0.64 |
| hybrid | 0.74 | 1.0 | 0.82 |
| hybrid+hyde | 0.74 | 1.0 | 0.82 |

### Answers

| retrieval | answer_accuracy | refusal | pii_leaks | faithfulness | latency_s |
|---|---|---|---|---|---|
| hybrid | 0.7 | 0.75 | 0 | 0.96 | 0.0 |
| hybrid+hyde | 0.7 | 0.75 | 0 | 0.96 | 0.0 |
