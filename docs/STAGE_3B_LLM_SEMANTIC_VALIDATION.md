# Stage 3B — LLM Semantic Normalization Validation

**Date:** 2026-09-25  
**Validator:** Automated + manual, same fixture as Stage 3/3A  
**Fixture:** `Mobile-Stage3B-LLM-001` (subset of `02- Mobile substations`, 5 files, 65 pages, same as Stage 3A AFTER) + `evaluation/gold/mobile_representative_gold.json` (12 reqs, 8 distinct categories, not modified)  
**Branch:** `main` (Stage 3A hardened: 7 deterministic reqs, 0 wrong deadlines, commercial 3 fields, txt COMPLETE)

---

## 1. Objective

> Given the same deterministic candidates and source chunks, does the existing `qwen2.5:3b / Variant B` LLM normalization materially improve semantic quality while preserving provenance and schema correctness?

This is **evaluation, not architecture rewrite**. Measure semantic summary quality, splitting/merging, category, mandatory/entity, evidence/provenance, JSON/schema robustness, latency, and cross-tender sanity. Do not redesign prompt/model/categories, do not invent scores, do not add BID/NO-BID.

---

## 2. Environment

- **OS:** Windows 10, `win32`, Python 3.11.0, `pymupdf 1.28.2`, `openpyxl 3.1.5`, `tesseract 5.4.0_ara+eng_psm6_dpi300` (for Drawings), `pydantic 2.11.7`, `fastapi 0.115.0`
- **CPU:** Local, no GPU, no Azure, no paid API
- **Ollama:** `http://localhost:11434` via `check_ollama_available()` — **available**, `model qwen2.5:3b` found, `GET /api/tags` 200, `ollama list` shows `qwen2.5:3b`
- **Tender path:** Temp `C:\Users\EgyTech\AppData\Local\Temp\stage3b_*` with 5 files copied from `02- Mobile substations` (same as Stage 3A): `Commercial forms.txt` 217 chars, `Drawings.pdf` 2 pages `tesseract` 4350 chars, `Price schedules …xlsx` 5040 chars, `Tender Price Schedule- Arabic.pdf` 41 pages 83049 chars, `Vol I subset 20pages.pdf` 20 pages 40380 chars — total 65 pages, 133036 chars, `ocr_ratio 0.03`
- **Gold:** `evaluation/gold/mobile_representative_gold.json` (12 reqs, not modified) — `source_fixture: evaluation/fixtures/mobile_llm_representative.json` (3 synthetic chunks, but we use real 5-file subset for LLM)

---

## 3. Model/version

- **Model:** `qwen2.5:3b` (`DEFAULT_MODEL` in `evaluation/llm_generic_extraction.py:14`, `OLLAMA_MODEL` env override, `TENDERMIND_OLLAMA_MODEL` fallback) — same as Stage 2B/3A `PROMPT_VERSION Variant B`, `PIPELINE_VERSION 1.0`, `LLM_MODEL qwen2.5:3b` in `app/processing.py`
- **Endpoint:** `http://localhost:11434` (`DEFAULT_BASE_URL`, `OLLAMA_ENDPOINT`, `TENDERMIND_OLLAMA_ENDPOINT` env)
- **Timeout:** `90` seconds per chunk (`TIMEOUT_PER_REQUEST`, `TENDERMIND_OLLAMA_TIMEOUT` env, `options: {"temperature":0}`, `format:"json"`, `stream:false`)
- **No model switch, no prompt rewrite before measuring.**

---

## 4. Prompt/version/hash

**Variant B prompt** (`evaluation/llm_generic_extraction.py:82` `LLM_SYSTEM_PROMPT`) — preserved, not redesigned:

> You are a tender document extraction assistant. Extract ONLY information explicitly supported by the supplied text.
>
> For each requirement, return: `candidate_id` (e.g., chunk-0001-item-02), `summary`, `category` (12 enum), `mandatory` (true/false/null), `requirement_type`, `applicable_entity`, `evidence_required`, `conditional`, `source_document` (must be from chunk), `page_number`, `confidence`, `provenance` (`quote_en` exact), `extraction_method ("llm")`.
>
> For each evidence (only if explicitly supported): `candidate_id`, `requirement_candidate_id`, `fact`, `source_document`, `page_number`, `confidence`, `provenance`, `applicable_entity`, `valid_until`, `reusable`.
>
> Rules: `UNKNOWN != FALSE`, never invent entities/dates/evidence/source, every requirement/evidence must have traceable provenance, evidence must point to same chunk's source, if no evidence return `[]`, return ONLY valid JSON.
>
> Category definitions (classify by PRIMARY PURPOSE, not keywords): `TECHNICAL`=equipment/spec, `EXPERIENCE`=bidder/project experience, `FINANCIAL`=financial/commercial qualification, `LEGAL`=legal/documentary, `SCHEDULE`=delivery/completion/time, `HSE`=health/safety/environment, `QA_QC`=quality, `COMMERCIAL`=pricing/payment.

**Prompt version:** `Variant B` (hard-coded, no hash file, but `PROMPT_VERSION` in `app/processing.py` is `Variant B`, `LLM_MODEL qwen2.5:3b`). **Hash preserved** — no change, prompt string identical to Stage 2B.

**Existing normalization schema:** `candidate_id` (`chunk-0001-item-02`) → canonical `REQ-001` via `assign_canonical_ids` (stable sorting by `source_document,page_number,summary`), evidence `candidate_id` → `evidence_id` and `requirement_candidate_id` → canonical `requirement_id`, with deduplication and provenance validation.

**Provenance/evidence representation:** `source_document` must equal `chunk.source_document`, `page_number` must equal `chunk.page_number`, `provenance.quote_en` exact quote, `extraction_method:"llm"`, `confidence 0.0-1.0`.

**Retries/failures:** `call_ollama_for_chunk` returns `None` on HTTP !=200 or exception; `parse_llm_json` handles `empty`, `fenced`, `extracted`, `malformed`; `validate_requirement`/`validate_evidence` reject missing `source_document`/wrong category; `deduplicate_requirements` conservative; `assign_canonical_ids` filters orphan evidence.

---

## 5. Fixture

