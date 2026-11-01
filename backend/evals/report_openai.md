# MetroMind eval report (openai: gpt-6-luna)

Generated 2026-11-01T13:34:57+00:00 - 9 documents - 27 questions (4 must be refused) - k = 5

### Level 1 and gate

| L1 accuracy | gate accuracy | L2 precision | L2 recall |
|---|---|---|---|
| 1.0 | 1.0 | 0.87 | 0.98 |

### Level 2 by entity type

| entity | precision | recall | extracted | gold |
|---|---|---|---|---|
| dates | 0.85 | 1.0 | 26 | 22 |
| amounts | 0.85 | 1.0 | 13 | 11 |
| reference_ids | 0.92 | 0.92 | 12 | 12 |
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
| vector | 0.87 | 1.0 | 0.92 |
| hybrid | 1.0 | 1.0 | 1.0 |
| hybrid+hyde | 1.0 | 1.0 | 1.0 |

### Answers

| retrieval | answer_accuracy | refusal | pii_leaks | faithfulness | latency_s |
|---|---|---|---|---|---|
| hybrid | 1.0 | 1.0 | 0 | 0.98 | 1.42 |
| hybrid+hyde | 0.91 | 1.0 | 0 | 0.89 | 3.46 |
