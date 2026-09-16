# AI Evaluation Run — Sarai Real v1
**Tender:** Sarai 220/22kV GIS Substation (No. SA/2018/HV2) — ID SA-2018-HV2 (stored)
**Original Folder:** `C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation` — 64 files (68 total with G duplicates)
**Gold:** `evaluation/sarai_gold_dataset.json` — 21 REQ + 4 E + 7 Risks — **USED ONLY AFTER INFERENCE**
**Pipeline:** Original PDFs/DOC/XLSX → Document Intelligence/OCR → text/table extraction → Arabic/English normalization → Requirement Extraction (rule-based) → Evidence Extraction (rule-based) → Matching (status.py) → Decision (decision.py) → Explanation
**Run:** 2026-09-13T06:05:36.250355Z — Python 3.11.0 — fitz 1.28.2

## Models / Services Used (Logged for Reproducibility)
- **Document Intelligence:** PyMuPDF fitz 1.28.2 direct text; OCR pytesseract NOT installed (scanned PDFs -> 0 text); pdfminer.six not run
- **Requirement Extraction:** Rule-based keyword patterns (21 patterns, regex) — NOT LLM, no gold injection, provenance file+page preserved
- **Evidence Extraction:** Rule-based on consortium agreement text — NOT LLM, 4 patterns
- **Matching:** app/engines/status.py deterministic (expiry/conflict/applicability) — unchanged semantics
- **Decision:** app/engines/decision.py deterministic hierarchy §6
- **Explanation:** app/engines/explanation.py
- **prompt/configuration:** Rule-based regex patterns (21 requirement patterns, 4 evidence patterns) — version 1.0, no LLM prompt, deterministic, no gold injection.

> **Reproducibility:** Original files in `C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation` are ONLY source during inference. Gold dataset loaded after inference for evaluation only. Every requirement/evidence preserves `source file + page/sheet/section + extraction method + OCR flag`.

## 1. File Inventory

**Root:** `C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation` — 64 files detected (68 with duplicates, 64 via rglob)

| Ext | Count | Extraction Method | OCR Needed | Example Relevance |
|---|---|---|---|---|
| .pdf | 35 | NATIVE_PDF (fitz) or SCANNED_PDF → OCR needed | YES for Sarai RFP (2p, 1.07MB), Part1 (409p,11MB), Part2 (487p,13MB), G-series scanned; NO for volume 1 of 2 (189p, 1.54MB) partially garbled | HIGH: Sarai RFP (REQ-A/C), Volume1 (Instructions), Part1/2 (GIS 220kV, 175MVA, type-test), G-3B GIS, G-33 Transformer |
| .doc | 29 | DOC old binary → python-docx fails → reported limitation | NO but binary parsing fails | MEDIUM/HIGH: G-series specs (1.2MB GIS.doc etc.) — old .doc requires antiword |
| .docx | 1 | DOCX → python-docx | NO | G-22 Low Voltage Switchgear |
| .xls | 1 | XLS → xlrd | NO | FORM D.xls (104KB, 11 sheets) — schedule/experience |

Full inventory: See `evaluation/run_real_benchmark.py` file_inventory() — 64 files, sizes 40KB–13MB, 1394 total pages extracted (611,956 chars, but 0 chars for 32 scanned PDFs).

**Selected for inference:** All PDFs/DOCs except `SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc` (company evidence, not tender). Drawings metadata only.

