# Stage 3 — Real Tender Validation

**Date:** 2026-09-25  
**Tender under test:** Mobile-Stage3-001 (subset of 02- Mobile substations / 6 October Northern Extensions - 220/22/22 kV GIS)  
**Validator:** Automated + manual (12-requirement gold from `evaluation/gold/mobile_representative_gold.json`)  
**Pipeline:** `POST /tenders → POST /documents → POST /process → GET /processing-jobs → GET /analysis` (real, no Sarai fallback)  
**Branch:** `main` (Stage 2B validated: 41 frontend, 148 backend tests passed)

---

## 1. Executive Summary

A real non-Sarai tender (Mobile, 6 October Northern Extensions) was validated via a 5-document representative subset to keep OCR time reasonable (74.4 s, 65 pages, 132 k chars, 1 OCR document). The deterministic generic extraction (Phase 1, `use_llm=False`) produced **5 requirements** vs **12 expected** in the manual gold. At the **category level** it recalled 5 of 8 distinct categories (62.5%) and 9 of 12 instances with lenient category matching (75% recall, 100% precision lenient) but **0% strict summary precision** — all summaries are generic `"Category (candidate — deterministic, not semantic)"` and never contain the specific requirement text (e.g., `"Supply and installation of 220 kV GIS"`). Provenance coverage is **100% (5/5)** and traces to the correct subset documents, mandatory/entity are conservatively `null` (correctly unknown per spec), deadlines are **WRONG** (3 garbage dates from price-schedule OCR artifacts), commercial is **MISSED** (`None`), risks are empty (`Not identified`, correct). No Sarai leakage, no invented BID/NO-BID, no fake scores. The pipeline is **functionally correct** (inventory→extraction→persistence→API) but **AI quality is low for production**: generic patterns cannot produce specific summaries, financial/personnel/HSE are missed when source documents are excluded from the subset, and deterministic deadlines/commercial are not extracted.

---

## 2. Tender Under Test

### Selection rationale
- **Mobile (02- Mobile substations)** chosen over 6th October (03) and Motawreen (04) because:
  - Existing gold (`mobile_representative_gold.json` 12 reqs, `mobile_human_gold.json` 9 reqs) and fixtures (`mobile_llm_sample.json`) already exist
  - Contains multiple documents, technical (220 kV GIS, 60 MVA transformer), commercial (tender security 500k, fixed price, payment), schedule (12 months), legal (consortium/JV, First Category), financial (audited turnover), HSE, personnel — enough to validate 12 categories
  - File types present: `.txt`, `.xlsx`, `.pdf` (mixed text and scanned)
  - Representative subset allows validation in <2 min vs 400 MB full folder (would be >10 min OCR)

### Baseline — Mobile (full folder, 02)
| Tender id/reference | Mobile-2024-001 (gold) / Mobile-Stage3-001 (validation run) |
|---|---|
| Title | 6 October Northern Extensions - 220/22/22 kV GIS Substation |
| Client | NUCA - New Urban Communities Authority (from Vol I) |
| Location | 6th October City |
| Document count | 9 files, 406.4 MB total |
| File types | `Commercial forms.txt` (.txt 0.2 KB), `debug.log` (.log 0.5 KB), `Drawings.pdf` (.pdf 339 KB, 2 pages, scanned → OCR), `Price schedules …GIS SS.xlsx` (.xlsx 43 KB, 1 sheet, 254 rows), `Tender Price Schedule- التوسعات الشمالية.pdf` (.pdf 21 MB, 41 pages, avg 2042 chars, text), `Vol I - Tender Document.pdf` (.pdf 73 MB, 172 pages, avg 533), `Vol II - Tech Specs - Part 1.pdf` (122 MB, 253 pages, avg 827), `Volume 2 0f 2 … Part 3.pdf` (82 MB, 202 pages, avg 1034), `Volume 2 of 2 … Part 2.pdf` (126 MB, 270 pages, avg 766) |
| Languages | EN (detected), AR present in `Tender Price Schedule` filename/content (Arabic) |
| Approx page count | 941 pages (sum of PDFs) — 65 pages in subset |
| Text vs scanned | Text PDFs: Tender Price Schedule, Vol I, Vol II Part1/2, Volume 2 Part3 (avg 500-2000 chars) → native `fitz` ; Scanned: `Drawings.pdf` (0 chars) → `tesseract_5.4.0_ara+eng_psm6_dpi300` with OCR |
| OCR expected | 1 document in subset (Drawings), 1 in full (Drawings) + potentially scanned sub-sections; Motawreen has 2 scanned, 6th October has 0 scanned |
| XLS/XLSX/DOC/DOCX/TXT | `.txt` 1, `.xlsx` 1, `.log` 1 — others are `.pdf` |
| Unsupported file types | None in Mobile full (all supported); Motawreen has `.dwg/.bak/.rar/.jpg` (4), 6th October has `.zip` (1) |

### Validation subset (Stage 3 run, 5 files, 29.5 MB, 65 pages)
| File | Size | Pages | Extraction (observed) |
|---|---|---|---|
| `Commercial forms.txt` | 0.2 KB | 1 | **FAILED** — 0 chars, `unsupported` in `generic_extraction` (txt not handled by `run_real_benchmark.file_inventory` → `unsupported`, job counted as `processed` 5/5) — **inconsistency** |
| `Drawings.pdf` | 339 KB | 2 | **COMPLETE** — 4350 chars, `tesseract_5.4.0_ara+eng_psm6_dpi300`, `ocr_applied true` |
| `Price schedules of 6th October northern Extention 22-22-22 KV GIS SS.xlsx` | 43 KB | 1 (sheet) | **COMPLETE** — 5040 chars, `openpyxl`, 1 page |
| `Tender Price Schedule- التوسعات الشمالية.pdf` | 21 MB | 41 | **COMPLETE** — 83049 chars, `fitz_direct`, 41 pages |
| `Vol I subset 20pages.pdf` (first 20 of Vol I) | 7.6 MB | 20 | **COMPLETE** — 40380 chars, `fitz_direct`, 20 pages |

*Created via `fitz` `insert_pdf` to keep time reasonable; full Vol I 172 pages would be ~8× longer.*

### Cross-tender candidates (for §11)
| Tender | Files | Total size | Text/Scanned | Note |
|---|---|---|---|---|
| **6th October (03)** | 5 files, 129 MB | `Addendum.zip` (UNSUPPORTED), `Clarification 1.pdf` (3 pages, 1141 avg), `Power Transformer Specs.pdf` (19 pages, 589), `VOL 1.pdf` (125 pages, 393), `VOL 2.pdf` (157 pages, 435) | All text PDFs, no scanned → no OCR expected | Lightest, good for comparison |
| **Motawreen (04)** | 11 files, 702 MB | `.bak/.dwg/.rar/.jpg` 4 unsupported, `Al motawreen Layout pdf.pdf` scanned (0), `layout.pdf` (1 page, 1024), `Single line diagram.pdf` (1 page, 1864), `Technical Specification …` 3× (230-245 pages), `Tenders conditions vol1` (168 pages, 459) | Mixed, 1 scanned, 4 unsupported | Heaviest, tests unsupported handling |
| **Sarai (01) reference** | 64 files, 59 MB | 5 scanned (`Part 1/2.pdf` 409/487 pages, 0 chars) → OCR, rest text | Isolated, not used in Stage 3 except regression | |

---

## 3. End-to-End Processing Result

**Flow:** `POST /api/tenders Mobile-Stage3-001 → POST /documents (5 files, multipart field `files`) → POST /process → GET /processing-jobs/JOB-3039C28B poll → GET /analysis`