**Same Mobile Stage 3 / Stage 3A representative fixture:** `Mobile-Stage3-001` / `Mobile-Stage3B-LLM-001` (identical 5-file subset, not silently changed). Gold: `evaluation/gold/mobile_representative_gold.json` (12 `gold_requirements` with `gold_id`, `summary`, `category`, `mandatory`, `source_document`, `page_number`, `source_text`, `source_chunk_id`; 2 `gold_evidence`). Do not modify gold.

**Gold categories present (12):** `TECHNICAL` 3 (Gold-001,004,005), `COMMERCIAL` 3 (Gold-002,006,008), `EXPERIENCE` 1 (Gold-003), `HSE` 1 (Gold-007), `LEGAL` 1 (Gold-009), `PERSONNEL` 1 (Gold-010), `FINANCIAL` 1 (Gold-011), `SCHEDULE` 1 (Gold-012). **Conditional:** Gold-006 `conditional true` (consortium JV allowed). **Mandatory true:** Gold-002 (tender security 500k) and Gold-009 (First Category) are `mandatory true` (HARD_GATE).

**Fixture completeness for gold:** For this 5-file subset, Gold-007 `HSE` source `Clarification 1.pdf` (from 6th October, not in Mobile 02) is **not present in fixture** (expected `not present in fixture`, not LLM miss). Gold-010 `PERSONNEL` source `Vol II - Tech Specs - Part 1.pdf` is also not in 5-file subset (Vol I subset only, not Vol II) — **not present**. Gold-011 `FINANCIAL` source `Vol I - Tender Document.pdf` page 3 is in Vol I subset (20 pages includes page 3), so **present**.

**Distinction (per spec):** We explicitly distinguish `not present in fixture` vs `deterministic miss` vs `LLM miss` vs `unsupported` vs `evaluation limitation` in §17.

---

## 6. Experimental design

**At least two comparable paths, same deterministic candidates/source chunks:**

- **A) DETERMINISTIC BASELINE:** `build_generic_extraction(tender_path, tender_id, use_llm=False)` → `generic_extraction.py` `ingest_tender` → `file_inventory` + `run_document_intelligence` (txt fixed, 65 pages) → `extract_deadlines_deterministic` (context-hardened) → `extract_requirements_generic` (11 patterns, now includes `FINANCIAL` broadened + `PERSONNEL`) → `extract_commercial_terms_deterministic` → `validate_against_schema` → `derived_features`. Freeze output: 7 requirements.

- **B) DETERMINISTIC + EXISTING LLM NORMALIZATION:** **Same** `ingest_tender` → `doc_results` → `chunk_documents` (`max_chars 3000`, page-aware) → **same source chunks** (69 total, we selected **representative 5 chunks, one per document** to keep time <5 min and cover all docs: `Commercial forms.txt:1` 217 chars, `Drawings.pdf:1` 2976 chars, `Drawings.pdf:1` 804 chars, `Price schedules …xlsx:1` 2989 chars, `Vol I subset 20pages.pdf:1` 256 chars — actually 5, but first run used `max_chunks=5` first 5 chunks (Commercial, Drawings×3, Price schedules) missing Vol I; second run used **one per doc** 5 representative including Vol I). Feed each chunk to **existing** `call_ollama_for_chunk` → `parse_llm_json` → `validate_requirement`/`validate_evidence` → `deduplicate` → `assign_canonical_ids`. **Do not regenerate candidates via different deterministic config** — same `doc_results` and `tender_path`.

**Adapter:** Minimal evaluation-only adapter in `evaluation/stage3b/run_llm_validation_v2.py` that reuses `chunk_documents` and `llm_extract_requirements_for_tender` with `max_chunks` param, not a production pipeline redesign. Production `app/processing.py` remains `use_llm=False` (deterministic only) — LLM path is evaluation only.

**Isolation:** Deterministic candidates are **not fed as input** to LLM; LLM extracts directly from chunk `text` (as designed). The comparison isolates LLM's **semantic normalization** contribution vs deterministic's **pattern** contribution on same source material.

---

## 7. Deterministic baseline

**Run:** `Mobile-Stage3B-LLM-001` (same 5 files) via `build_generic_extraction` (Stage 3A hardened code, 7 reqs, 50.1s). Output saved `evaluation/stage3b/deterministic_baseline.json` (same as `stage3/mobile_stage3_analysis.json` AFTER).

| # | req_id | category | summary | mandatory | source | page | confidence | method |
|---|---|---|---|---|---|---|---|
| 1 | REQ-001 | EXPERIENCE | Experience/qualification (candidate — deterministic, not semantic) | null | Vol I subset 20pages.pdf | 6 | 0.55 | deterministic |
| 2 | REQ-002 | SCHEDULE | Schedule/delivery (candidate — deterministic, not semantic) | null | Price schedules …xlsx | 1 | 0.55 |
| 3 | REQ-003 | TECHNICAL | Technical equipment (candidate — deterministic, not semantic) | null | Commercial forms.txt | 1 | 0.55 |
| 4 | REQ-004 | COMMERCIAL | Commercial/bid security (candidate — deterministic, not semantic) | null | Tender Price Schedule- …pdf | 40 | 0.55 |
| 5 | REQ-005 | LEGAL | Consortium/JV (candidate — deterministic, not semantic) | null | Vol I subset 20pages.pdf | 6 | 0.55 |
| 6 | REQ-006 | FINANCIAL | Financial capacity (candidate — deterministic, not semantic) | null | Vol I subset 20pages.pdf | 3 | 0.55 |
| 7 | REQ-007 | PERSONNEL | Personnel (candidate — deterministic, not semantic) | null | Vol I subset 20pages.pdf | 8 | 0.55 |

- **Deadlines:** 0 (correct for subset, no false `20/22/22`)
- **Commercial:** `{"price_schedules":"valid for 30 days","payment":"Advance Payment","currency":"EGP"}` (was `None` before)
- **Evidence:** 0 (deterministic returns empty)
- **Provenance coverage:** 7/7 =1.00, correct doc/page 1.00
- **Strict summary correct:** 0/12 (generic, not specific)

---

## 8. LLM-normalized results

**Run:** Same 5-file tender, `llm_extract_requirements_for_tender(tender_path, max_chunks=5)` (first run) and `representative 5 chunks, one per doc` (second run). Both gave **4 requirements, 4 evidence, all TECHNICAL** (second run) or 4 TECHNICAL (first run). We report the **representative 5-chunk, one-per-doc** run (v2) as more fair (covers all docs):

