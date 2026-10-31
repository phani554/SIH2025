# MetroMind eval report (offline: offline-rules-v1)

Generated 2026-10-31T20:01:09+00:00 - 8 documents - 25 questions (4 must be refused) - k = 5

### Level 1 and gate

| L1 accuracy | gate accuracy | L2 precision | L2 recall |
|---|---|---|---|
| 1.0 | 1.0 | 0.98 | 1.0 |

### Level 2 by entity type

| entity | precision | recall | extracted | gold |
|---|---|---|---|---|
| dates | 0.95 | 1.0 | 20 | 19 |
| amounts | 1.0 | 1.0 | 9 | 9 |
| reference_ids | 1.0 | 1.0 | 10 | 10 |
| vendors | 1.0 | 1.0 | 3 | 3 |

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

### Retrieval

| retrieval | hit@1 | hit@5 | MRR |
|---|---|---|---|
| keyword | 1.0 | 1.0 | 1.0 |
| vector | 0.67 | 0.95 | 0.76 |
| hybrid | 0.81 | 1.0 | 0.89 |
| hybrid+hyde | 0.81 | 1.0 | 0.89 |