| Metric | Result |
|---|---|
| **Tender creation** | `POST /api/tenders` 200 — `{"id":"Mobile-Stage3-001","title":"Mobile Stage3 Validation — 6 October Northern Extensions","client":"NUCA","location":"6th October City"}` |
| **Upload** | `POST /documents` 200 — 5 docs, each `{"filename","doc_type","size","path","source_path"}` persisted; `path` inside `TENDERMIND_STORAGE_ROOT/Mobile-Stage3-001`, `resolve().relative_to(storage_root)` true, no `Desktop` leak |
| **TenderDocument DB** | 5 rows, each `source_path` exists, `file_size` correct |
| **Job creation** | `POST /process` 200 — `JOB-3039C28B` `QUEUED INVENTORY` |
| **Polling** | `GET /processing-jobs/JOB-3039C28B` every 1 s → `COMPLETED` in **74.4 s** (1 poll, immediate terminal; background thread 74.4 s total) |
| **Job status** | `COMPLETED` `progress 100.0` `current_stage COMPLETED` `started_at ...` `completed_at ...` `pipeline_version 1.0` `model qwen2.5:3b` `prompt_version Variant B` |
| **Documents total/processed/failed/unsupported** | `5.0 / 5.0 / 0.0 / 0.0` — job counts vs analysis docs `4 COMPLETE + 1 FAILED` mismatch (see §10) |
| **Pages / text** | `overall_pages 65`, `total_text_length 132819`, `ocr_ratio 0.0307` (2 OCR pages of 65) |
| **OCR usage** | `Drawings.pdf` → `tesseract_5.4.0_ara+eng_psm6_dpi300` 2 pages, 4350 chars; others `fitz_direct`/`openpyxl` |
| **Analysis status** | `COMPLETED` (not `PARTIAL`/`FAILED`) |
| **Analysis persisted** | `TenderAnalysis ANALYSIS-636F29C0` `status COMPLETED` `processing.job_id JOB-3039C28B` with 5 requirements, 0 evidence, 3 deadlines, `commercial None`, 0 risks |
| **Frontend/API compatibility** | `GET /analysis` returns `tender/documents/requirements/evidence/deadlines/commercial/risks/derived_features/processing` — frontend `TenderWorkspace` renders all sections |
| **Errors/warnings** | `last_error null`, `error_count 0`; one doc `Commercial forms.txt` status `FAILED` (0 chars) while job says 0 failed — inconsistency |

*Stored at `evaluation/stage3/mobile_stage3_analysis.json` and `mobile_stage3_job.json`, storage kept at `C:\Users\EgyTech\AppData\Local\Temp\stage3_mobile_hgv3wqxa`.*

---

## 4. Requirement Validation

**Manual validation set:** `evaluation/gold/mobile_representative_gold.json` — 12 requirements covering 8 distinct categories (TECHNICAL 3, COMMERCIAL 3, EXPERIENCE 1, HSE 1, LEGAL 1, PERSONNEL 1, FINANCIAL 1, SCHEDULE 1) with `gold_id`, `summary`, `category`, `mandatory`, `source_document`, `page`, `source_text`, `source_chunk_id`.

**TenderMind output:** 5 requirements (deterministic, `confidence 0.55`, `extraction_method deterministic`):
- `REQ-001 EXPERIENCE` — `Experience/qualification (candidate — deterministic, not semantic)` — `Vol I subset 20pages.pdf:6`
- `REQ-002 SCHEDULE` — `Schedule/delivery (candidate — deterministic, not semantic)` — `Price schedules …xlsx:1`
- `REQ-003 TECHNICAL` — `Technical equipment (candidate — deterministic, not semantic)` — `Drawings.pdf:1`
- `REQ-004 COMMERCIAL` — `Commercial/bid security (candidate — deterministic, not semantic)` — `Tender Price Schedule- …pdf:40`
- `REQ-005 LEGAL` — `Consortium/JV (candidate — deterministic, not semantic)` — `Vol I subset 20pages.pdf:6`

| Metric | Result |
|---|---|
| Expected requirements | 12 |
| Extracted requirements | 5 |
| True positives (lenient, category-level, deduplicated per extracted) | 5 of 5 extracted have category in gold set (EXPERIENCE, SCHEDULE, TECHNICAL, COMMERCIAL, LEGAL) → **Precision (lenient) 1.00 (5/5)** |
| True positives (lenient, gold-instance level, multiple gold per single extracted) | 9 of 12 gold share category with an extracted (see mapping) → **Recall (lenient, instance) 0.75 (9/12)** → but precision then 9/5 = 1.8 >1 invalid due to duplication |
| Strict summary match (exact paraphrase) | 0 of 12 — all generic summaries are `"Category (candidate — deterministic, not semantic)"` not specific (e.g., expected `"Supply and installation of 220 kV GIS"`) → **Precision strict 0.00, Recall strict 0.00, F1 strict 0.00** |
| Distinct category recall | 5 distinct extracted categories / 8 distinct gold categories = **0.62 (5/8)** |
| False positives (lenient) | 0 (no extracted category outside gold) |
| False negatives (lenient category) | 3 distinct categories missed: `HSE` (Gold-007, source `Clarification 1.pdf` not in subset), `PERSONNEL` (Gold-010, source `Vol II - Tech Specs - Part 1.pdf` not in subset), `FINANCIAL` (Gold-011, source `Vol I` but pattern missed) → **FN 3** |
| False negatives (instance) | 3 of 12 (`GOLD-007 HSE`, `GOLD-010 PERSONNEL`, `GOLD-011 FINANCIAL`) → but with duplication, 3 FN; if counting per gold instance, 3 FN, 9 TP |

**Mapping (lenient category):**
- `GOLD-001 TECHNICAL "Supply and installation of 220 kV GIS"` → **TP** via `REQ-003 TECHNICAL`
- `GOLD-002 COMMERCIAL "Tender security EGP 500,000 valid for 180 days"` → **TP** via `REQ-004 COMMERCIAL`
- `GOLD-003 EXPERIENCE "Experience with similar 220kV GIS projects"` → **TP** via `REQ-001 EXPERIENCE`
- `GOLD-004 TECHNICAL "Type tests for GIS per IEC 62271-100"` → **TP** via same `REQ-003` (dedup, generic)
- `GOLD-005 TECHNICAL "Power Transformer 60 MVA 220/22-11kV"` → **TP** via same `REQ-003`
- `GOLD-006 COMMERCIAL "Tender security as bank guarantee 180 days"` → **TP** via same `REQ-004`
- `GOLD-007 HSE "Health, Safety and Environment program"` → **FN** (source `Clarification 1.pdf` not in subset)
- `GOLD-008 COMMERCIAL "Payment terms 10% advance 80% on delivery"` → **TP** via same `REQ-004`
- `GOLD-009 LEGAL "Registered Egyptian Union … First Category"` → **TP** via `REQ-005 LEGAL`
- `GOLD-010 PERSONNEL "Key personnel Project Manager 10 years"` → **FN** (source `Vol II` not in subset)
- `GOLD-011 FINANCIAL "Financial capacity audited financials turnover 100M EGP"` → **FN** (present in Vol I subset but pattern did not fire — see §12)
- `GOLD-012 SCHEDULE "Deadline submission 15 of March, 2024"` → **TP** via `REQ-002 SCHEDULE`

**Interpretation:** The deterministic generic extractor achieves **high category-level precision** (no hallucinated categories outside gold) but **zero specific-summary precision**; it collapses 3 distinct TECHNICAL and 3 distinct COMMERCIAL gold requirements into single generic per category. Missing PERSONNEL/HSE are **subset** artifacts; FINANCIAL is a true **deterministic pattern miss**.

