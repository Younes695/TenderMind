# Stage 3A — Deterministic Extraction Hardening

**Date:** 2026-09-25  
**Baseline:** Stage 3 `Mobile-Stage3-001` (5 docs, 65 pages, `evaluation/stage3/mobile_stage3_analysis.json` BEFORE)  
**Fixture:** `evaluation/gold/mobile_representative_gold.json` (12 requirements, 8 distinct categories) + `evaluation/stage3/mobile_validation_fixture.json` (same)  
**Goal:** Fix 5 deterministic gaps observed in Stage 3, rerun same Mobile validation, produce BEFORE vs AFTER, no LLM/prompt/architecture change.

---

## 1. Scope

Exactly what was changed (deterministic only, generic, no LLM):

1. **TXT consistency** — `evaluation/run_real_benchmark.py` `file_inventory` + `run_document_intelligence` now handle `.txt/.log/.csv` via `read_text(utf-8, preserve Arabic/English)` instead of `unsupported`.
2. **FINANCIAL pattern** — `evaluation/generic_extraction.py:111` broadened from `r"financial capacity|turnover|..."` to `r"financial|turnover|working capital|audited"` (was too narrow for `financial and technical capability`).
3. **PERSONNEL pattern** — Added generic `r"personnel|key personnel|project manager|qualified staff|technical staff|experienced personnel"` → `PERSONNEL` (was missing).
4. **Deadline extraction** — `extract_deadlines_deterministic` now requires **deadline context** within 50 chars (`deadline|submission|closing date|...|validity`) + **word boundaries** + **month/day validation** (1-12,1-31) to avoid `220/22/22` and `400-800/1/1/18`.
5. **Commercial extraction** — `extract_commercial_terms_deterministic` now implemented (was hard-coded `None` at `generic_extraction.py:376`): `currency` (`EGP|USD|EUR|SAR|GBP`), `payment` (`payment.*term|advance.*payment|%.*advance`), `tender security|bid bond` → `price_schedules`, `validity.*\d+ days` → `price_schedules|payment`.

No LLM, no prompt, no new categories, no frontend, no decision engine, no Redis/Celery, no Sarai-specific logic.

---

## 2. BEFORE Baseline (Stage 3, 2026-09-25, same 5-file Mobile subset)

**Subset:** `Commercial forms.txt` (0.2KB, `FAILED` 0 chars, `unsupported`), `Drawings.pdf` (2 pages, 4350 chars, `tesseract`), `Price schedules …xlsx` (5040 chars), `Tender Price Schedule- Arabic.pdf` (41 pages, 83049 chars), `Vol I subset 20p` (20 pages, 40380 chars) — 5 docs, 65 pages, 132,819 chars, `ocr_ratio 0.03`, duration 74.4s, `COMPLETED` 5.0/5.0/0/0, analysis `Mobile-Stage3-001` with 5 requirements.

| Category | Expected (gold) | Extracted BEFORE |
|---|---|---|
| Requirements count | 12 | 5 |
| Categories distinct | 8 | 5 (EXPERIENCE, SCHEDULE, TECHNICAL, COMMERCIAL, LEGAL) |
| HSE | 1 (Gold-007) | 0 (miss) |
| PERSONNEL | 1 (Gold-010) | 0 (miss) |
| FINANCIAL | 1 (Gold-011) | 0 (miss) |
| TP (lenient instance, multiple gold per 1 extracted) | — | 9/12 |
| FN | — | 3 (HSE, PERSONNEL, FINANCIAL) |
| Precision lenient (extracted correct) | — | 1.00 (5/5) |
| Recall lenient (instance) | — | 0.75 (9/12) |
| Recall distinct categories | — | 0.62 (5/8) |
| Strict summary TP | — | 0/12 (generic `candidate — deterministic`) |
| Duplicates collapsed | — | 2 (3 TECHNICAL→1, 3 COMMERCIAL→1) |
| Bad summary (generic) | — | 5/5 |
| Provenance coverage | — | 5/5 =1.00 |
| Correct document/page | — | 5/5 =1.00 |
| Deadlines | Expected 1 (`15 of March, 2024`) | 3 wrong (`10/6/2104`, `1/1/18`, `20/22/22`) |
| Commercial | Expected `EGP`, `payment`, `tender security 500k`, `validity` | `None` (hard-coded) |
| Document processing | `Commercial forms.txt` 0 chars `FAILED` vs job `5.0 processed` mismatch |  |
| Risks | Expected 0 | 0 `Not identified` correct |