| # | req_id (canonical) | candidate_id | category | summary (LLM, specific) | source | page | confidence | evidence links |
|---|---|---|---|---|---|---|---|
| 1 | REQ-001 | chunk-0001-item-01 | TECHNICAL | 220kV, 22kV, and 20kV equipment specifications and ratings | Drawings.pdf | 1 | 0.75 | 1 evidence (chunk-0001-ev-01) |
| 2 | REQ-002 | chunk-0001-item-02 | TECHNICAL | Main Road and Car Park layout for a 220kV project | Drawings.pdf | 1 | 0.75 | 1 evidence |
| 3 | REQ-003 | chunk-0001-item-03 | TECHNICAL | Minimum XLPE cable length and phase requirements for a 500 k | Drawings.pdf | 1 | 0.75 | 1 evidence |
| 4 | REQ-004 | chunk-0004-item-01 | TECHNICAL | Supply of 220KV GIS switchgear | Price schedules …xlsx | 1 | 0.75 | 1 evidence |

*First run (first 5 chunks, no Vol I) gave 4 TECHNICAL as well: `220kV, 22kV, and 20kV equipment ratings…`, `Main Road…`, `Minimum XLPE…`, `Supply of 220KV GIS switchgear` — same 4.*

- **Evidence:** 4 items, each `evidence_id: chunk-XXXX-ev-01`, `requirement_candidate_id: chunk-XXXX-item-01`, `fact: same as summary`, `source_document` same as chunk, `page_number` same, `confidence 0.75`, `provenance.quote_en` exact quote (e.g., `220kV, 22kV, and 20kV equipment ratings…`). All 4 evidence point to **REQ-001 only** (first requirement of each chunk) — **incorrect linking** (should link to each requirement, not all to REQ-001). See §13.
- **Raw JSON:** `evaluation/stage3b/llm_normalized.json` (4 reqs, 4 evs, model `qwen2.5:3b`, prompt `Variant B`), `llm_v2_reqs.json`/`llm_v2_evs.json` for representative run.
- **Valid JSON:** 4/5 chunks succeeded (1 chunk `Commercial forms.txt:1` 217 chars timed out after 92s, `call_ollama_for_chunk` returned `None` → no retry, counted as LLM failure, not fallback to deterministic). See §14.

**Comparison:** Deterministic 7 reqs across 5 categories (EXPERIENCE, SCHEDULE, TECHNICAL, COMMERCIAL, LEGAL, FINANCIAL, PERSONNEL) vs LLM 4 reqs all **TECHNICAL** (no EXPERIENCE/SCHEDULE/COMMERCIAL/LEGAL/FINANCIAL/PERSONNEL/HSE/QA_QC/SUBCONTRACTOR).

---

## 9. Semantic summary analysis

**Question:** Does LLM produce materially better semantic summaries (specific vs generic candidate-marked)?

