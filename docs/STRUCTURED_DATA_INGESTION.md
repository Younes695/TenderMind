# TenderMind — Structured Data Ingestion (Stage 4A)

## Position on contributor work

A Data Engineering contributor produced exploratory Excel/notebook outputs for
Mobile, Motawreen, Project 3 / 6th October and Sarai (price-schedule rows with
item/description/unit/quantity/prices, form fields, equipment/voltage,
delivery/completion, experience/project history). That work is REFERENCE/INPUT
to design ONLY: no notebook is copied into production, no hardcoded Windows
path is inherited, no exploratory assumption is imported, and no contributor
spreadsheet is treated as ground truth.

## Adapter boundary (code: `app/pipeline/structured_data.py`)

`StructuredDataAdapter` ABC: `name`, `can_handle(source)`, `read_tables(source)`
-> `List[StructuredTable]` (never raises on bad content: returns `[]`).
Contract types (`app/pipeline/contracts.py`): `StructuredTable` (document, sheet,
columns, rows), `FormRecord`, `CommercialLineItem`, `ProjectExperienceRecord` —
available for future domain adapters; only the generic table path is wired now.

## What 4A implements

`GenericXlsxAdapter` (`generic-xlsx-1`): values-only `.xlsx` reading (openpyxl
`data_only`, all sheets, `|`-free row dicts, first-nonempty-row headers,
5000-row/sheet and per-sheet char budgets mirroring current production caps).
Accepts a filesystem path OR a binary stream (in-memory workbooks in tests —
no temp files, no paths). `read_structured()` dispatches to the first capable
adapter, `[]` when nothing handles the source.

## Current production XLS/XLSX behavior (unchanged, audited)

`evaluation/run_real_benchmark.py::extract_xls_text` (called by
`app/processing.py`): `.xls` via xlrd (first 50 rows/sheet, `|`-joined);
`.xlsx` via openpyxl `data_only`, all worksheets, `iter_rows(values_only)`,
`|`-joined, 5000-char break per sheet, `page_number=1`. No styling/formula/
chart/merged-cell interpretation. Full domain FORM-D reconstruction is
explicitly out of scope unless the repo already supports it safely (it does not).

## Format policy (code: `app/pipeline/format_extraction.py`)

PDF (fitz direct; Tesseract iff scanned/garbled) · DOC (LibreOffice, olefile
fallback) · DOCX (python-docx) · XLS/XLSX (above) · TXT/CSV/LOG (utf-8 ignore) ·
images/archives/CAD/unknown -> UNSUPPORTED (explicit, counted). Never force OCR
on text PDFs. Azure/Sarai OCR stays offline-evaluation-only.