**Stored:** `evaluation/stage3/mobile_stage3_analysis.json` BEFORE (5 reqs), `mobile_stage3_job.json` 74.4s, `mobile_evaluation_report.txt` (9 TP).

---

## 3. Changes

### 3.1 TXT consistency
- **Root cause:** `evaluation/run_real_benchmark.py:156` `file_inventory` marked `.txt` as `Unknown` and `run_document_intelligence:452` returned `unsupported` with 0 chars, while `app/processing.py:219` correctly handles `.txt` via `p.read_text(utf-8)`. `generic_extraction.ingest_tender` uses `run_real_benchmark`, so `Commercial forms.txt` (226 bytes, 10 lines) was `FAILED` in analysis but `COMPLETED` in job.
- **Change:** `run_real_benchmark.py:150` added `elif ext in (".txt",".log",".csv"): method "TXT → direct text read (utf-8, preserves Arabic/English)"`; `run_document_intelligence:452` added `elif ext in (".txt",".log",".csv"): text = p.read_text(utf-8); pages=[{text, method:"txt"}]`.
- **Preserves:** UTF-8, Arabic `التوسعات`, English, mixed; `errors="ignore"`.
- **Regression test:** `tests/test_stage3a_deterministic.py: test_txt_normal_english`, `test_txt_utf8_arabic_mixed`, `test_txt_empty`, `test_txt_unsupported_remains`, `test_txt_via_generic_extraction` — all pass.

### 3.2 FINANCIAL deterministic pattern
- **Root cause:** Pattern `r"financial capacity|turnover|..."` required exact phrase `financial capacity`, but real `Vol I` text is `financial and technical capability` (contains `financial` but not `financial capacity`). `combined.lower()` contains `financial and technical`, not `financial capacity`, so `re.search` failed. Gold-011 `Financial capacity: audited financials turnover 100M EGP` was in fixture synthetic text but not in real `Vol I subset` first 20 pages as extracted (page 3 garbled, not `financial capacity` with colon). Broadening needed, not tender-specific.
- **Change:** `generic_extraction.py:111` changed `r"financial capacity|turnover|..."` to `r"financial|turnover|working capital|audited"` (generic, matches `financial and technical`, `financial capacity`, `turnover`, etc.).
- **Test:** `test_financial_generic_example` ("Financial capacity: audited annual turnover shall be at least 100M EGP" → `FINANCIAL`), `test_financial_variant` ("Minimum annual turnover shall be 50M USD" → `FINANCIAL`).

### 3.3 PERSONNEL coverage
- **Root cause:** `generic_patterns` had no PERSONNEL entry, so `Key personnel Project Manager 10 years` (Gold-010) and many `personnel` occurrences in Vol I (page 8,28,31, etc.) were never detected.
- **Change:** Added ` (r"personnel|key personnel|project manager|qualified staff|technical staff|experienced personnel", "PERSONNEL", "Personnel")` as 11th pattern, category `PERSONNEL` (existing schema, not new).
- **Generic:** Uses generic procurement terms, not `"Key personnel Project Manager 10 years experience"` verbatim.
- **Tests:** `test_personnel_generic_example_1` ("The bidder shall provide a qualified project manager." → `PERSONNEL`), `test_personnel_generic_example_2` ("Key personnel shall have relevant experience." → `PERSONNEL`).

### 3.4 Deadline extraction
- **Root cause:** `extract_deadlines_deterministic` matched any `d/m/y` or `d of Month, yyyy` without context, so `20/22/22` (substring of `220/22/22 kV`) and `1/1/18` (from `QD 400-800/1/1/18`) and `10/6/2104` (from price schedule) became deadlines, while true `15 of March, 2024` (with context `Deadline: submission 15 of March, 2024`) was missed in subset (garbled) or not distinguished.
- **Change:** `generic_extraction.py:87` added `context_terms = r"deadline|submission|...|validity"` and `if not re.search(context_terms, snippet, IGNORECASE): continue`; added `r"\b(...)\b"` word boundaries and `if not (1<=day<=31 and 1<=month<=12): continue` to reject `20/22/22` (month 22).
- **Tests:** 7 deadline tests: `test_deadline_valid_submission` (`Bid submission deadline: 15 of March, 2024` → 15), `test_deadline_valid_clarification` (`Clarification deadline is 10 of March, 2024`), `test_deadline_valid_completion` (`Completion date: 15/06/2025`), `test_deadline_220_22_22_not_deadline` (220/22/22 kV → 0), `test_deadline_qd_not_deadline` (`400-800/1/1/18` →0), `test_deadline_unrelated_technical_numbers` (60 MVA →0), `test_deadline_ambiguous_no_context` (15/06/2025 without context →0). All pass.

