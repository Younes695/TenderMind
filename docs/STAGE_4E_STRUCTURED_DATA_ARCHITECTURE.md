# TenderMind — Structured Data Architecture (Stage 4E)

## Reference package (read first)
`Ganna_Reference_Package.txt` (Downloads): derived summary of 4 inspected
workbooks + 4 notebooks. Reference ONLY — not gold, no code copied, no paths
inherited, no tender-specific rules. Full mapping:
`evaluation/stage4e/ganna_reference_audit.json`.
- Mobile price-schedule xlsx: 1 sheet, 254 rows, bilingual EN/AR BOQ
  (Item/Description/Unit/Quantity/Material unit price/Total); prices mostly
  empty (bidder-filled); fully tabular from row 2.
- Sarai FORM D.xls: 11 sheets (D1–D10 + Sheet1), 56×21 each; identical form
  skeleton (equipment type varies): subcontractor flag/name/origin +
  project-history slots (project/customer/location/end-user/contact); values
  sparse (pre-bid); Sheet1/D10 header-less.
- Motawreen: CAD/DWG/BAK → explicit unsupported; PINGGAOU.JPG legitimately
  empty OCR (status, not error); sparse drawing text keeps page/file provenance.
- Project 3: Clarification 1 bilingual topics (DAP, local manufacturer, org
  chart, missing form, VAT/tax, completion-start); Addendum No. 1 DUPLICATED
  in inventory → deterministic file dedup is load-bearing.
  ClarificationRecord/AddendumRecord feed future reconciliation, not plain text.

## Notebook audit (do NOT copy)
pdfplumber + pdf2image + pytesseract + pandas/openpyxl; OCR lang **eng only**;
hardcoded `C:\Users\Admin\Downloads\…`, `D:\Tesseract-OCR\…`, `D:\poppler\…`.
TenderMind contrast (kept): configurable paths (4A config), ara+eng routing,
PyMuPDF direct + OCR-only-if-scanned, no poppler chain.

## Architecture
Raw XLS/XLSX → `StructuredDataAdapter` (values-only, stream-safe) →
`StructuredTable` → `normalize_boq_table` (generic bilingual header-alias map;
refuses non-BOQ shapes; `split_bilingual` separates Arabic segments, no
translation) → `CommercialLineItem[]` (+`description_ar`) with sheet+row lineage →
validation → canonical provenance → downstream AI ONLY for semantic clauses.
Form slots → `EquipmentRecord` / `ProjectExperienceRecord` contracts (positional
reading; no tender-specific rules in production code — tested).

## What is generic vs out of scope
Generic: header aliases (EN/AR commercial terms), row dicts, bilingual text,
empty-cell tolerance, per-sheet budgets. Out of scope: merged-cell layouts,
formula/chart interpretation, Sheet1-style header-less inference, FORM-D
reconstruction, any tender-specific production rule (tested absent).

## Provenance
Every line item carries source_document + sheet + 1-based data-row
(`Sheet1!R2`); adapter never generates text; AI outputs never become
provenance truth (§11 lineage).