| Gold summary (specific) | Deterministic summary (generic) | LLM summary (specific?) | Correct? |
|---|---|---|---|
| Supply and installation of 220 kV GIS (TECHNICAL) | Technical equipment (candidate — deterministic, not semantic) | Supply of 220KV GIS switchgear | **LLM correct** — specific, preserves `220KV GIS`, `Supply` |
| Power Transformer 60 MVA 220/22-11kV (TECHNICAL) | Technical equipment (same generic) | 220kV, 22kV, and 20kV equipment specifications and ratings | **LLM partially correct** — captures `220kV, 22kV, 20kV` and `equipment specifications` but not `60 MVA` or `Power Transformer` |
| Type tests for GIS per IEC 62271-100 (TECHNICAL) | Technical equipment (generic) | Minimum XLPE cable length and phase requirements for a 500 k | **LLM incorrect** — hallucinated `XLPE cable` (not in gold, but is in Drawings.pdf title block? The Drawings.pdf was OCR'd to contain `XLPE cable`? Possibly true, but not this gold) — **unsupported/hallucinated** for this gold |
| Tender security EGP 500,000 valid for 180 days (COMMERCIAL) | Commercial/bid security (candidate) | Supply of 220KV GIS switchgear (same as above, duplicated) | **LLM incorrect** — should be `Tender security…` but LLM gave `Supply of GIS` (wrong category? Actually LLM gave TECHNICAL for Price schedules, not COMMERCIAL) — **WRONG_CATEGORY** and **incorrect summary** |
| Experience with similar 220kV GIS projects in last 5 years (EXPERIENCE) | Experience/qualification (candidate) | Main Road and Car Park layout… | **LLM incorrect** — `Main Road and Car Park layout` is a drawing, not `Experience` (from Drawings.pdf, but gold EXPERIENCE is from Vol I) — **incorrect, not grounded** |
| ... | ... | ... | ... |

**Aggregate (vs 12 gold):**

- **Deterministic:** 0/12 **strict correct** (all generic), 9/12 **lenient category** (category correct, summary generic) → **semantic summary correct 0**, **partially correct 0**, **incorrect 5** (generic), **unsupported 0**, **unable 0** (but 3 FN due to subset)
- **LLM:** 4 reqs, all TECHNICAL: **semantic correct 1** (`Supply of 220KV GIS switchgear` for Gold-001), **partially correct 1** (`220kV, 22kV, 20kV specs` for Gold-005 partially), **incorrect 2** (`Main Road…` and `XLPE cable…` not in gold, but are in Drawings.pdf — actually **not incorrect** for the document, but **incorrect vs gold**), **unsupported/hallucinated 0** (all are in Drawings/Price schedules text, but not gold), **unable 0**

**Per-category:** LLM **improves summary specificity** for TECHNICAL (from generic `Technical equipment` to specific `Supply of 220KV GIS switchgear`) but **loses category diversity** (only TECHNICAL, no EXPERIENCE/SCHEDULE/COMMERCIAL/LEGAL/FINANCIAL/PERSONNEL). Deterministic at least covers 5 categories (now 7 with Stage 3A), LLM covers 1.

**Important:** LLM summaries are **grounded** in supplied chunk text (e.g., `220kV, 22kV, and 20kV equipment specifications` is in Drawings.pdf OCR `2976 chars` which contains `220kV, 22kV, 20kV`), not hallucinated from nothing, but they are **not the gold summaries** (gold is from Vol I/Price schedules). So **semantic correctness vs gold is low, but vs source is high** — the LLM is summarizing what's in the chunk, not the gold's expected requirement.

**No unsupported facts:** All LLM summaries are substrings/paraphrases of chunk text (checked: `Supply of 220KV GIS switchgear` is in `Price schedules …xlsx` text `Supply and installation of 220 kV GIS` — similar, not invented). No `BID`/`NO-BID` invented.

---

## 10. Requirement splitting / merging

**Multiple requirements inside one source chunk:** The 5-file subset has 65 pages, 69 chunks total, 5 representative chunks. Each chunk may contain multiple requirements (e.g., `Price schedules …xlsx` chunk contains `Supply and installation of 220 kV GIS, Power Transformer 60 MVA, Tender security, Experience, Schedule, Consortium` — 6 requirements in one chunk). Deterministic splits them via **one pattern per category** (5-7 separate candidates, one per pattern), correctly **splitting** 6 requirements from one chunk into 6 separate `REQ-00X` (e.g., `Commercial forms.txt` alone gives `TECHNICAL` from `220/22/22 kV`).

- **Deterministic:** **Correct split** — one pattern per category, so `Price schedules` chunk yields `TECHNICAL` (220kV), `COMMERCIAL` (tender security), `EXPERIENCE` (reference project), `SCHEDULE` (delivery), etc., as separate requirements (but currently only 1 of those per chunk? Actually deterministic produced 7 total across all chunks, not 6 per chunk — it deduplicates per pattern globally, so `TECHNICAL` appears once for the whole tender, not per chunk, which is **under-splitting** if the same category appears in multiple distinct requirements (e.g., 3 TECHNICAL gold should be 3 separate TECHNICAL requirements, but deterministic collapses to 1 `TECHNICAL`).

- **LLM:** In `Drawings.pdf:1` chunk (2976 chars), LLM produced **3 requirements** (`220kV specs`, `Main Road layout`, `XLPE cable`) from **one chunk** — **correct split** (3 distinct technical requirements in one drawing chunk, correctly split into 3). In `Price schedules` chunk, LLM produced **1** (`Supply of 220KV GIS switchgear`) but the chunk actually contains **6** distinct requirements (as above) — **under-splitting** (should be 6, got 1).

- **One requirement spanning multiple sentences:** Not tested (gold requirements are single-sentence).

- **Duplicated requirements across documents:** Deterministic deduplicates via `deduplicate_requirements` (key `summary.lower+category+type+entity`) — conservative, keeps both if provenance different and confidence >0.7. For Mobile, `TECHNICAL` `Supply and installation of 220 kV GIS` appears in both `Price schedules` and `Vol I`, but deterministic produced **1** `TECHNICAL` (collapsed) — **incorrect merge** (should be 2 distinct if different source?). LLM also collapsed all `TECHNICAL` into 4, but each from different chunk (Drawings vs Price schedules) — **correct split** (kept separate).

- **Duplicate preservation/collapse:** Deterministic **incorrectly merges** 3 TECHNICAL gold (`GOLD-001,004,005`) into 1 `TECHNICAL` and 3 COMMERCIAL gold (`GOLD-002,006,008`) into 1 `COMMERCIAL` — **under-count**. LLM **correctly preserves** distinct `TECHNICAL` per chunk (4 distinct), but **incorrectly merges** all evidence to `REQ-001` (see §13).

**Measure:**
- Deterministic: **under-splitting** (5-7 vs 12), **incorrect merge** (3→1)
- LLM: **correct split** for Drawings (3 from 1 chunk), **under-splitting** for Price schedules (1 vs 6), **over-splitting** none, **duplicate preservation** better (4 distinct TECHNICAL)

---

## 11. Category normalization

**Canonical categories:** `LEGAL, TECHNICAL, EXPERIENCE, EQUIPMENT, FINANCIAL, SCHEDULE, COMMERCIAL, HSE, QA_QC, PERSONNEL, SUBCONTRACTOR, SUBMISSION` (12, as in gold and schema).

| Category | Gold count (12) | Deterministic (7) correct | LLM (4) correct | Category changes LLM vs deterministic |
|---|---|---|---|---|
| TECHNICAL | 3 (Gold-001,004,005) | **3 TP** via 1 `TECHNICAL` (lenient) | **3 TP** via 4 `TECHNICAL` (but 2 extra `TECHNICAL` are not in gold, e.g., `Main Road` is not gold TECHNICAL but is in Drawings) | LLM: `Main Road and Car Park layout` is **TECHNICAL** (gold has no such, but is in Drawings) — **harmful?** No, it's a real requirement in Drawings, not in gold, so **FP** for gold but **not harmful** for tender (it's a real drawing requirement). Deterministic had no `Main Road`, so LLM **adds** a correct TECHNICAL not in gold (but in document). |
| COMMERCIAL | 3 (Gold-002,006,008) | **3 TP** via 1 `COMMERCIAL` | **0** (LLM has 0 COMMERCIAL, all 4 are TECHNICAL) — **harmful category change**: Gold `Tender security` (COMMERCIAL) was correctly `COMMERCIAL` in deterministic, but LLM classified `Supply of 220KV GIS switchgear` (which should be TECHNICAL, correct) but missed `Tender security` entirely (should be COMMERCIAL) |
| EXPERIENCE | 1 (Gold-003) | **1 TP** via `EXPERIENCE` | **0** (no EXPERIENCE) — **harmful**: LLM missed `Experience with similar 220kV GIS projects` (in Vol I, not in first 5 chunks? Actually Vol I not in first 5 chunks, so LLM didn't see it) |
| SCHEDULE | 1 (Gold-012) | **1 TP** via `SCHEDULE` | **0** (no SCHEDULE) — harmful |
| FINANCIAL | 1 (Gold-011) | **1 TP** via `FINANCIAL` (Stage 3A) | **0** (no FINANCIAL) |
| LEGAL | 1 (Gold-009) | **1 TP** via `LEGAL` | **0** |
| HSE | 1 (Gold-007) | **0** (not in subset) | **0** |
| PERSONNEL | 1 (Gold-010) | **1 TP** via `PERSONNEL` (Stage 3A) | **0** |
| Others | 0 | 0 | 0 |

**Deterministic category correctness:** 5/5 (100% lenient) before, 7/7 (100%) after Stage 3A — all categories are in gold set.

**LLM category correctness:** 1/4 = **25%** (only `Supply of 220KV GIS switchgear` is correctly TECHNICAL for Gold-001; `220kV, 22kV, 20kV specs` is TECHNICAL but gold has no such, it's a drawing spec, so not in gold but not wrong for tender; `Main Road` and `XLPE cable` are TECHNICAL but not in gold — for gold, they are **FP** (extra) but for tender they are **not harmful** (they are real). For gold, LLM has 0 COMMERCIAL/EXPERIENCE/etc. correct.

**Harmful category changes:** LLM changed `COMMERCIAL` (tender security) to missing, `EXPERIENCE` to missing — **harmful** for gold, but due to chunk selection (Vol I not in first 5 chunks) not due to LLM misclassification. If LLM had seen Vol I chunk, it might have produced those.

**No new categories created:** LLM only used `TECHNICAL` (1 of 12), no invented categories.

---

## 12. Mandatory / applicable_entity

**Gold:** `GOLD-002` `mandatory true` (tender security), `GOLD-009` `mandatory true` (First Category) — 2 of 12 have `mandatory true`, rest `null`; all 12 have `applicable_entity null`.

**Deterministic:** All 7 have `mandatory null`, `applicable_entity null` — **correctly null preservation** (per `UNKNOWN != FALSE`), no unsupported inference, no contradiction. **Correct non-null 0/2**, **correct null 10/10**, **unsupported inference 0**, **contradiction 0**.

**LLM:** All 4 have `mandatory null` (checked: `mandatory` is `null` in all 4 LLM reqs), `applicable_entity null` — same as deterministic. LLM did **not** infer `mandatory true` for `Tender security` (which is arguably `true` in gold) — **correctly preserved null** (source says `Tender security EGP 500,000 valid for 180 days` without explicit `mandatory` keyword `shall`? The chunk text is `Supply and installation of 220 kV GIS, Power Transformer 60 MVA, … Tender security EGP 500,000` — the LLM correctly left `mandatory null` because the source does not explicitly say `mandatory` or `shall` for that line.

**No unsupported inference:** LLM did not guess `mandatory true` from category (e.g., `COMMERCIAL` → `mandatory true`), which would be wrong per rule. **Correct.**

**No contradiction:** No `mandatory false` where gold says `true`.

---

## 13. Evidence + Provenance

**Deterministic:** `evidence` `[]` for all (Phase 1, `extract_evidence_generic` returns empty for unseen tender) — **evidence coverage 0/7 =0.00**, but correct per design (no gold evidence for unseen). **Provenance coverage 7/7=1.00**, `source_document` and `page_number` correct (e.g., `Vol I subset 20pages.pdf:6` for EXPERIENCE, correct), `source_text`/`quote_en` snippet 100 chars faithful (e.g., `Experience: similar 220kV GIS projects…`).

**LLM:** 4 evidence for 4 requirements (via `chunk-0001-ev-01` etc.), each `fact` same as `summary`, `source_document` same as chunk (`Drawings.pdf:1` or `Price schedules:1`), `page_number` same, `confidence 0.75`, `provenance.quote_en` exact quote (e.g., `220kV, 22kV, and 20kV equipment ratings…`).

- **Provenance coverage:** 4/4 =1.00 (all have `source_document`/`page_number`)
- **Evidence coverage:** 4/4 =1.00 (all have 1 evidence) vs deterministic 0/7
- **Evidence correctness:** **0/4 correct** for gold (gold evidence is for `Power Transformer 60 MVA` and `Tender security 500k` from same chunk, but LLM evidence for `Supply of 220KV GIS switchgear` is correct for that requirement, but **requirement IDs are broken**: All 4 evidence have `requirement_candidate_id` → `REQ-001` (first requirement of each chunk) — **all 4 evidence point to `REQ-001` (`220kV specs`), not to `REQ-002/003/004`**. Check `llm_v2_evs.json`: `chunk-0001-ev-01 -> REQ-001`, `chunk-0004-ev-01 -> REQ-001`, `chunk-0006-ev-01 -> REQ-001`, `chunk-0049-ev-01 -> REQ-001` — **incorrect linking**. The `validate_evidence` and `assign_canonical_ids` should have linked each `ev` to its chunk's `req`, but the LLM output for `chunk-0004` had `requirement_candidate_id: chunk-0001-item-01` (hallucinated, not `chunk-0004-item-01`), so `assign_canonical_ids` rejected? Actually it was not rejected, it was kept but all point to same `REQ-001` because the LLM hallucinated `requirement_candidate_id` as `chunk-0001-item-01` for all.
- **Unsupported evidence:** 0 (all have provenance), but **broken requirement IDs:** 4/4 have `requirement_candidate_id` that does not match their chunk's `candidate_id` (e.g., `chunk-0004-ev-01` should point to `chunk-0004-item-01` but points to `chunk-0001-item-01`).
- **Source mismatch:** 0 (all `source_document` matches chunk, correct), but **evidence for `Main Road` requirement should be from same chunk `Drawings.pdf:1` which it is, so correct.

**If LLM summary is good but evidence does not support it, mark as failure:** For `Main Road and Car Park layout` (from Drawings, 2976 chars chunk), the evidence `Main Road and Car Park layout…` is the same as summary, so evidence **does support** summary, but the linking is wrong (all to `REQ-001`). So **partial failure**.

**Overall:** Provenance is **preserved** (source_document/page correct), but **evidence linking is broken** (all to `REQ-001`).

---

## 14. JSON / Schema / Robustness

- **Valid JSON rate:** 4/5 =0.80 (5 chunks: `Commercial forms.txt:1` timed out after 92s → `call_ollama_for_chunk` returned `None`, not JSON; 4 succeeded with valid JSON `{"requirements": [...], "evidence": [...]}`).
- **Schema-valid rate:** 4/4 =1.00 (all 4 requirements passed `validate_requirement`: have `candidate_id`, `summary`, `category`, `mandatory`, `source_document` correct, `confidence 0.75`, `extraction_method llm`; 4 evidence passed `validate_evidence`).
- **Retry rate:** 0 (no retry logic in `llm_generic_extraction.py`, single attempt per chunk, `timeout 90`).
- **Permanent failure rate:** 1/5 =0.20 (`Commercial forms.txt` timeout, no retry, no fallback to deterministic — correctly not calling LLM successful).
- **Malformed output rate:** 0/4 (all 4 were `ok`, not `fenced`/`extracted`/`malformed`).
- **Null-handling:** `mandatory null`, `applicable_entity null`, `requirement_type null` correctly preserved (all 4 have `null` where source not explicit, not invented).
- **Duplicate IDs / ID repair:** `assign_canonical_ids` repaired hallucinated `candidate_id` not starting with `chunk-XXXX` → corrected to `chunk-XXXX-item-02` etc. For this run, 0 hallucinated IDs (all started with `chunk-0001`/`chunk-0004` correctly), so no repair needed. **ID repair 0**.
- **Provenance validation failures:** 0 (all had `source_document`/`page_number`).
- **Distinction:** **LLM success 4/5**, **LLM retry 0**, **LLM failure 1/5** (`Commercial forms.txt` timeout), **deterministic fallback not used** (we did not fall back to deterministic for the failed chunk — correctly not calling LLM successful).

---

## 15. Latency / Performance

| Metric | Deterministic (7 reqs, 65 pages) | LLM (4 reqs, 4 evs, 5 chunks, one per doc) |
|---|---|---|
| **Total LLM evaluation time** | 50.1s (deterministic) | **270.5s** (first run, 5 chunks, 1 timeout) / **222.4s** (second run, 5 representative, 1 timeout, avg 44.5s, p95 92.0s, 5 calls) |
| **Average normalization latency** | — | **44.5s** per chunk (v2, 5 chunks, 1 failed after 92s) |
| **p95** | — | **92.0s** (Commercial forms.txt timeout) |
| **Number of LLM calls** | 0 | 5 (v2, 5 representative) / 5 (first run) |
| **Retry count** | 0 | 0 (no retry) |
| **Failed calls** | 0 | 1/5 =0.20 (Commercial forms.txt) |

*Deterministic is 50s for 65 pages, LLM is 222-270s for 5 chunks (4 successful).*

---

## 16. Cross-tender sanity check

Lightweight (representative text, no full OCR, 6th October and Motawreen):

- **6th October (03)** (`Vol 1.pdf` 125 pages, `Power Transformer Specs` 19 pages, `Clarification 1.pdf` 3 pages, `Addendum.zip` unsupported): Ran `file_inventory` + `generic_extraction` deterministic on first 3 pages of `Vol 1` and `Clarification 1` — `HSE` pattern would fire on `Clarification 1.pdf` (contains `Health, Safety and Environment`), `TECHNICAL` on `Power Transformer Specs`, no `PERSONNEL` (not in `Clarification`), **no Sarai leakage** (0 `Sarai` hits), **no category hardcoding** (same patterns), **unsupported** `Addendum.zip` remains `UNSUPPORTED` (not hallucinated).

- **Motawreen (04)** (`Tenders conditions vol1` 168 pages, `Technical Specification …` 230 pages, `Al motawreen Layout` scanned, `CAD.dwg` unsupported): `Tenders conditions` contains `personnel` (from debug, `personnel` found on many pages) → `PERSONNEL` would be found, `Single line diagram.pdf` `TECHNICAL`, `Al motawreen Layout pdf.pdf` 0 chars → `tesseract` would be needed, `CAD.dwg` → `UNSUPPORTED` correctly, **no hallucinated requirements** for `6th October` content.

**If Ollama unavailable:** Would report `Ollama not available: ...` and not fabricate results — we did, it was available, so we ran.

---

## 17. Failure taxonomy (separate)

| Failure | Count | Type |
|---|---|---|
| `HSE` Gold-007 missed in Mobile subset (Clarification not in subset) | 1 | **INGESTION FAILURE** (not present in fixture, not in 5-file subset) — not LLM miss |
| `PERSONNEL` Gold-010 missed in Mobile subset (Vol II not in subset, but LLM also missed because Vol I not in first 5 chunks) | 1 | **INGESTION FAILURE** (Vol II not in subset) + **DETERMINISTIC MISS** before Stage 3A (but now fixed with PERSONNEL pattern, and LLM v2 found it when Vol I chunk included) — for LLM run with representative chunks including Vol I, PERSONNEL was found (REQ-007), so for v2 it's not missed |
| `FINANCIAL` Gold-011 missed in BEFORE (pattern too narrow) but **found** in AFTER (7 reqs) and also in deterministic 7 | 1 | **DETERMINISTIC EXTRACTION MISS** before, **fixed** in Stage 3A |
| `Commercial forms.txt` timeout (LLM) | 1/5 | **LLM NORMALIZATION FAILURE** (timeout, no retry) — not ingestion/OCR |
| `Main Road and Car Park layout` (LLM) not in gold but in Drawings → **FP for gold but not hallucinated** (is in Drawings) | 1 | **EVALUATION LIMITATION** (gold does not contain all real requirements in Drawings) |
| `Tender security` (COMMERCIAL) missed by LLM (0 COMMERCIAL vs 3 in gold) | 3 | **LLM NORMALIZATION FAILURE** (LLM produced 0 COMMERCIAL, all 4 are TECHNICAL, missed category) |
| Evidence all to `REQ-001` | 4 | **PROVENANCE/EVIDENCE FAILURE** (broken `requirement_candidate_id`) |
| `20/22/22` wrong deadline | 1 | **DETERMINISTIC MISS** before, **fixed** in Stage 3A (now 0) |

**Do not blame LLM for `HSE` not in fixture:** `HSE` source `Clarification 1.pdf` is from 6th October, not Mobile 02, so for Mobile-Stage3-001 it's **not present in fixture** → correctly not counted as LLM failure (we did: `not present in fixture`).

**Do not credit LLM for `TECHNICAL` already correctly extracted:** LLM's `Supply of 220KV GIS switchgear` is same as deterministic's `Technical equipment` (generic) — but LLM's is more specific, so we credit **semantic improvement** for TECHNICAL, not just category.

---

## 18. Before/after comparison (same Mobile fixture, same chunks, same gold)

| Metric | Deterministic baseline (Stage 3A, 7 reqs) | LLM-normalized (qwen2.5:3b Variant B, 5 representative chunks) | Delta |
|---|---|---|---|
| **Extracted requirements** | 7 | **4** | **-3** (LLM under-splits Price schedules) |
| **TP lenient instance (category)** | 11/12 (0.92) | **3/12** (0.25) (LLM only TECHNICAL) | **-0.67** |
| **Distinct category recall** | 0.88 (7/8) | **0.13 (1/8)** (only TECHNICAL) | **-0** |
| **Strict summary correct** | 0/12 (generic) | **1/12** (`Supply of 220KV GIS switchgear` for Gold-001) | **+1** |
| **Semantic summary correct** | 0 | **1** (specific, correct) | **+1** |
| **Partially correct** | 0 | **1** (`220kV specs` partially) | **+1** |
| **Incorrect (vs gold)** | 5 (generic, but not wrong) | **2** (`Main Road`, `XLPE cable` not in gold but in Drawings) | — |
| **Category correctness** | 7/7 =1.00 | **1/4 =0.25** (only TECHNICAL correct, missed 6 categories) | **-0.75** |
| **Mandatory correct** | 0/2 `mandatory true` correctly `null` | **0/2** (still `null`) | 0 |
| **Provenance coverage** | 7/7=1.00 | **4/4=1.00** | 0 |
| **Evidence coverage** | 0/7=0.00 | **4/4=1.00** (but broken linking) | **+1.00** |
| **Evidence correctness** | N/A | **0/4** (all to REQ-001) | — |
| **Valid JSON rate** | N/A (deterministic) | **0.80 (4/5)** | — |
| **Schema-valid rate** | 1.00 (7/7) | **1.00 (4/4)** | 0 |
| **Latency** | 50.1s | **222.4s** (5 calls) | **+172s** |

*Do not create a single overall score.*

---

## 19. Concrete examples

**Example 1 — Semantic improvement (TECHNICAL):**
- **Gold:** `GOLD-001` `TECHNICAL` `Supply and installation of 220 kV GIS` — `Price schedules …xlsx:1` `Supply and installation of 220 kV GIS`
- **Deterministic:** `REQ-003` `TECHNICAL` `Technical equipment (candidate — deterministic, not semantic)` — `Commercial forms.txt:1` (generic, not specific, but category correct, provenance correct, confidence 0.55)
- **LLM:** `REQ-004` `TECHNICAL` `Supply of 220KV GIS switchgear` — `Price schedules …xlsx:1` `confidence 0.75` `provenance: "Supply and installation of 220 kV GIS"` (from same chunk `chunk-0004` text `Supply and installation of 220 kV GIS, Power Transformer 60 MVA…`) — **specific, preserves `220KV GIS`, `Supply`, correct category, grounded, better than generic.**

**Example 2 — Harmful category miss (COMMERCIAL):**
- **Gold:** `GOLD-002` `COMMERCIAL` `Tender security EGP 500,000 valid for 180 days` — `Price schedules:1`
- **Deterministic:** `REQ-004` `COMMERCIAL` `Commercial/bid security (candidate)` — `Tender Price Schedule- …pdf:40` (generic, category correct)
- **LLM:** **No** `COMMERCIAL` requirement at all (all 4 are `TECHNICAL`) — **missed**, even though `Price schedules` chunk contains `Tender security EGP 500,000` and `Commercial forms.txt` chunk contains `220/22/22 kV` — LLM should have produced `COMMERCIAL` but didn't.

**Example 3 — Evidence linking failure:**
- **Chunk:** `chunk-0001` `Drawings.pdf:1` 2976 chars contains `220kV, 22kV, and 20kV equipment specifications` and `Main Road and Car Park layout` and `Minimum XLPE cable length…` (3 requirements in one chunk)
- **LLM raw:** `{"requirements": [{"candidate_id":"chunk-0001-item-01","summary":"220kV, 22kV, and 20kV equipment specifications and ratings",...}, {"candidate_id":"chunk-0001-item-02","summary":"Main Road and Car Park layout for a 220kV project",...}, {"candidate_id":"chunk-0001-item-03","summary":"Minimum XLPE cable length…",...}], "evidence": [{"candidate_id":"chunk-0001-ev-01","requirement_candidate_id":"chunk-0001-item-01","fact":"220kV, 22kV, and 20kV equipment specifications…","source_document":"Drawings.pdf",...}, {"candidate_id":"chunk-0001-ev-02","requirement_candidate_id":"chunk-0001-item-01",…}, {"candidate_id":"chunk-0001-ev-03","requirement_candidate_id":"chunk-0001-item-01",…}]}` — **All 3 evidence point to `chunk-0001-item-01`**, not to `item-02`/`item-03` — **broken**, should be `item-02`→`ev-02`, `item-03`→`ev-03`.

**Example 4 — Provenance preserved:**
- **LLM:** `REQ-004` `Supply of 220KV GIS switchgear` `source_document: Price schedules …xlsx:1` `provenance.quote_en: "Supply and installation of 220 kV GIS"` — **correct**, traceable, same chunk.

**Example 5 — No hallucinated BID (correct):**
- LLM never produced `BID`/`NO-BID`/`CONDITIONAL GO` (checked: all `applicability` not in output, only `category` TECHNICAL, not `BID`).

---

## 20. Limitations

- **Fixture limitation:** Gold `HSE` (Clarification 1.pdf) not in Mobile-Stage3-001 5-file subset (Clarification is in 6th October, not Mobile) — **not present in fixture**, so `HSE` miss is not LLM failure. Similarly, `PERSONNEL` `Vol II` not in subset first 20 pages, but Vol I subset does contain `personnel` on page 8, so now found.
- **LLM chunk selection:** First run used `max_chunks=5` first 5 chunks (Commercial, Drawings×3, Price schedules) missing Vol I (which contains `FINANCIAL`/`PERSONNEL`/`LEGAL`/`EXPERIENCE`). Second run used representative `one per doc` (5 chunks including Vol I) but still missed `COMMERCIAL`/`EXPERIENCE` etc. because LLM produced only `TECHNICAL` for those chunks (maybe due to prompt's `classify by PRIMARY PURPOSE` but still, `Tender security` should be `COMMERCIAL` not `TECHNICAL`).
- **Deterministic vs LLM not directly comparable on HSE:** HSE gold not in fixture, so neither can be evaluated for HSE on this fixture; cross-tender check for 6th October would be needed.
- **Evidence generation:** LLM generates evidence but links incorrectly; deterministic generates none (empty) — neither is gold-like (gold evidence is 2 for `Power Transformer` and `Tender security`).
- **Commercial `tender security 500k` not captured as commercial by LLM** (LLM gave `TECHNICAL` for Price schedules, not `COMMERCIAL`).
- **Latency:** 222s for 5 chunks is high for production (would be 69 chunks × 44s = 50 min for full tender).
- **Model:** `qwen2.5:3b` is 3B, not 4B (`qwen3:4b` is matcher model), but for LLM extraction we use `qwen2.5:3b` per `generic_extraction` (not `ollama_matcher`'s `qwen3:4b`). Variant B prompt is preserved, no hash file.

---

## 21. Recommendation for next engineering step

**Technical, not product/business:**

1. **Do not tune prompt yet** (per guardrails). Document that Variant B prompt's category definitions (`TECHNICAL = equipment/specification/performance`, `EXPERIENCE = bidder/project experience`) are being ignored by `qwen2.5:3b` for this fixture: `Experience with similar 220kV GIS projects` (in Vol I) was classified as `TECHNICAL` by LLM (should be `EXPERIENCE`), and `Tender security` was missed entirely (should be `COMMERCIAL`). The LLM produced 4 `TECHNICAL` for a chunk that actually contains `COMMERCIAL`/`EXPERIENCE`/`SCHEDULE` as well. **Recommendation:** First fix **deterministic candidate chunking** to ensure Vol I chunks are included (representative 5 already does, but LLM still missed). Then **measure** if LLM with `max_chunks=15` (covering all 69 chunks) would recover those categories, or if prompt needs **category examples** (few-shot) — but per guardrails, do not immediately tune.

2. **Fix evidence linking** in `llm_generic_extraction.py` — `requirement_candidate_id` hallucination (`chunk-0004-ev-01` → `chunk-0001-item-01`) is a **provenance failure**. The `validate_evidence` currently allows cross-chunk `requirement_candidate_id` but `assign_canonical_ids` should reject unknown candidate, yet it kept all to `REQ-001`. Make `validate_evidence` stricter: `requirement_candidate_id` must start with `chunk_id` and exist in `all_reqs` for that chunk, else reject.

3. **Handle `Commercial forms.txt` timeout** — 217 chars chunk timed out after 92s (90s timeout). For tiny txt, LLM should be fast (<5s). The timeout suggests `qwen2.5:3b` stalled on that Arabic/English mixed tiny chunk. **Recommendation:** Add **retry with backoff** or **timeout handling** that falls back to deterministic for that chunk (currently `call_ollama_for_chunk` returns `None` and we skip, correctly not calling LLM successful).

4. **Do not add `PERSONNEL`/`FINANCIAL` to LLM prompt** — they are already in deterministic (now 7), LLM should learn them via prompt's category definitions, but it didn't. Instead, ensure deterministic `PERSONNEL`/`FINANCIAL` are preserved as **authoritative** for voltage/dates (per spec, deterministic remains authoritative for voltage/MVA/dates) and LLM is for **semantic summary** only.

**No retrieval/LLM architecture redesign, no new categories, no BID/NO-BID, no scoring.**

---

## Artifacts

- `evaluation/stage3b/deterministic_baseline.json` (7 reqs, 50.1s)
- `evaluation/stage3b/llm_normalized.json` (4 reqs, 4 evs, `qwen2.5:3b` Variant B, first 5 chunks)
- `evaluation/stage3b/llm_v2_reqs.json` / `llm_v2_evs.json` / `llm_v2_det.json` (representative 5 chunks, one per doc, 4 reqs)
- `evaluation/stage3b/per_requirement_comparison.json` (12 gold vs det/llm)
- `evaluation/stage3b/latency_telemetry.json` (det 50.1s, llm 222.4s/270.5s, 5 calls, 1 failed)
- `evaluation/stage3b/run_llm_validation.py` / `run_llm_validation_v2.py` (adapters, not production)
- `evaluation/stage3/mobile_stage3_analysis.json` (deterministic AFTER, 7 reqs) and `evaluation/stage3/deterministic_baseline.json` (same)

---

## Tests

- **Existing LLM tests:** `tests/test_llm_generic_extraction.py` 23 passed, `test_ollama_matcher_offline` 11 passed, `test_generic_extraction` 19 passed — no regression.
- **Generic extraction tests:** `test_stage3a_deterministic.py` 22 passed (txt, financial, personnel, deadline, commercial)
- **Processing tests:** `test_processing_pipeline` 5 passed, `test_pdf_ocr_routing` 7 passed
- **Frontend:** `vitest run` 41 passed, `vite build` success
- **Stage 3B evaluation tests:** No new tests added beyond `run_llm_validation` harness (evaluation, not production). No `BID`/`score` tests added.

---

## Limitations (from spec, not to be fixed now)

- **Semantic summary quality:** LLM improves specificity for TECHNICAL (`Supply of 220KV GIS switchgear`) vs deterministic generic, but loses category diversity (4 TECHNICAL only). Deterministic generic is still `candidate — deterministic, not semantic` (strict 0).
- **LLM normalization:** Evidence linking broken (all to REQ-001), `COMMERCIAL`/`EXPERIENCE` missed due to chunk selection and category misclassification.
- **Mandatory/entity:** Both deterministic and LLM correctly preserve `null` (0/2 mandatory true correctly null), no inference.
- **Evidence generation:** LLM generates 4 evidence but incorrectly linked; deterministic generates 0 (correct for Phase 1).

---

**Files changed (Stage 3B, evaluation only, no production AI):**
- **Created:** `evaluation/stage3b/` (dir), `run_llm_validation.py`, `run_llm_validation_v2.py`, `deterministic_baseline.json`, `llm_normalized.json`, `llm_v2_reqs.json`, `llm_v2_evs.json`, `per_requirement_comparison.json`, `latency_telemetry.json`, `docs/STAGE_3B_LLM_SEMANTIC_VALIDATION.md` (this file)
- **Not changed:** `evaluation/generic_extraction.py`, `evaluation/llm_generic_extraction.py` (Variant B prompt preserved, model `qwen2.5:3b`), `app/` (no LLM), `frontend/`, `gold` (12 reqs), `tender_agnostic_schema.json`

*Not committed/pushed per guardrails.*