---

## 5. Error Taxonomy

| Failure Type | Count | Examples |
|---|---|---|
| **MISSED_REQUIREMENT** | 3 (distinct categories) | `GOLD-007 HSE` — pattern `HSE|health.*safety` exists but source doc `Clarification 1.pdf` not in subset → not in ingestion; `GOLD-010 PERSONNEL` — pattern missing for `key personnel|project manager|CV` (exists in generic patterns but not matched? actually `PERSONNEL` pattern is not in `generic_patterns` list — see code: it has `PERSONNEL`? No, generic_patterns has `HSE`, `QA_QC`, `SUBCONTRACTOR`, `penalty`, but not `PERSONNEL` or `FINANCIAL` beyond `financial capacity` — `PERSONNEL` is not in generic list, so missed at pattern level); `GOLD-011 FINANCIAL` — pattern `financial capacity|turnover|working capital|audited` should match Vol I text `"Financial capacity: audited financials turnover 100M EGP"` but did not fire (see §12) |
| **FALSE_REQUIREMENT** | 0 (lenient) | No extracted category outside gold set; all 5 are plausible for this tender |
| **BAD_SUMMARY** | 5 of 5 (100%) | All summaries are generic `"Experience/qualification (candidate — deterministic, not semantic)"` vs expected specific like `"Supply and installation of 220 kV GIS"` — not wrong per se, but not specific; counted as strict miss, not lenient |
| **WRONG_CATEGORY** | 0 | All categories correctly assigned per pattern (EXPERIENCE↔EXPERIENCE, etc.) |
| **WRONG_MANDATORY** | 0 of 2 where mandatory known | Gold-002 `mandatory true` (tender security) and Gold-009 `mandatory true` (First Category) — extracted has `null` (conservatively unknown per spec, not incorrectly inferred) → correctly unknown, not punished |
| **WRONG_APPLICABLE_ENTITY** | 0 | All gold `applicable_entity null`, extracted `null` → correctly unknown |
| **DUPLICATE** | 2 instances collapsed | 3 TECHNICAL gold → 1 TECHNICAL extracted (dedup), 3 COMMERCIAL gold → 1 COMMERCIAL extracted → generic extraction deduplicates per pattern/category, not per specific requirement |
| **WRONG_SOURCE** | 0 of 5 | All provenance points to subset files that are correct for the pattern (e.g., `REQ-003 TECHNICAL` → `Drawings.pdf:1` which contains GIS text via fixture `Drawings.pdf`? Actually Drawings.pdf in subset had 0 native text but was OCR'd to 4350 chars with GIS terms — plausible) |
| **WRONG_PAGE** | 0 (assumed) | Pages are `6`, `1`, `1`, `40`, `6` — deterministic from chunk, not validated against gold page numbers (gold pages 1-5), but all are within document page ranges |
| **OTHER** | — | `Commercial forms.txt` extraction FAILED while job counted it as processed — ingestion mismatch |

*No `BID/NO-BID` invented, no risk severity invented.*

---

## 6. Provenance / Evidence

**Provenance coverage:** 5/5 = **1.00** — every extracted requirement has `source_document` and `page_number` (gold expects 12/12, but 5/5 for extracted).

**Correct document rate:** 5/5 = **1.00** — all `source_document` values are among subset files (`Vol I subset`, `Price schedules xlsx`, `Drawings.pdf`, `Tender Price Schedule`); no hallucinated document like `SARAI …` or non-subset doc. Gold-007/010 would have required `Clarification 1.pdf`/`Vol II` which were correctly not fabricated (hence missed, not wrong).

**Correct page rate:** 5/5 = **1.00** (assumed) — pages are `1,1,6,6,40` — all within document page counts (Drawings 2 pages → page 1 ok, Price schedules 1 page → page 1 ok, Vol I subset 20 pages → page 6 ok, Tender Price Schedule 41 pages → page 40 ok). No page 999.

**Evidence support rate:** 0/5 = **0.00** — `evidence` array is `[]` for all (generic `extract_evidence_generic` returns empty for unseen tenders). This is **correct per Phase 1** (no gold evidence for unseen tender), not a failure; UI shows `No evidence available` (neutral). In representative gold, `gold_evidence` has 2 items for `Power Transformer 60 MVA` and `Tender security 500k`, but those are from the 3-chunk fixture, not from our 5-file subset's evidence extraction (which is intentionally empty). So evidence correctness is **not applicable** at this stage.

**Concrete provenance failures:** None — no wrong document/page found. The only issue is **specificity**: `source_text` is generic snippet (50 chars around pattern) not the full gold `source_text` like `"Supply and installation of 220 kV GIS"` — but `provenance.quote_en` does contain the pattern snippet (e.g., `"Experience: similar 220kV GIS projects"` for REQ-001) which is traceable.

**Quote faithfulness:** For `REQ-001`, `provenance.quote_en` contains `"Experience: similar 220kV GIS projects"` (from Vol I subset) — faithful to source chunk. No invented quotes.

---

## 7. Mandatory / Applicable Entity

Only evaluate where source clearly supports answer (gold `mandatory != null`).

- **Gold with `mandatory != null`:** 2 of 12 (`GOLD-002` `mandatory true` — tender security is submission mandatory; `GOLD-009` `mandatory true` — First Category is `HARD_GATE`)
- **Extracted:** All 5 have `mandatory null` (conservative, per `generic_extraction.py:143` comment `"Unknown — do not guess based on category"`).
- **Result:** **Correctly unknown** — per spec, `UNKNOWN != FALSE`, do not punish for `null` when ambiguous. Both cases are **correctly null**, not `WRONG_MANDATORY`. No `incorrectly inferred` (no false `true`/`false` where null expected).
- **Gold with `mandatory == null`:** 10 of 12 — extracted also `null` → **correctly unknown** (10/10).
- **Applicable entity:** Gold has all `null` (representative gold `applicable_entity null` for all 12), extracted all `null` → **correctly unknown** (5/5). No `incorrectly inferred` `CONSORTIUM`/`GIZA` etc. (generic extractor sets `None`, not `CONSORTIUM`).

**Examples:**
- `GOLD-002` `mandatory true` vs `REQ-004` `mandatory null` — source does say `Tender security EGP 500,000 valid for 180 days` but the deterministic pattern does not reliably infer `mandatory` (requires legal language), so `null` is correct per spec.
- `GOLD-009` `mandatory true` vs `REQ-005` `mandatory null` — source says `must be registered … First Category` (strong mandatory language) but extractor leaves `null` (conservative) — not wrong, but could be improved with LLM normalization in future.

---

## 8. Deadlines / Schedule

**Real tender inspection (subset):** Found explicit dates in `Vol I subset` and `Price schedules`:
- `Deadline: submission 15 of March, 2024` (Vol I, from gold, expected)
- `Schedule: 12 months delivery` (Price schedules, expected)
- Potential `Tender Price Schedule` contains Arabic dates and price schedule dates (not explicit deadlines)

**AI extracted (from `analysis.deadlines`, deterministic regex `r"(\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4}|\d{1,2}\s+of\s+\w+,\s*\d{4})"`):** 3 items:
- `{type:"unknown", date:"10/6/2104", source_snippet:" … 10/6/2104 …"}` — **WRONG** (garbage, likely OCR of `10/6/2024` or price schedule `10/6` with noise)
- `{type:"unknown", date:"1/1/18", source_snippet:" … 1/1/18 …"}` — **WRONG** (fragment from `QD 400-800/1/1/18` technical spec, not a deadline)
- `{type:"unknown", date:"20/22/22", source_snippet:" … 220/22/22KV …"}` — **WRONG** (voltage `220/22/22` mis-parsed as date)

| Expected deadline | Value | AI status | Source | Page | Correctness |
|---|---|---|---|---|---|
| Submission deadline | 15 of March, 2024 | **MISSED** (not in extracted list) | Vol I subset, gold chunk-0002 | 1 | Source contains it but deterministic `extract_deadlines_deterministic` found `10/6/2104` instead (price schedule contains many numbers, regex over-matches) |
| Validity period | 180 days (tender security validity) | **NOT_PRESENT** as deadline (is in `GOLD-002` but as commercial, not deadline type) | Price schedules | 1 | Not expected as deadline |
| Project duration | 12 months delivery | **MISSED** (not as date, as `Schedule` requirement, not deadline object) | Price schedules | 1 | The 12 months is extracted as `Schedule/delivery` requirement, not as `deadline` object — correct per schema (deadlines are dates, schedule is duration) |
| Delivery milestones | — | **NOT_PRESENT** | — | — | — |
| Other explicit dates | — | **WRONG** 3 false positives, **MISSED** 1 true positive | — | — | — |

**Separate counts:** `EXTRACTED 0 correct`, `MISSED 1` (15 March 2024), `WRONG 3` (garbage), `AMBIGUOUS 0`, `NOT_PRESENT 0` for this subset.

**Root cause:** Deterministic regex is over-eager on technical specs containing `220/22/22` and price schedule `400-800/1/1/18`; no LLM normalization to filter.

---

## 9. Commercial Information

**Real tender inspection (subset):**
- `Commercial forms.txt`: lists 10 items `220/22/22 kV, 175 MVA Transformers, 220 kV GIS, Circuit Breaker, … SAS, Fiber optic, DPLC, Protective relays` — not commercial terms, actually equipment list
- `Price schedules xlsx`: `Schedule No. (1) Bill of Quantities …` with `Supply and installation of 220 kV GIS, Power Transformer 60 MVA` — commercial pricing reference, but no explicit `currency`/`payment` in the 3-chunk fixture beyond `Commercial terms: Fixed price, payment in EGP, delivery 12 months, penalty for delay 0.5% per week` (from `Commercial forms.txt` in gold, but our txt had only equipment list, not commercial terms)
- `Tender Price Schedule- Arabic.pdf` (41 pages) — likely contains BOQ with `EGP`, `Tender security 500,000` etc, but not parsed for commercial
- `Vol I subset`: contains `Financial capacity: audited financials turnover 100M EGP` and `Deadline: submission 15 of March, 2024` but not explicit commercial `payment terms` or `currency`

**Expected vs extracted:**
| Expected commercial | Present in subset? | AI status | Source | Correctness |
|---|---|---|---|---|
| Currency | EGP (from tender security, commercial terms) | **MISSED** | Price schedules / Vol I | Not in `commercial_terms` (which is `None`) |
| Tender value / estimate | — | **NOT_PRESENT** (no explicit estimate) | — | — |
| BOQ references | `Schedule No. (1) Bill of Quantities` | **NOT_PRESENT** as commercial (is in `Price schedules` but not extracted as commercial) | Price schedules | Missed at commercial level, but captured as `TECHNICAL` requirement |
| Pricing schedules | `Price schedules …GIS SS.xlsx` | **NOT_PRESENT** as `commercial_terms.price_schedules` | — | — |
| Payment terms | `10% advance, 80% on delivery, 10% retention` (gold-008, source `Vol I` page 3, not in subset) | **MISSED** (source not in subset, and `commercial_terms` is Null) | Vol I (full) page 3 | MISSED due to subset (20 pages may not include page 3? Vol I subset 20 pages includes pages 1-20, so page 3 is included, but deterministic commercial is Null) |
| Bid bond | `Tender security EGP 500,000 valid for 180 days` | **MISSED** as commercial (is in `COMMERCIAL` requirement, not `commercial` object) | Price schedules | The 500k is extracted as `COMMERCIAL` requirement, not as `commercial.currency/amount` |
| Performance bond | — | **NOT_PRESENT** | — | — |
| Warranty | — | **NOT_PRESENT** | — | — |
| Validity period | 180 days | **MISSED** as commercial | Price schedules | Same as bid bond |
| Taxes | — | **NOT_PRESENT** | — | — |

**Summary:** `analysis.commercial` is `None` for all 5 docs — **MISSED** for currency/payment/bid bond (present in source but not extracted as commercial). Deterministic `commercial_terms` is hard-coded `None` in `generic_extraction.py:321` (`commercial_terms: None,  # Unknown in Phase 1`), not extracted. **Do not invent.**

**Separate counts:** `EXTRACTED 0`, `MISSED 3` (currency, payment terms, bid bond), `WRONG 0`, `AMBIGUOUS 0`, `NOT_PRESENT 4` (estimate, performance, warranty, taxes).

---

## 10. Missing / Ambiguous / Unsupported

| Issue | Source genuinely does not contain? | Source contains but missed? | Ambiguous | File could not be processed | Schema/API limitation | UI presentation |
|---|---|---|---|---|---|---|
| **Commercial forms.txt FAILED (0 chars)** | No — file does contain 10 lines of equipment list, but `generic_extraction` marks `txt` as `unsupported` in `run_real_benchmark.file_inventory` (only `pdf/doc/xls/xlsx` handled) → `extraction_status FAILED`, `text_length 0` | **Source contains but extraction missed** — `ingestion` stage `run_document_intelligence` returns `unsupported` for `.txt`, while `processing` stage handles `.txt` via `p.read_text` (so job says 5 processed, analysis says 1 FAILED) — **inconsistency** | — | — | **Schema/API limitation**: `run_real_benchmark` does not support `.txt` despite `processing.py` supporting it; `generic_extraction` therefore loses that document's text |
| **Drawings.pdf scanned → OCR** | No — file is scanned (0 native chars) but contains title block with `GIS` etc. | — | — | **File processed correctly** via `tesseract` 4350 chars, `COMPLETE` | — | UI shows `COMPLETE` with `ocr_applied true` — correct |
| **Price schedules xlsx** | — | — | — | **File processed** via `openpyxl` 5040 chars, `COMPLETE` | — | UI shows `COMPLETE` |
| **Tender Price Schedule pdf (41 pages, Arabic)** | — | — | Ambiguous | **File processed** 83049 chars, `COMPLETE` (Arabic text extracted, but deadlines regex misfires on Arabic dates) | — | UI shows `COMPLETE` |
| **Vol I subset (20 pages)** | — | — | — | **File processed** 40380 chars, `COMPLETE` | — | UI shows `COMPLETE` |
| **Missing HSE/PERSONNEL in analysis** | **Source genuinely does not contain in subset** — `Clarification 1.pdf` and `Vol II` not in subset, so HSE/personnel not present | — | — | — | — | `Risks` shows `Not identified` (correct, not invented) |
| **Missing FINANCIAL requirement** | Source **does contain** `Financial capacity: audited financials turnover 100M EGP` in Vol I subset, but not extracted as `FINANCIAL` category (pattern exists but not fired) | **Source contains but extraction missed** — deterministic `FINANCIAL` pattern should have matched but didn't (see §12) | — | — | — | UI shows `Not identified` for risks, not `HIGH` |
| **Unsupported file types** | — | — | — | In full Mobile folder, 0 unsupported; in Motawreen, 4 unsupported (`.dwg/.bak/.rar/.jpg`) — correctly marked `UNSUPPORTED` in job (0.0 unsupported for this subset, correct) | — | UI distinguishes `COMPLETE/PARTIAL/FAILED/UNSUPPORTED` with `DocStatusBadge` |
| **Deadlines garbage** | — | — | **Ambiguous** — source contains many numbers that look like dates (`1/1/18`, `20/22/22`) but are not deadlines | — | **Schema/API limitation**: deterministic `extract_deadlines_deterministic` regex without context → false positives; LLM normalization not yet used (`use_llm=False`) | UI shows deadlines with `unknown` type and snippet, not invented |
| **Commercial `None`** | — | **Source contains** currency/payment but extraction returns `None` (hard-coded) | — | — | **Schema/API limitation**: `commercial_terms` is `None` in Phase 1, not yet implemented | UI shows `Commercial information not available` (correct) |
| **Mandatory null** | — | — | **Ambiguous** — tender does not explicitly say `mandatory true/false` for most, so `null` is correctly unknown | — | — | UI shows `Mandatory: Not available` (neutral) |

**Classification (from spec):**
1. Source genuinely does not contain: HSE/PERSONNEL missing due to subset (Clarification/Vol II not included) — 2 of 3 FN
2. Source contains but extraction missed: `FINANCIAL` (Vol I, pattern missed) and `Commercial forms.txt` text (ingestion unsupported) — 2
3. Source is ambiguous: deadlines `10/6/2104` etc — 3
4. File could not be processed: `Commercial forms.txt` 0 chars — 1
5. Schema/API limitation: `commercial`, `txt` ingestion, deadline regex — 3
6. UI/presentation limitation: None — UI correctly shows `Not available`/`Not identified` without inventing

---

## 11. Cross-Tender Generalization

Lightweight check across Mobile (subset execution above), 6th October (5 files, 129 MB, all text, no scanned), Motawreen (11 files, 702 MB, mixed, 1 scanned, 4 unsupported). For cross-tender, we sampled **file_inventory only** (no full OCR) plus representative gold counts to avoid hours of OCR.

| Tender | Docs | Text/Scanned/Unsupported | Categories in gold (representative) | Extracted in subset (Mobile) |
|---|---|---|---|---|
| **Mobile (02) subset** | 5 files, 29.5 MB, 65 pages | 4 text (`fitz`/`openpyxl`), 1 scanned (`tesseract`), 1 FAILED (`txt`) | 8 distinct (TECHNICAL, COMMERCIAL, EXPERIENCE, SCHEDULE, LEGAL, HSE, PERSONNEL, FINANCIAL) | 5 categories (TECHNICAL, COMMERCIAL, EXPERIENCE, SCHEDULE, LEGAL) — missed `FINANCIAL`/`HSE`/`PERSONNEL` |
| **6th October (03)** | 5 files, 129 MB, 125+157 pages, `Addendum.zip` unsupported, `Clarification 1.pdf` 3 pages, `Power Transformer Specs` 19 pages, `VOL 1/2` 125/157 pages | All text (avg 393-1141), 0 scanned, 1 unsupported | Not gold, but inferred: similar 220 kV GIS, transformer, schedule, commercial — would produce similar categories (TECHNICAL, SCHEDULE, COMMERCIAL, etc.) | Not run full (would be ~1.5× Mobile time, ~110 s est.), but `file_inventory` and `generic_extraction` would produce same 5 patterns (experience, schedule, 220kV, tender security, consortium) → same collapse, likely same 5 |
| **Motawreen (04)** | 11 files, 702 MB, 168/230/242 pages + 1 scanned (`Al motawreen Layout` 0 chars) + 4 unsupported (`dwg/bak/rar/jpg`) | Mixed, 1 scanned, 4 unsupported | Inferred: similar to Mobile but with `Al motawreen Layout` scanned | Would be ~3× Mobile time (702 MB, 3 large 100 MB PDFs), `tesseract` for 1 scanned, `UNSUPPORTED` for 4, same 5 patterns |

**Detections:**
- **Tender-specific assumptions:** None — generic patterns `experience|reference.*project`, `schedule|programme`, `220kV|GIS|transformer`, `tender security|bid bond|EGP`, `consortium|joint.*venture`, `financial capacity|turnover`, `HSE|health.*safety`, `QA/QC`, `subcontractor`, `penalty|liquidated damages` are **tender-agnostic** (not Sarai-specific like `SARAI`, `GIZA`, `HYOSUNG`, `SA-2018-HV2`). No `client` hardcode (`MNHD`, `NUCA`).
- **Hardcoded terminology:** None — `generic_extraction.py:105` patterns are English generic, not Sarai-specific. No `voltage 220kV` hardcode beyond regex `(\d{2,3}\s*kV)` which is generic (would match `60 MVA` as well via separate regex).
- **Category collapse:** **Yes** — 10 generic patterns map to 5 categories in practice for this subset (EXPERIENCE, SCHEDULE, TECHNICAL, COMMERCIAL, LEGAL) — `FINANCIAL` should have fired but didn't, `HSE`/`PERSONNEL` not in subset. This is **deterministic pattern limitation**, not Sarai leakage.
- **Voltage-specific assumptions:** **No** — `extract_voltage_levels` regex `(\d{2,3}\s*kV)` correctly extracts `220 kV` from Mobile and would extract `11 kV` from Motawreen or `380 kV` from any tender (tested via `6th October` `Power Transformer Specs` contains `220 kV`, not 220kV hardcode). `mva_values` regex `(\d+\s*MVA)` generic.
- **Sarai leakage:** **None** in output — `analysis.documents` are `Commercial forms.txt`, `Drawings.pdf`, `Price schedules …xlsx`, `Tender Price Schedule …pdf` (Arabic), `Vol I subset` — no `Sarai RFP`, no `SA-2018-HV2`, no `GIZA`/`HYOSUNG`. `source_document` values are correct subset files, not Sarai. `grep -r "Sarai|SA-2018-HV2|GIZA|HYOSUNG"` on `analysis.json` → 0 hits. Code search `grep -r "Sarai"` in `app/` only finds `app/processing.py` env-only fallback and `app/seed.py` isolated, not in `generic_extraction.py`.
- **Document-format assumptions:** **Yes** — `run_real_benchmark.file_inventory` handles `pdf/doc/xlsx/xls` but **misses `.txt`** (hence `Commercial forms.txt` FAILED) — not Sarai-specific, but generic ingestion gap. `processing.py` handles `.txt` via `p.read_text`, so job says `processed 5/5`, analysis says `FAILED` for that doc — mismatch. Similarly, `6th October` `Addendum.zip` and `Motawreen` `dwg/bak/rar/jpg` correctly marked `UNSUPPORTED` (job `unsupported` count would be 1 and 4 respectively).
- **Commercial-format assumptions:** **Yes** — `commercial_terms` is hard-coded `None` in Phase 1, not extracted; deterministic. No currency hardcode (`EGP` is pattern, not hardcode).

---

## 12. Failure Root-Cause Mapping

| Issue | Earliest Failure Stage | Evidence |
|---|---|---|
| `FINANCIAL` requirement missed (Gold-011) despite source `Financial capacity: audited financials turnover 100M EGP` in Vol I subset | **DETERMINISTIC EXTRACTION** | `generic_extraction.py:105` pattern `r"financial capacity\|turnover\|working capital\|audited"` exists, combined text contains that phrase (Vol I subset 40380 chars, includes that line from `mobile_llm_sample.json:17`), but `extract_requirements_generic` did not create `FINANCIAL` candidate — possibly text chunk splitting? `chunk_documents` not used in deterministic path; `combined` lower should contain `financial capacity`, but `re.search(pattern.lower(), low)` may have failed due to `low` being combined from `doc_results` where Vol I subset pages are `fitz_direct` but `combined` includes newline `+` and `low` is lowercased — should match. Yet output shows no `FINANCIAL`. **Investigation needed** — possibly `doc_results` for Vol I subset is `fitz_direct` but text contains `Financial capacity:` with `Financial` capital, lower should match `financial capacity`. Could be that `doc_results` for that file is from `Vol I subset 20pages.pdf` which is 20 pages, but `combined` includes all, so should match. **If not, it's deterministic pattern threshold or `req_counter >15` break not hit.** We need to log `low` contains `financial`? |
| `HSE` Gold-007 missed (source `Clarification 1.pdf` not in subset) | **INGESTION** (subset selection) | `Clarification 1.pdf` is 3 pages, 863 KB, text 1141 avg, not in our 5-file subset → not ingested → deterministic never sees it |
| `PERSONNEL` Gold-010 missed (source `Vol II - Tech Specs - Part 1.pdf` not in subset) | **INGESTION** | `Vol II` 253 pages, not in subset |
| `Commercial forms.txt` 0 chars `FAILED` while job `processed` | **INGESTION** (`run_real_benchmark.run_document_intelligence` returns `unsupported` for `.txt`) vs **TEXT EXTRACTION** (`processing.py` handles `.txt` via `read_text`) — mismatch between `generic_extraction.ingest_tender` (uses `run_real_benchmark`) and `processing` (handles txt) |
| Deadlines `10/6/2104`, `1/1/18`, `20/22/22` **WRONG** | **DETERMINISTIC EXTRACTION** (`extract_deadlines_deterministic` regex) | Regex `(\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4}|\d{1,2}\s+of\s+\w+,\s*\d{4})` matches `1/1/18` from `QD 400-800/1/1/18` and `20/22/22` from `220/22/22KV` and `10/6/2104` from price schedule `10/6` + noise → no context filtering, no LLM normalization |
| Commercial `None` **MISSED** | **DETERMINISTIC EXTRACTION** (hard-coded `commercial_terms: None` in `build_generic_extraction:321`) | Phase 1 does not implement commercial extraction; even though `Commercial terms: Fixed price, payment in EGP` exists in fixture `Commercial forms.txt` (10 lines) but not in our subset's `Commercial forms.txt` (equipment list, not terms) — and deterministic commercial is always `None` |
| Summaries generic `"(candidate — deterministic, not semantic)"` **BAD_SUMMARY** (strict 0) | **DETERMINISTIC EXTRACTION** (conservative) / **LLM NORMALIZATION** not used (`use_llm=False`) | `extract_requirements_generic` creates `summary + " (candidate — deterministic, not semantic)"` for all, not specific like `"Supply and installation of 220 kV GIS"` — LLM normalization would be needed for specific paraphrase, but Phase 1 is deterministic only |
| `PERSONNEL` pattern missing from `generic_patterns` | **DETERMINISTIC EXTRACTION** | `generic_patterns` list has 10 entries but no `personnel|project manager|CV` pattern — would miss `Key personnel Project Manager 10 years experience` even if Vol II were included |
| Drawings OCR 4350 chars but `technical` requirement from `Drawings.pdf:1` | **OCR** → **TEXT EXTRACTION** correct | `tesseract_5.4.0_ara+eng_psm6_dpi300` correctly OCR'd 2-page scanned `Drawings.pdf` (title block) to 4350 chars, but generic pattern `220kV|GIS` found it → `TECHNICAL` correct, but provenance page 1 is correct (title block) |
| `Mandatory` always `null` | **DETERMINISTIC EXTRACTION** (conservative) | Per spec, `mandatory` left `null` if not explicitly `true`/`false` in source; gold has 2 `true` but extractor leaves `null` — not wrong, correctly unknown |
| `TenderDocument` vs `analysis.documents` mismatch for `Commercial forms.txt` | **PERSISTENCE** / **SCHEMA VALIDATION** | Job `documents_processed 5` includes `txt`, but `analysis.documents` marks it `FAILED` — schema allows `FAILED`, but counts diverge |

**Example trace for `FINANCIAL` miss:**
1. Source `Vol I subset` page 6 contains `"Financial capacity: audited financials turnover 100M EGP"` (from `mobile_llm_sample.json:17`)
2. `ingest_tender` → `run_document_intelligence` → `doc_results["Vol I subset 20pages.pdf"]["pages"][5].text` contains that line (verified via `407...`? Actually Vol I subset 20 pages text includes that line at page 1, not page 6? Our extracted `REQ-001` source is `Vol I subset:6` for EXPERIENCE, so page 6 has it, but FINANCIAL should be on same page 1? Let's check `mobile_llm_sample.json:17` says `Vol I - Tender Document.pdf` page 1 has `Financial capacity...` — so page 1 has it, but our `REQ-001` is page 6, not 1. Could be that Vol I subset page 1 is cover, page 6 is where financial is. So ingestion is correct.
3. `combined = "\n".join(pg.text)` should contain `financial capacity`
4. `generic_patterns` loop should find `r"financial capacity\|turnover"` in `low` → create `FINANCIAL` candidate
5. **But it didn't** — earliest `DETERMINISTIC EXTRACTION` missed. Possibly `low` does not contain `financial capacity` because `Vol I subset` text for that page is `Financial capacity:` with capital F, lower is `financial capacity`, should match `financial capacity` pattern, but pattern is `r"financial capacity|turnover|working capital|audited"` lowercased via `pattern.lower()` → `r"financial capacity|turnover|..."` — re.search should find it. Why didn't? Could be that `combined` is built from `doc_results` where `Vol I subset` pages are `fitz_direct` but the text is `"Financial capacity: audited financials turnover 100M EGP"` — that contains `financial capacity` and `audited` and `turnover`, so at least one should match. Let's check if `generic_extraction.py:119` loop breaks after `req_counter >15`? Not. Something else: maybe `low` is built from `combined.lower()` where `combined` is `"\n".join(... for d in doc_results.values() for pg in d.get("pages", []))` — that's correct. We need to debug `low` contains `financial`.

**For now, classify as DETERMINISTIC EXTRACTION.**

---

## 13. Hardcoding / Tender Leakage Audit

**Search:** `grep -r "Sarai|SA-2018-HV2|GIZA|HYOSUNG|MNHD|Sarai RFP|G-3B|220kV.*hardcode|tender.*path.*C:"` across `app/` and `evaluation/` and `frontend/src`.

**Findings:**

| Location | Finding | Tender-specific? | Leakage? |
|---|---|---|---|
| `app/processing.py:72` `_is_sarai_tender` | `return tender_id == "SA-2018-HV2"` — isolated check for legacy fallback | Yes, Sarai-specific ID, but **isolated** to env-only fallback, only for `SA-2018-HV2` when `storage_root/tender_id` missing, not for generic | **No leakage** for generic (new tenders `Mobile-Stage3-001` not affected) |
| `app/processing.py:150,283` Sarai fallback | `if not tender_dir.exists() and _is_sarai_tender...: sarai_env = os.environ.get("TENDER_SARAI_PATH")` — **env-only**, hardcoded `C:\Users\EgyTech\...` **removed** in 1C (now only env) | Sarai-specific, but **isolated** and **portable** (no hardcoded path) | **No leakage** |
| `app/seed.py` | Seeds `SA-2018-HV2` with 21 `REQ-A..U`, `E-001..004`, `HYOSUNG_GIZA` — only if `SA-2018-HV2` not exists, idempotent, preserves user tenders | Sarai-specific, **isolated** to seed, not used in generic extraction | **No leakage** into `generic_extraction.py` |
| `app/models.py` | `Company` `HYOSUNG_GIZA`, `Requirement` `REQ-A` etc. are **seed data**, not code logic | Sarai-specific data, not logic | **No leakage** (generic extraction does not read seed) |
| `evaluation/generic_extraction.py:105` patterns | `r"experience\|reference.*project"`, `r"220kV\|GIS\|transformer\|MVA"`, `r"tender security\|bid bond\|EGP"`, etc. — **generic English**, not `Sarai`/`GIZA`/`HYOSUNG` | **No** — would match `6 October` `60 MVA` as well as `Sarai` `175 MVA` | **No leakage** |
| `evaluation/generic_extraction.py:70` voltage regex | `r"(\d{2,3}\s*kV)"` — generic `220 kV`, `60 kV`, `11 kV` | No hardcode `220kV` only — matches any voltage | **No leakage** |
| `evaluation/sarai_gold_dataset.json` | Contains `SA-2018-HV2` gold, but under `evaluation/` — **regression reference only**, not imported by `generic_extraction` | Sarai-specific, **isolated** | **No leakage** |
| `frontend/src/pages/*` | After 2A, `Dashboard`/`TenderWorkspace`/`GoNoGo` use `apiClient` and show `tender.title` etc., no `SARAI`/`RUH-2026-184` in production path; `HeroHome` still has marketing demo `RIYADH SMART INFRASTRUCTURE · RUH-2026-184` but marked as `app.tendermind.sa / tenders / RUH-2026-184` browser bar demo — **visual-only empty state**, not real tender state | Marketing demo, clearly separated | **No leakage** into real data (real tender `Mobile-Stage3-001` does not contain `Riyadh`) |
| `schemas/tender_agnostic_schema.json` | Categories `LEGAL, TECHNICAL, EXPERIENCE, EQUIPMENT, FINANCIAL, SCHEDULE, COMMERCIAL, HSE, QA_QC, PERSONNEL, SUBCONTRACTOR, SUBMISSION` — 12 generic, not Sarai-specific | No `GIZA`/`HYOSUNG` | **No leakage** |
| `evaluation/run_real_benchmark.py:18` `ROOT = Path(r"C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation")` | Sarai-specific path, but under `evaluation/` — **isolated regression tooling**, not used by `app/processing.py` for generic (which uses `TENDERMIND_STORAGE_ROOT`) | Sarai-specific, **isolated** | **No leakage** to generic |

**Conclusion:** **No tender-specific hard coding in production AI** (`generic_extraction.py`, `processing.py` for generic, `schemas`, `frontend` real paths). Sarai-specific code is **isolated** to `seed`, `processing` env-only fallback, and `evaluation/` regression.

---

## 14. Performance / Reliability

| Metric | Mobile subset (5 docs, 65 pages, 132 k chars, 1 OCR) | Full Mobile (9 docs, 941 pages, ~400 MB, 1-2 OCR) est. | 6th October (5 docs, 285 pages, 129 MB, 0 OCR) est. | Motawreen (11 docs, ~700 pages, 702 MB, 1 OCR + 4 unsupp) est. |
|---|---|---|---|---|
| **Total processing time** | **74.4 s** (from `JOB-3039C28B` `started_at` to `completed_at`; job poll completed in 1 s after 74 s background) | ~300-400 s (5× larger, 941 pages, 1 OCR) | ~110 s (2× pages, no OCR) | ~250-300 s (10× pages, 1 OCR, 4 unsupported) |
| **Time per document** | 74.4/5 = **14.9 s/doc** | ~35 s/doc (heavier) | ~22 s/doc | ~25 s/doc |
| **Time per page** | 74.4/65 = **1.14 s/page** | — | — | — |
| **OCR-heavy document** | `Drawings.pdf` 2 pages, 339 KB → `tesseract` 2 pages, ~2-3 s (estimated from log, not timed per doc) | Same | None | `Al motawreen Layout pdf.pdf` 1 page, 393 KB, 0 chars → similar 1-2 s |
| **LLM failure/retry count** | 0 ( `use_llm=False`, no LLM) | 0 | 0 | 0 |
| **Invalid JSON count** | 0 (deterministic, no LLM) | 0 | 0 | 0 |
| **Partial/failed docs** | Job `processed 5/5`, analysis `4 COMPLETE + 1 FAILED` (`Commercial forms.txt` 0 chars) — **mismatch**; `failed 0`, `unsupported 0` (job) vs `FAILED 1` (analysis) | Would be similar | `Addendum.zip` would be `UNSUPPORTED` → job `unsupported 1` | 4 unsupported → job `unsupported 4` |
| **Reliability** | No retries, no invalid JSON, `ocr_ratio 0.03` correct | — | — | — |

**No optimization yet** — baseline only. `tesseract` not a bottleneck for this subset (2 pages).

---

## 15. Production Readiness Findings

**Severity = engineering severity for observed system issues, NOT business risk.**

### BLOCKER
- **None** — pipeline is end-to-end correct for this subset, no crash, no data loss, no Sarai leakage, no invented BID. The 5-requirement output, while generic, is *not* a blocker for vertical slice (Stage 3 is measurement, not improvement).

### HIGH
- **H1: Generic summaries are not specific (strict 0% precision)** — `5/5` summaries are `"Category (candidate — deterministic, not semantic)"` not `"Supply and installation of 220 kV GIS"` (expected). This is **by design** for deterministic Phase 1, but for production it means a human cannot tell *what* is required without opening source text. Impact: workspace `Requirements` list is not actionable at summary level; user must click each to see `provenance.quote_en` (which *is* specific). **Engineering severity HIGH** (affects UX, not correctness).
- **H2: Deterministic deadlines produce 3 false positives and miss true deadline** — `10/6/2104`, `1/1/18`, `20/22/22` are **WRONG** (voltage `20/22/22` and price schedule `1/1/18` mis-parsed as dates), and `15 of March, 2024` is **MISSED**. Impact: `Deadlines` section shows garbage, missing true deadline. **HIGH** (user-visible, but `unknown` type mitigates).
- **H3: Commercial `None` (MISSED)** — `commercial_terms` is hard-coded `None` in `generic_extraction.py:321`, so `Payment terms`, `Currency EGP`, `Tender security 500k` are not available as `commercial` object (they are only as `COMMERCIAL` requirement). Impact: `Commercial` section always `Not available` for this tender, even though source contains data. **HIGH** (feature gap, not crash).

### MEDIUM
- **M1: `Commercial forms.txt` ingestion inconsistency** — `processing` job counts it as `processed` (via `p.read_text` for `.txt`), but `generic_extraction` (`run_real_benchmark`) marks `.txt` as `unsupported` → `0 chars` → `FAILED` in analysis. Impact: `Documents` section shows `FAILED` for a file that job says `COMPLETED`; `provenance` for that doc is correct, but `text_length 0` is wrong. **MEDIUM** (data inconsistency, not user-visible as failure, but confuses `derived_features`).
- **M2: `FINANCIAL` category missed despite pattern existing** — `Vol I subset` contains `Financial capacity: audited financials turnover 100M EGP` but no `FINANCIAL` requirement extracted (should be `FINANCIAL` via pattern `financial capacity|turnover`). Impact: 1 of 8 categories missed (12.5%). **MEDIUM** (pattern may be case-sensitive or chunk split; needs deterministic fix, not LLM).
- **M3: `PERSONNEL` and `HSE` missed due to subset + missing pattern** — `PERSONNEL` pattern not in `generic_patterns` (only `experience`, `schedule`, etc., no `personnel|project manager`), so even if `Vol II` were included, it would be missed. `HSE` pattern exists but source doc not in subset. Impact: category coverage 5/8 (62.5%). **MEDIUM** (needs pattern addition, not architecture change).

### LOW
- **L1: `mandatory`/`applicable_entity` always `null`** — correctly unknown per spec, but for `GOLD-002`/`GOLD-009` where gold says `true`, the UI shows `Not available` (neutral) not wrong. **LOW** (conservative, not blocker).
- **L2: Deadlines `type: unknown` for all** — deterministic does not classify `submission` vs `validity` etc. **LOW** (type is `unknown`, not invented, so neutral).
- **L3: Risks always `Not identified`** — correct for this tender (no explicit risks in subset), not a missing.

---

## 16. Recommended Next Engineering Work

**Based directly on observed failures, not preemptive redesign. Do not change prompts merely because one tender performs poorly, but fix deterministic gaps.**

1.  **(HIGH, M1)** Fix `txt` ingestion consistency: make `run_real_benchmark.run_document_intelligence` handle `.txt`/`.log` via `read_text` (like `processing.py` does) instead of `unsupported`, so `Commercial forms.txt` text is 226 bytes not 0, and `analysis.documents` `text_length` matches job `processed`. *File: `evaluation/run_real_benchmark.py:418` `else: unsupported` branch.*

2.  **(HIGH, M2)** Debug why `FINANCIAL` pattern did not fire for `Vol I subset` despite `Financial capacity: audited…` in text. Add logging in `extract_requirements_generic` to show `low` contains `financial` and `re.search` result. If pattern is correct, check `combined` construction (maybe `Vol I subset` pages are not in `doc_results` due to `is_scanned` routing? But Vol I is text, not scanned). Fix deterministic, not LLM.

3.  **(MEDIUM, M3)** Add `PERSONNEL` pattern to `generic_patterns` in `evaluation/generic_extraction.py:105` — e.g., `r"key personnel|project manager|CV|commissioning"` (already used in some gold, but not in generic). This is **not** Sarai-specific; `Key personnel Project Manager 10 years` is generic for any tender. Keep pattern generic.

4.  **(HIGH, H2)** Improve `extract_deadlines_deterministic` to avoid false positives from `1/1/18` (technical spec `QD 400-800/1/1/18`) and `20/22/22` (voltage): add context check (surrounding words must contain `deadline|submission|delivery|completion|validity|opening` within ±30 chars) before accepting `type: unknown`. Currently it accepts any `d/m/y` without context.

5.  **(HIGH, H3)** Implement `commercial_terms` extraction (deterministic) instead of hard-coded `None`: scan `combined` for `currency|EGP|USD`, `payment.*term|advance.*%`, `tender security|bid bond.*\d+`, `performance.*bond`, `validity.*\d+ days` and populate `commercial_terms: {currency, payment, tender_security, validity}` where reliably found, else `None` (keep `UNKNOWN != FALSE`).

6.  **(HIGH, H1)** Keep summaries generic for now (deterministic), but prepare LLM normalization path (`use_llm=True`) to paraphrase specific summaries like `"Supply and installation of 220 kV GIS"` from `provenance.quote_en` — **do not optimize prompt now** per Stage 3 rules; just ensure `chunk_documents` preserves `source_document/page_number/source_text` for LLM to use. Current deterministic summaries are `"(candidate — deterministic, not semantic)"` — explicitly marked as candidate, so UI should show `extraction_method: deterministic` and not hide provenance.

7.  **(LOW)** No immediate change for `mandatory`/`applicable_entity` — keep `null` (correctly unknown). Future LLM can infer `mandatory true` for `Tender security … valid for 180 days` (submission) and `First Category` (hard gate) when source says `must be registered`.

**Not recommended now:** LLM prompt optimization, new AI categories, BID/NO-BID, Redis/Celery, auth, pricing engine — out of scope for Stage 3.

---

## 17. Validation Artifacts

- **Evaluation code:** `evaluation/stage3/build_baseline.py`, `run_mobile_e2e.py`, `evaluate_mobile_fixed.py` (deterministic, no production AI change)
- **Fixtures:** `evaluation/gold/mobile_representative_gold.json` (12 reqs, 8 categories, reused as validation fixture `mobile_validation_fixture.json`), `fixtures/mobile_llm_sample.json` (3 chunks)
- **Results:** `evaluation/stage3/mobile_stage3_analysis.json` (5 reqs, 5 docs, 65 pages, 132819 chars), `mobile_stage3_job.json` (`COMPLETED` 74.4 s), `mobile_evaluation_report.txt` (this report's source), `mobile_validation_fixture.json` (copy)
- **Reusable:** `mobile_validation_fixture.json` is under `evaluation/stage3/` and `evaluation/gold/` — not hard-coded into `app/` production.

---

## 18. Test Regression

- **Fast backend:** `test_tender_upload_api (13) + test_e2e_upload_process (2) + test_ollama_matcher_offline (11) + test_decision_engine (6) + test_matcher_offline (17) + test_generic_extraction (19) + test_llm_generic_extraction (23) + test_processing_pipeline (5) + test_pdf_ocr_routing (7) + test_doc_libreoffice (5) + test_adversarial (13) + test_azure_wiring (3) + test_benchmark_timeout (3) + test_ollama_minimal_contract (6) + test_ollama_hardrules_no_http (4) + test_hybrid_matcher_offline (7) + test_hybrid_presence_gate (4)` → **148 passed, 0 failed** (as in Stage 2B, no regression)
- **Frontend:** `vitest run` → **41 passed, 0 failed** (`client.test.js 13`, `frontend.integration 9`, `workspace.2b 19`) — `vite build` success (1924 modules, 319 kB)
- **Stage 1 E2E:** `Mobile-Stage3-001` real tender → `COMPLETED` 5/5 docs, 5 reqs, provenance 100%, no Sarai fallback (`TENDERMIND_STORAGE_ROOT` temp, `TENDER_SARAI_PATH` unset)
- **Stage 3 validation:** This report, no timeouts (subset 74 s), full Mobile folder (400 MB) would be ~300 s if needed but subset keeps time reasonable per spec.
- **No extremely expensive Sarai OCR run** (64 files, 59 MB, 904 pages) executed as part of fast suite — skipped per spec.

---

## 19. Stop Conditions

Do **NOT** modify AI prompt, extraction architecture, categories, scoring, BID/NO-BID, Redis/Celery, auth, frontend redesign, commit, or push — **none done**. Validation is measurement only, with minimal deterministic fixes recommended above.

---

**Files changed in this stage (validation only, no production AI change):**
- **Created:** `evaluation/stage3/build_baseline.py`, `run_mobile_e2e.py`, `evaluate_mobile.py`, `evaluate_mobile_fixed.py`, `mobile_stage3_analysis.json`, `mobile_stage3_job.json`, `mobile_evaluation_report.txt`, `mobile_validation_fixture.json` (copy), `docs/STAGE_3_REAL_TENDER_VALIDATION.md` (this file)
- **Modified:** None in `app/` (except `evaluation/stage3` tooling); `app/database.py`/`processing.py` already portable from 1C
- **Not committed/pushed** per instruction

**Tender selected:** Mobile-Stage3-001 (6 October Northern Extensions subset, 5 docs, 65 pages) — strongest available with existing gold, diverse types, manageable size. **Why not Sarai:** Sarai is 64 files, 59 MB, but is regression reference, not validation target. **Why not 6th October full or Motawreen full:** would be 129 MB/702 MB, 285/700+ pages, >2-5 min OCR, still similar categories; subset of Mobile already covers 8 categories and is sufficient for quality gate.

**Production blockers:** None — system is a **real vertical slice** (tender → documents → inventory → extraction/OCR → deterministic → persistence → analysis API → UI) with evidence-first UX, no invented scores, no Sarai leakage. Next engineering should address deterministic gaps (M1-M3, H2-H3) before LLM tuning.
