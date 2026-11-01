# Diagram PDFs: how images, chunks and the review gate work

The two demo PDFs are built by `python -m scripts.make_demo_pdfs`. All content is synthetic and the PII is fake.

| File | Pages | What is inside | Expected result |
|---|---|---|---|
| `clean_rolling_stock_report_Q2_2025.pdf` | 4 | Text, KPI table, MDBF bar chart (image), depot workflow diagram (image), **scanned approval note** (image only, no text layer) | `ANALYZED`, Maintenance; 3 of 3 images read by OCR |
| `unclean_cctv_bid_sentinel_vision.pdf` | 4 | Bid text with a prompt injection, price table, architecture diagram with an **injection written inside the image**, scanned KYC page with Aadhaar/PAN/mobile, an **illegible scan** | `NEEDS_REVIEW`: injection quarantined (3 lines, from text and from the image), PII masked, page 4 unreadable |

## What happens to an image (`ingestion/extraction.py`)
1. pypdf reads the page's text layer.
2. Every embedded image on the page is listed. Images under 120x120 px (logos) are skipped.
3. Each remaining image is OCR'd with Tesseract (English, plus Hindi/Malayalam if those packs are installed). OCR noise lines with fewer than 4 letters or digits are dropped.
4. The OCR text is appended to **its own page** as `[Figure N, p.P] ...`, so a chunk built from it still cites the right page.
5. That text then goes through **PII redaction** and the **injection scan** like any other text. That's why the Aadhaar in a scanned KYC page is masked, and an instruction hidden in a diagram is quarantined.
6. A page that is only an image and gave no readable text goes in `unreadable_pages`, and the review gate holds the document. We never silently lose part of a file.
7. The trace (`extract_text` step) lists every image: page, size, words read, status.

## Live result (gpt-6-luna + Decisions API, fresh DB, 1 Nov 2026)
| | Clean report | Unclean bid |
|---|---|---|
| extract_text | 4 pages, 412 words; 3 images, 3 read | 3 pages, 262 words; 3 images, 2 read; page 4 unreadable |
| pii_redaction | no PII | 2 PHONE, 1 EMAIL, 2 AADHAAR, 1 PAN masked |
| injection_scan | clean | 3 lines quarantined (cover letter x2, diagram x1) |
| chunks | 4, 1536-dim vectors | 3, 1536-dim vectors |
| Decisions API | Maintenance 1.00 | Procurement 1.00 |
| status | ANALYZED, 4 action items | NEEDS_REVIEW |

Question answered **from the scanned page**: "Who approved the Q2 maintenance report and on what date?" got "The report was approved by the Depot Manager, Muttom, on 10 October 2025. [1]", citing p.4, faithfulness 1.0.

Known gap you can point out: the bank account number `1234 5678 9012` on the KYC scan was masked as `[AADHAAR]`. The 12-digit regex can't tell them apart. It's a safe failure (over-masking), and a checksum (Verhoeff) check would fix it.