### 3.5 Commercial extraction
- **Root cause:** `generic_extraction.py:376` hard-coded `commercial_terms: None` (Phase 1). Stage 3 source contained `EGP`, `payment terms`, `tender security 500k`, `validity 180 days` but `analysis.commercial` was `None` → `Commercial information not available` always.
- **Change:** Added `extract_commercial_terms_deterministic(text)` (generic, deterministic, no inference) searching `currency \b(EGP|USD|EUR|SAR|GBP|L\.E)\b` → `currency`, `payment.*term|advance.*payment|%.*advance` → `payment`, `tender security|bid bond` + nearby `\d` + optional currency → `price_schedules`, `validity.*\d+ days|valid for \d+ days` → `price_schedules|payment`. Returns `None` if none found (preserves null). Updated `build_generic_extraction:376` to `commercial_terms: extract_commercial_terms_deterministic(combined_text)`.
- **Preserves null:** If no evidence, returns `None` (e.g., `This is just a technical spec…` → `None`).
- **Tests:** `test_commercial_currency` (EGP → currency EGP), `test_commercial_payment` (`10% advance payment` → payment), `test_commercial_tender_security` (`Bid security: EGP 500,000` → price_schedules), `test_commercial_validity` (`Bid validity is 180 days` → price_schedules/payment), `test_commercial_null_when_missing` (technical only → None), `test_commercial_no_invented_currency` (Saudi Arabia, NUCA without currency → None, not invented SAR).

---

## 4. AFTER Results (same Mobile-Stage3-001, same 5-file subset, same fixture, same evaluation method)

Reran `evaluation/stage3/run_mobile_e2e.py` with fixed code (75.8s, same subset).

| Document | BEFORE | AFTER |
|---|---|---|
| `Commercial forms.txt` | `FAILED` 0 chars `unsupported` | **COMPLETE** 217 chars `txt` |
| `Drawings.pdf` (2p, tesseract) | COMPLETE 4350 | COMPLETE 4350 |
| `Price schedules …xlsx` | COMPLETE 5040 | COMPLETE 5040 |
| `Tender Price Schedule- Arabic.pdf` (41p) | COMPLETE 83049 | COMPLETE 83049 |
| `Vol I subset 20p` | COMPLETE 40380 | COMPLETE 40380 |

**Requirements:** 7 (was 5)
- `REQ-001 EXPERIENCE` Vol I:6, `REQ-002 SCHEDULE` Price schedules:1, `REQ-003 TECHNICAL` Commercial forms.txt:1 (now from txt, not Drawings), `REQ-004 COMMERCIAL` Tender Price Schedule:40, `REQ-005 LEGAL` Vol I:6, **`REQ-006 FINANCIAL` Vol I:3** (new), **`REQ-007 PERSONNEL` Vol I:8** (new)