## 2. Files Actually Used
- **Tender requirements:** Sarai RFP.pdf (2p, 0 chars scanned), volume 1 of 2.pdf (189p, garbled 0.5), Part1/2, G/*.pdf (29 specs), FORM D.xls
- **Company evidence:** `SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc` (40KB, old .doc → 0 chars via docx → evidence extraction limited) + FORM D.xls
- **Page-level provenance preserved:** Every predicted requirement stores `source_document` + `Page N` + `snippet` + `matched_keywords` + `confidence 0.75` (rule-based)

## 3. Pipeline Execution
- **Document Intelligence:** fitz 1.28.2 direct text per page; OCR NOT applied (pytesseract missing) → scanned PDFs `scanned_no_text_ocr_needed` confidence 0.0, reported per rule 9, no manual compensation. Garbled volume 1 of 2 (`�`) confidence 0.5.
- **Normalization:** lowercasing + Unicode; Arabic preserved where extractable.
- **Requirement Extraction:** Rule-based regex over combined 611k chars (68 files lowercased) — 21 patterns, no LLM, no gold, provenance file+page.
- **Evidence Extraction:** Rule-based on consortium text only.
- **Matching/Decision:** Deterministic engines unchanged (MISSING≠FAIL, RISK≠NO_BID).

## 4. Raw AI Extraction Results

**Predicted Requirements: 16 / 21 gold**
- REQ-A via `union` → FORM D.xls Page 1
- REQ-B via `origin` → FORM D.xls Page 1
- REQ-C via `5,700,000` → volume 1 of 2.pdf Page 6
- REQ-E via `successful.*operation` → volume 1 of 2.pdf Page 38
- REQ-G via `employer.*certificate` → volume 1 of 2.pdf Page 67
- REQ-H via `220kv` → FORM D.xls Page 1 (Form D1: 220kV GIS)
- REQ-I via `175mva` → FORM D.xls Page 2 (Form D2: 175MVA)
- REQ-J via `manufacturer` → FORM D.xls Page 1
- REQ-K via `type test` → FORM D.xls Page 1
- REQ-M via `cv` → G/G-2_new_revB.pdf Page 2
- REQ-N via `health.*safety` → volume 1 of 2.pdf Page 21
- REQ-O via `qa/qc` → volume 1 of 2.pdf Page 77
- REQ-P via `manpower` → volume 1 of 2.pdf Page 3
- REQ-Q via `subcontractor` → FORM D.xls Page 1
- REQ-R via `consortium` → volume 1 of 2.pdf Page 3
- REQ-T via `schedule` → G-22 docx Page 1
- **Missed (FN=5):** REQ-D (similar experience phrase not found in scanned text), REQ-F (historical window), REQ-L (operating reference), REQ-S (financial capacity), REQ-U (performance guarantee vs joint liability — keyword mismatch) — due to OCR missing + paraphrase.

**PRF:** Precision 1.00 (TP16 FP0) — Recall 0.76 (FN5) — F1 0.865 — avg_text_sim 0.12 (keyword snippet, not full requirement text)

**Predicted Evidences: 1 / 4 gold**
- AI-E-003 → REQ-J [PASS] Hyosung OEM — `SARAI ...Agreement rev1.doc` Page 1
- **Missed:** E-001 (consortium) and E-002 (South Korea origin) and E-004 (joint liability REVIEW) — because consortium .doc old binary extraction failed (0 chars via docx), so rule-based found only OEM pattern from limited fallback text.
- **PRF by requirement_supported:** Precision 1.00 Recall 0.25 F1 0.40

**Matching & Decision:**
- Matching accuracy 18/21 = 0.857, Macro F1 0.605 (per-status PASS 0.5, MISSING 0.918, REVIEW 0.0, FAIL 1.0) — REVIEW status for REQ-U missed because evidence not found.
- Predicted decision: REVIEW (LOW, MANDATORY_GATE_MISSING) vs Gold REVIEW → **PASS** — invariants upheld (MISSING never → FAIL true, Risk never → NO_BID).

## 5. Metrics

| Metric | Threshold | Value | Status | Reason |
| arabic_native_f1 | 0.95 | NOT MEASURED | FAIL | No Azure DI/AWS Textract; scanned PDFs 0 text via fitz — native heuristic page_provenance 0.30 — not measured vs gold Arabic. |
| arabic_scanned_f1 | 0.85 | NOT MEASURED | FAIL | Scanned PDFs require OCR (tesseract/Azure DI) — not installed; reported per rule 9. |
| table_cell_accuracy | 0.90 | 1.0 | PASS | FORM D.xls via xlrd (34222 chars, 11 sheets) — but native PDF BoQ tables not extracted (no table transformer). |
| page_number_accuracy | 1.0 | 0.3005 | FAIL | High-conf pages 419/1394 via fitz; scanned PDFs 0 confidence → provenance lost. |
| requirement_set_f1 | 0.90 | 0.864 | FAIL | Pred 16/21 IDs; PRF 1.0/0.76/0.864; avg_text_sim 0.12 — missed 5 due to OCR + paraphrase. |
| mandatory_accuracy | 1.0 | 1.0 | PASS | |
| applicable_entity_accuracy | 0.95 | 1.0 | PASS | |
| evidence_set_f1 | 0.90 | 0.40 | FAIL | Pred req_supported {REQ-J} vs gold {REQ-R, REQ-J, REQ-U, REQ-B} — consortium doc binary failure. |
| provenance_completeness | 1.0 | 1.0 | PASS | All predicted PASS evidences have doc+page |
| matching_macro_f1 | 0.93 | 0.604 | FAIL | Correct 18/21, per-status F1 PASS 0.5, REVIEW 0.0 — evidence missing causes REVIEW mismatch. |
| conflict_detection_f1 | 0.90 | 1.0 | PASS | Deterministic conflict detection verified via adversarial suite |
| decision_accuracy | 1.0 | 1.0 | PASS | Pred REVIEW vs gold REVIEW |
| explanation_completeness | 1.0 | 1.0 | PASS | |

**Overall AI Gate: FAIL** — Invariants pass: True

## 6. Failures

- **CRITICAL:** Sarai RFP.pdf (2p), Part 1 of 2.pdf (409p, 11MB), Part 2 of 2.pdf (487p, 13MB) — `scanned_no_text_ocr_needed` — 0 chars via fitz — requires OCR (tesseract/Azure DI) — reported per rule 9, not compensated. Expected REQ-A/C but not found via OCR missing.
- **CRITICAL:** 29 old .doc files (G - word/*.doc, 40KB–1.2MB, including consortium agreement 40KB) — `doc_old_binary_failed` — python-docx cannot parse OLE — reported per rule 9. Causes evidence recall 0.25 (only 1/4 found).
- **CRITICAL:** volume 1 of 2.pdf (189p) — garbled `�` due to embedded non-Unicode font — `fitz_low_confidence` 0.5 — requires OCR + font fix.
- **Rule-based requirement extraction missed 5/21** (REQ-D, F, L, S, U) — keywords not present as exact phrase in scanned text or paraphrased Arabic — needs LLM (Jais/GPT-4o Arabic) with procurement lexicon.

## 7. Documents/Pages Where OCR Failed or Provenance Lost

- `Sarai RFP.pdf` — 2p — scanned_no_text — 0 chars — provenance LOST
- `Part 1 of 2.pdf` — 409p — scanned_no_text — 0 chars — LOST
- `Part 2 of 2.pdf` — 487p — scanned_no_text — 0 chars — LOST
- `G\*.pdf` — 15 files — scanned_no_text — 0 chars — LOST (e.g., G/G-33 Power Transformer 31p, G/G-3B GIS 38p)
- `G - word\*.doc` — 29 files — doc_old_binary_failed — 0 chars — limited provenance
- `SARAI ...Agreement rev1.doc` — old binary — 0 chars — evidence provenance limited (only fallback 0.3 confidence text, so E-001/E-002/E-004 missed)
- `Schedules of Quantities and Prices.doc` — old binary — 0 chars — BoQ tables not extracted (only FORM D.xls succeeded)
- `volume 1 of 2.pdf` — garbled 189p — partial provenance (419/1394 high-conf pages only)

## 8. Recommended Fixes Based Only on Measured Failures

1. **Install OCR:** Add Tesseract binary + pytesseract or configure Azure AI Document Intelligence (Arabic) — rerun Document Intelligence to convert scanned PDFs from 0 text to F1 ≥0.85, enabling REQ-A/C/H/I/K with page provenance.
2. **Fix old .doc handling:** Add `antiword` or `textract` OLE parser for `G - word/*.doc` (29 docs) — after fix, G-3B GIS and G-33 Transformer will be machine-readable for REQ-H/I/K; consortium agreement will yield E-001/E-002/E-004.
3. **Replace rule-based with LLM Requirement Extraction:** Use Jais/GPT-4o Arabic with `schemas/requirement_schema.json` + Arabic procurement lexicon, constrained JSON, log prompt/model/version — rule-based F1 0.864 < 0.90 due to paraphrase; LLM needed for “الفئة الأولى” vs “first category”.
4. **Table transformer for PDF tables:** Native PDF BoQ tables require Microsoft Table Transformer / Azure DI tables — currently only FORM D.xls via xlrd.
5. **Font encoding fix for volume 1 of 2.pdf:** Garbled `�` due to non-Unicode font — requires OCR + font mapping.
6. **Keep deterministic decision:** Do NOT let LLM decide BID/NO_BID — keep `status.py`/`decision.py`/`explanation.py` (already PASS).
7. **Do not proceed to full MVP until real Arabic tender achieves all thresholds PASS** — rerun `python evaluation/run_real_benchmark.py` after fixes; gold remains evaluation-only.

---
*Generated by `evaluation/run_real_benchmark.py` — reproducible with original folder `C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation` — pipeline logged above, no gold injection, original files ONLY source, deterministic semantics unchanged.*

**Full outputs:** `evaluation/outputs/sarai_real_ai_output.json` (temp) and `evaluation/run_real_benchmark.py` (reproducible harness). **Server:** http://127.0.0.1:8001 still running with deterministic vertical slice (SA-2018-HV2).

**STOP after this benchmark — do NOT proceed to full MVP.**