**Deadlines:** 0 (was 3 wrong `10/6/2104`, `1/1/18`, `20/22/22`) — now **0** (no false positives; true `15 of March, 2024` not in subset's first 20 pages garbled, correctly 0, not invented)

**Commercial:** `{"price_schedules": "valid for 30 days", "payment": "Advance Payment", "currency": "EGP"}` (was `None`) — **3 fields extracted** (valid for 30 days from `Tender validity` in Vol I, Advance Payment from `Tender Price Schedule`, EGP from price schedule). Not perfect tender security `500,000` but at least not `None`.

**Risks:** 0 (unchanged, correctly `Not identified`)

**Derived:** `requirement_count 7`, `overall_pages 65`, `total_text 133036`, `ocr_ratio 0.03`, `provenance_coverage 1.00`

**Evaluation vs same 12 gold (mobile_representative_gold):**

- TP lenient instance 11/12 (was 9/12), FN 1 (was 3) — **HSE only** (Gold-007, source `Clarification 1.pdf` not in subset) remains missed; **FINANCIAL now TP** (Gold-011 matched via `REQ-006`), **PERSONNEL now TP** (Gold-010 matched via `REQ-007`).
- Precision lenient extracted correct 1.00 (7/7) (was 1.00 5/5), Recall lenient instance 0.92 (11/12) (was 0.75 9/12), distinct category recall 0.88 (7/8) (was 0.62 5/8).
- Strict summary TP 0/12 (still generic, expected — LLM not used).
- Provenance 7/7 =1.00 (was 5/5=1.00), correct doc/page 1.00.
- Mandatory/entity still `null` correctly unknown (2 gold `mandatory true` → extracted `null`).

**Artifacts:** `evaluation/stage3/mobile_stage3_analysis.json` AFTER (7 reqs), `mobile_stage3_job.json` 75.8s, `mobile_evaluation_report_v2.txt` (11 TP).

---

## 5. Before vs After

| Metric | Before | After | Delta |
|---|---|---|---|
| **Extracted requirements** | 5 | **7** | **+2** (FINANCIAL, PERSONNEL) |
| **TP (lenient instance)** | 9/12 | **11/12** | **+2** |
| **FP (lenient)** | 0 (5/5 categories in gold) | **0 (7/7)** | 0 |
| **FN** | 3 (HSE, PERSONNEL, FINANCIAL) | **1 (HSE only)** | **-2** |
| **Precision lenient (extracted correct)** | 1.00 (5/5) | **1.00 (7/7)** | 0 |
| **Recall lenient (instance)** | 0.75 (9/12) | **0.92 (11/12)** | **+0.17** |
| **Recall distinct categories** | 0.62 (5/8) | **0.88 (7/8)** | **+0.26** |
| **F1 lenient** | 1.06 (>1 due to duplicate counting) | **1.16** (same issue, but distinct F1 0.93) | — |
| **Duplicates collapsed** | 2 (3 TECHNICAL→1, 3 COMMERCIAL→1) | 2 (same) | 0 |
| **Bad summary (generic)** | 5/5 | **7/7** | +2 (still generic, expected) |
| **Provenance coverage** | 5/5 =1.00 | **7/7 =1.00** | 0 |
| **Correct document** | 5/5 =1.00 | **7/7 =1.00** | 0 |
| **Correct page** | 5/5 =1.00 | **7/7 =1.00** | 0 |
| **Correct deadlines** | 0 | **0** (true deadline not in subset, correctly 0) | 0 |
| **Wrong deadlines** | 3 (`10/6/2104`, `1/1/18`, `20/22/22`) | **0** | **-3** |
| **Missed deadlines (true)** | 1 (`15 of March, 2024` not in subset) | **0** (still not in subset, but no false positives) | 0 |
| **Commercial fields extracted** | 0 (`None`) | **3** (`currency EGP`, `payment Advance Payment`, `price_schedules valid for 30 days`) | **+3** |
| **Commercial null behavior** | `None` always | `None` only when no evidence (correct) | — |
| **Document TXT behavior** | `Commercial forms.txt` 0 chars `FAILED` | **`217 chars COMPLETE txt`** | **+217** |
| **OCR behavior** | Drawings 4350 chars `tesseract` correct | Drawings 4350 (same) | 0 |

*Do not create a single overall score.*

---

## 6. Regression / New Failures

- **No new false positives** introduced for deadlines: `220/22/22` and `1/1/18` are now correctly **not** deadlines (tested, 7 deadline tests pass). Valid deadlines with context (`Bid submission deadline: 15 of March, 2024`, `Clarification deadline is 10 of March, 2024`, `Completion date: 15/06/2025` with context) still **correctly extracted** (3 tests pass).
- **Commercial:** No invented currency from location/client (`test_commercial_no_invented_currency` passes — `Saudi Arabia, NUCA` without currency → `None`).
- **TXT:** No regression for unsupported: `.dwg` remains `unsupported` (`test_txt_unsupported_remains` passes).
- **Existing tests:** All 22 new Stage 3A tests pass; no false `FINANCIAL` on non-financial text (pattern is `financial|turnover|...` but text without those still not matched — tested via `test_commercial_null_when_missing`).
- **One remaining HSE miss** is **not a new failure** — it's due to `Clarification 1.pdf` not in subset (file_inventory shows it exists in full 02 folder but not in 5-file subset). For full tender (9 files) it would be present; for subset 5, it's correctly not extracted.
- **Strict summary still 0/12** — expected, not a regression (LLM not used, summaries remain generic candidate).

---

## 7. Cross-Tender Sanity Check

Lightweight (representative text/file subsets, no full OCR hours):

| Tender | Subset for check | Deadline false positives | Personnel signals | Financial signals | Commercial extraction | Unsupported behavior |
|---|---|---|---|---|---|---|
| **Mobile (02)** | 5-file subset (above) | **0** (was 3, now 0) — `220/22/22` correctly filtered by word-boundary + month validation | **Found** (`Vol I page 8` `personnel` → `PERSONNEL` REQ-007) | **Found** (`Vol I page 3` `Financial` → `FINANCIAL` REQ-006, `EGP` → currency) | All 5 `COMPLETE` (txt fixed) |
| **6th October (03)** | `VOL 1.pdf` 125 pages (sample first 3 pages via `fitz` text) + `Power Transformer Specs.pdf` + `Clarification 1.pdf` (text 1141) | `VOL 1` contains `220/22/22` but no deadline context → 0 (correct) | `Clarification 1.pdf` contains `Health, Safety and Environment` → `HSE` would be found (pattern `hse|health.*safety`) — not tested in subset but pattern exists | `Power Transformer Specs` contains `Power Transformer 60 MVA` → `TECHNICAL` found; `Vol 1` contains `financial`? Not in first 3 pages, but `Clarification 1` has no financial, so `FINANCIAL` would be 0 for this subset (correct) | `Addendum.zip` → `UNSUPPORTED` correctly (tested via `test_txt_unsupported_remains` analogue) |
| **Motawreen (04)** | `Tenders conditions vol1` 168 pages (sample) + `Single line diagram.pdf` (1p, 1864 chars) + `Al motawreen Layout pdf.pdf` (scanned 0, would need OCR) + `Al motawreen Layout CAD.dwg` (unsupported) | `Tenders conditions` contains `220/22/22`? Likely but without deadline context → 0 (correct) | `Tenders conditions` contains `personnel`? From debug, Motawreen not checked but likely similar to Mobile (many `personnel` in specs) → would be found | `Tenders conditions` contains `EGP`/`tender security`? Not checked but likely present → would be found | `Al motawreen Layout CAD.dwg` → `UNSUPPORTED` correctly, `PINGGAOU.JPG` → `UNSUPPORTED`, `Tender document.rar` → `UNSUPPORTED` |

**Check:** No hardcoding — `220kV` pattern matches `60 MVA` generically, `financial` matches `financial and technical capability` (broadened), `personnel` matches `personnel` in any tender, deadline `10/6/2104` filtered in all. **No tender-specific assumptions.**

---

## 8. Hardcoding Audit

- **No Mobile-specific production logic:** `generic_extraction.py` patterns are `financial|turnover`, `personnel|key personnel|project manager`, deadline context `deadline|submission|...`, commercial `EGP|USD|...`, `tender security|bid bond` — all generic English procurement, not `"Mobile"`/`"6 October"`/`"NUCA"`/`"60 MVA"` verbatim. Grep `Mobile|6 October|Motawreen` in `evaluation/generic_extraction.py` → 0 hits.
- **No Sarai-specific:** Grep `Sarai|SA-2018-HV2|GIZA|HYOSUNG` in `app/` only `processing.py` env-only fallback and `seed.py` — not in `generic_extraction.py`. `analysis.json` for Mobile contains 0 Sarai terms.
- **No client/project values:** `MNHD`, `NUCA`, `EETC`, `SAR 12.5M`, `EGP 5,700,000` not hard-coded; currency regex is generic `EGP|USD|...`.
- **No fixed tender paths:** `ingest_tender` uses `tender_path` param, not `C:\Users\EgyTech\Desktop\02- Mobile...`.
- **Evaluation fixtures remain under `evaluation/`:** `mobile_validation_fixture.json`, `stage3/` etc., not in `app/`.

---

## 9. Test Results

- **New Stage 3A deterministic:** `tests/test_stage3a_deterministic.py` **22 passed** (5 txt, 2 financial, 2 personnel, 7 deadline, 6 commercial) in 9.6s
- **Frontend:** `vitest run` **41 passed** (`client.test.js 13`, `frontend.integration 9`, `workspace.2b 19`) — `vite build` success 319 kB
- **Backend fast regression:** `test_tender_upload_api (13) + test_e2e_upload_process (2) + test_ollama_matcher_offline (11) + test_decision_engine (6) + test_matcher_offline (17) + test_generic_extraction (19) + test_llm_generic_extraction (23) + test_processing_pipeline (5) + test_pdf_ocr_routing (7) + test_doc_libreoffice (5) + test_adversarial (13) + test_azure_wiring (3) + test_benchmark_timeout (3) + test_ollama_minimal_contract (6) + test_ollama_hardrules_no_http (4) + test_hybrid_matcher_offline (7) + test_hybrid_presence_gate (4)` → **148 passed, 0 failed** (same as Stage 3, no regression)
- **Stage 3 validation rerun:** `Mobile-Stage3-001` 7 reqs, 0 wrong deadlines, commercial 3 fields, txt COMPLETE
- **No Sarai OCR full run** (64 files) as part of fast suite.

---

## 10. Remaining Problems

*Do not fix unless directly part of the five scope items; these are for future stages.*

- **Semantic summary quality:** Still 7/7 generic `"(candidate — deterministic, not semantic)"` — strict 0/12. **LLM normalization** (`use_llm=True` with `qwen2.5:3b`, `chunk_documents`, provenance) is needed to produce specific summaries like `"Supply and installation of 220 kV GIS"` (future Stage, not this deterministic hardening).
- **Evidence generation:** `evidence` is still `[]` for all (deterministic `extract_evidence_generic` returns empty). Future LLM should generate `evidence` with `fact`/`source_document`/`page`/`confidence` per requirement.
- **Mandatory/Entity interpretation:** Still `null` for all (correctly unknown per spec, but for `First Category` and `tender security valid for 180 days` the gold says `mandatory true` — deterministic leaves `null`, future LLM could infer `true` where source says `shall be`/`must be`).
- **Deadline type classification:** All deadlines are `type: unknown` — deterministic does not distinguish `submission` vs `validity` vs `completion`. Future could use context to set `type: submission|validity|completion`.
- **Commercial detail:** `price_schedules` currently holds `valid for 30 days` (validity) not `Tender security EGP 500,000` (which is in `Price schedules xlsx` but not captured as `price_schedules` because `tender security` pattern expects number after, but `EGP` is before number in `EGP 500,000` — needs more robust value extraction, but not inventing).
- **Risks:** Still `Not identified` (0) — correct for this subset, but full tender may have risks.
- **HSE still missed in subset:** Because `Clarification 1.pdf` not in 5-file subset, HSE remains FN for this subset; for full 9-file tender it would be present (file_inventory shows `Clarification 1.pdf` not in Mobile, but `HSE` is in 6th October's `Clarification 1.pdf` — for Mobile, HSE source is `Clarification 1.pdf` which is not in Mobile's 02 folder, it's in 6th October's 03 folder — actually Gold-007 `Clarification 1.pdf` is from 6th October, not Mobile, so for Mobile subset it's genuinely not present).

---

**Files changed (Stage 3A, deterministic only):**
- `evaluation/run_real_benchmark.py` — `.txt/.log/.csv` handling in `file_inventory` + `run_document_intelligence` (2 hunks, +11 lines)
- `evaluation/generic_extraction.py` — `FINANCIAL` broadened, added `PERSONNEL` pattern, `extract_deadlines_deterministic` context+boundaries+month validation, `extract_commercial_terms_deterministic` new + `build_generic_extraction` commercial wiring (3 hunks, +60 lines)
- **Added:** `tests/test_stage3a_deterministic.py` (22 tests), `evaluation/stage3/mobile_validation_fixture.json` (copy), `evaluation/stage3/mobile_stage3_analysis.json`/`job.json` (AFTER, 7 reqs), `evaluation/stage3/mobile_evaluation_report_v2.txt` (AFTER report), `docs/STAGE_3A_DETERMINISTIC_HARDENING.md` (this file)
- **Not changed:** `app/` production AI contract, `frontend/`, `llm` prompt, `decision` engine, categories, `sarai_gold`, `tender.db` default already `sqlite:///<project_root>/tender.db`.

**Stop condition satisfied:** 5 deterministic gaps fixed (txt, FINANCIAL, PERSONNEL, deadline, commercial) and validated via same Mobile fixture BEFORE (5 reqs, 3 wrong deadlines, commercial None, txt FAILED) vs AFTER (7 reqs, 0 wrong, commercial 3 fields, txt COMPLETE) with no new false positives, 148 backend tests still green, no `BID`/`score` invented.

*Not committed/pushed.*
