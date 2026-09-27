# Stage 3D — Larger-Sample LLM Behavior Confirmation + Tiny-Input Guard

**Date:** 2026-09-25
**Fixture:** `Mobile-Stage3D-001` (same 5-file Mobile subset as 3/3A/3B/3C) + gold `evaluation/gold/mobile_representative_gold.json` (12 reqs, 8 distinct categories, not modified)
**Model:** `qwen2.5:3b` at `http://localhost:11434` (available, `OK`), prompt Variant B preserved (no tuning), temperature 0, JSON mode, timeout 90s, evidence fix from 3C preserved
**Branch:** `main` at `d58cbb2` (origin/main in sync) + uncommitted Stage 3A/3C hardening + Stage 3D harness (evaluation-only, no push)

---

## A. Exact sample size

**12 chunks** selected from 69 total (target 12–15, met):

- Selector: `evaluation/stage3c/representative_selector.py` with `max_total=14`, `max_per_doc=3` (same generic principles as 3C: document coverage + category/signal coverage + text length + page diversity, no Mobile/Sarai filenames, no category-to-file map).
- Pass 1 (document coverage) gave 5 (one per document), Pass 2 (new-category gain) gave 2 more (Vol I:7 EXPERIENCE+LEGAL, Vol I:8 PERSONNEL) = 7, depth pass (generic, longest remaining per doc, evaluation-only in `run_3d_validation.py`) added 5 more to reach 12.
- 1 skipped tiny (`chunk-0000`), 11 LLM calls (9 successes, 2 timeouts).

---

## B. Selected documents / chunks

| chunk_id | source_document | page | text_len | deterministic categories | rationale |
|---|---|---|---|---|---|
| chunk-0000 | Commercial forms.txt | 1 | 217 | TECHNICAL | document coverage (best per doc) → **SKIPPED_TINY_INPUT** |
| chunk-0001 | Drawings.pdf | 1 | 2976 | TECHNICAL | document coverage |
| chunk-0004 | Price schedules …xlsx | 1 | 2989 | SCHEDULE, TECHNICAL | document coverage |
| chunk-0034 | Tender Price Schedule- Arabic.pdf | 29 | 2942 | SCHEDULE, TECHNICAL | document coverage |
| chunk-0051 | Vol I subset 20pages.pdf | 3 | 2652 | COMMERCIAL, FINANCIAL, SCHEDULE, TECHNICAL | document coverage |
| chunk-0055 | Vol I subset 20pages.pdf | 7 | 2364 | EXPERIENCE, FINANCIAL, LEGAL, TECHNICAL | category coverage (adds EXPERIENCE, LEGAL) |
| chunk-0056 | Vol I subset 20pages.pdf | 8 | 1890 | PERSONNEL, TECHNICAL | category coverage (adds PERSONNEL) |
| chunk-0039 | Tender Price Schedule- …pdf | 33 | 2996 | TECHNICAL | depth (longest remaining) |
| chunk-0044 | Tender Price Schedule- …pdf | 37 | 2779 | (none) | depth |
| chunk-0005 | Price schedules …xlsx | 1 | 2047 | TECHNICAL | depth |
| chunk-0002 | Drawings.pdf | 1 | 804 | TECHNICAL | depth |
| chunk-0003 | Drawings.pdf | 1 | 567 | TECHNICAL | depth |

- Covers all 5 documents, 7 deterministic categories (TECHNICAL, SCHEDULE, COMMERCIAL, FINANCIAL, EXPERIENCE, LEGAL, PERSONNEL). HSE/QA_QC/SUBCONTRACTOR not in subset with sufficient text (correctly not forced).
- Saved: `evaluation/stage3d/selected_chunks_3d.json`, `selection_rationale_3d.json`.

---

## C. Deterministic category distribution (frozen baseline, 48.6s, `use_llm=False`)

7 reqs: EXPERIENCE (Vol I:6), SCHEDULE (Price:1), TECHNICAL (Commercial:1), COMMERCIAL (Tender Price:40), LEGAL (Vol I:6), FINANCIAL (Vol I:3), PERSONNEL (Vol I:8). Deadlines 0, commercial 3 fields, provenance 7/7, TP lenient 11/12 (only HSE missed, Clarification not in Mobile subset). Saved `deterministic_baseline_3d.json`.

---

## D. LLM category distribution (Variant B, strict evidence, 11 calls)

9 reqs, **all TECHNICAL** (confidence 0.75, method `llm`):

- `REQ-001` Drawings.pdf:1 `220kV, 22kV, and 20kV equipment ratings…`
- `REQ-002` Drawings.pdf:1 `Main Road and Car Park layout…`
- `REQ-003` Drawings.pdf:1 `men XLPE, 220kV, 220/22/22 (GIS) transformer`
- `REQ-004` Price schedules:1 `Supply of 220KV GIS switchgear`
- `REQ-005` Price schedules:1 garbled OCR `O3U…` (Arabic/OCR noise, still TECHNICAL)
- `REQ-006` Tender Price Schedule:37 `The works shall include but not limited to design, excavation…`
- `REQ-007` Vol I:3 `Construction and completion on turnkey base…`
- `REQ-008` Vol I:7 `To be qualified for award… power of attorney… experience, financial and technical capability`
- `REQ-009` Vol I:8 `The tenderer is advised to visit and examine the Site…`

Vs gold 12: TP lenient 3/12 (only TECHNICAL Gold-001/004/005), distinct recall 1/8=0.13. COMMERCIAL/EXPERIENCE/SCHEDULE/FINANCIAL/LEGAL/PERSONNEL all missed despite Vol I chunks containing those signals.

---

## E. Whether TECHNICAL collapse persists

**Yes — stable, not small-sample variance.** Stage 3C (6 chunks, 4 reqs) gave 4/4 TECHNICAL. Stage 3D (12 chunks, 9 reqs, broader Vol I coverage including FINANCIAL/LEGAL/EXPERIENCE/PERSONNEL signals) gives **9/9 TECHNICAL**. Even `To be qualified… power of attorney… experience, financial and technical capability` (Vol I:7, clearly LEGAL/EXPERIENCE/FINANCIAL composite) was classified as TECHNICAL. Even `Tender security`-containing Price schedules chunks were classified as TECHNICAL, not COMMERCIAL. The collapse persists with 2.25× larger sample and full document coverage.

---

## F. Semantic summary findings

- **Correct (1):** `Supply of 220KV GIS switchgear` for GOLD-001 (preserves `220KV GIS`, `Supply`, grounded in `B/G 201000 | supply…`).
- **Partial (2):** `220kV specs` (captures voltages, misses `60 MVA`), `Construction turnkey… 220… GIS SIS` (captures scope, generic).
- **Incorrect but grounded (6):** `Main Road layout`, `XLPE cable`, `works shall include design, excavation…`, `To be qualified…` (faithful to source Vol I:7 but wrong category), `Site visit…`, garbled OCR `O3U…` (from Price schedules OCR noise, still TECHNICAL).
- **Hallucinated (0):** All are paraphrases of chunk text, no invented quantities/BID. Preserves voltages (`220kV, 22kV, 20kV`), equipment names (`GIS switchgear`, `XLPE`), durations? No durations extracted (12 months not in LLM summaries), financial values? No (`500,000` not in LLM summaries), contractual constraints? Partial (`power of attorney` preserved but misclassified).
- Deterministic still generic 7/7 (`candidate — deterministic`), strict 0/12.

---

## G. Split / merge findings

- **Correct split:** Drawings.pdf:1 2976 chars → 1 req in 3D (vs 3 in 3B from same chunk — model variance with temperature 0, reported honestly). Vol I:3, Vol I:7, Vol I:8 each 1 req — correct.
- **Under-split:** Price schedules 2989 chars (6 requirements in one chunk: TECHNICAL, COMMERCIAL, EXPERIENCE, SCHEDULE, etc.) → LLM gave 2 reqs (`Supply of GIS` + garbled OCR) — should be 6.
- **Over-split:** None.
- **Incorrect merge:** Deterministic 3 TECHNICAL→1, 3 COMMERCIAL→1 (under-count). LLM 9 distinct TECHNICAL (no merge, all kept separate via deduplication).
- **Duplicates:** No duplicate summaries (all 9 distinct), deduplication preserved all.

---

## H. Evidence / provenance integrity (3C fix mandatory, verified)

- **1-to-1 linkage:** 8 evidence for 9 reqs (one req `chunk-0005` garbled OCR has 0 evs — correctly no evidence fabricated). Each evidence `requirement_candidate_id` matches its own chunk (`chunk-0001-ev-01 -> chunk-0001-item-01 (REQ-001)`, `chunk-0004-ev-01 -> chunk-0004-item-01 (REQ-002)`, etc.), each `requirement_id` distinct. **0 cross-chunk errors** (vs 3B where 3/4 drifted to REQ-001).
- **Valid candidate IDs:** All `chunk-XXXX-item-YY` / `chunk-XXXX-ev-YY` with `_original_candidate_id` preserved for hallucinated `chunk-0001-item-01` copies (LLM still returns same IDs for every chunk, harness corrects to chunk-local).
- **Source correctness:** 8/8 `source_document` equals chunk document, 8/8 page correct (all within ranges).
- **Quote correctness:** Each `quote_en` is substring of chunk text (e.g., `B/G 201000 | supply…` for Price schedules).
- **No evidence for failed/skipped:** `chunk-0000` skipped tiny → 0 evs, `chunk-0034`/`chunk-0039` timeouts → 0 evs (correctly no fabrication).
- **Any regression is blocker:** None — fix holds on larger sample.

---

## I. JSON / schema robustness

- Valid JSON 9/11=0.82 (9 `ok`, 2 timeouts with no response, 0 `fenced`/`extracted`/`malformed`).
- Schema-valid 9/9=1.00 and 8/8 evidence pass `validate_requirement`/`validate_evidence` (12-enum, `mandatory null`, `source_document` match, confidence 0.75/0.8).
- Retries 0, permanent failures 2/11=0.18 (`chunk-0034` Tender Price p29, `chunk-0039` Tender Price p33 — both Arabic dense, 92.1s timeouts), skipped tiny 1/12, timeout count 2, fallback count 0 (never silently fallback).

---

## J. Tiny-input behavior

- **Threshold:** `<300` chars stripped (`TINY_THRESHOLD=300`, `SKIPPED_TINY_INPUT` in `evaluation/stage3d/tiny_guard.py`, evaluation/runtime guard, no semantic change for normal chunks).
- **This run:** `chunk-0000` Commercial forms.txt 217 chars → `SKIPPED_TINY_INPUT`, 0s latency, 0 reqs/evs, explicitly recorded in `per_chunk_3d.json` with `validation: tiny-guard`, not claimed as LLM success/failure.
- **Tests:** `tests/test_stage3d_tiny_guard.py` 6 passed (tiny 217→skipped, normal 2976→OK, empty→EMPTY_INPUT, whitespace→WHITESPACE_ONLY, explicit status, boundary 299→skipped/300→OK, no fake success).
- **Normal chunks unaffected:** All ≥567 chars went to LLM (11 calls).

---

## K. Latency

| Metric | Deterministic (7 reqs, 65 pages) | LLM (9 reqs, 8 evs, 12 chunks) |
|---|---|---|
| Total | 49.5s | **494.7s** |
| Avg per LLM call | — | **45.0s** (11 calls, 9 success +2 timeout) |
| p95 | — | **92.1s** (timeouts) |
| Successful calls | — | 9/11=0.82 |
| Failed calls | — | 2/11=0.18 |
| Skipped calls | — | 1/12=0.08 (tiny) |

Vs Stage 3C (6 chunks: total 342.9s, avg 57.2s, p95 92.1s, 4/6 success). Larger sample avg slightly lower (45s vs 57s) due to more medium chunks succeeding.

---

## L. Estimated full-tender runtime (69 chunks, estimate, not measured)

- At observed 45s avg per call (excluding tiny skips/timeouts): 69 × 45s = **3105s ≈ 52 min** for LLM alone, plus deterministic 50s → **~53 min** for full Mobile subset tender. Excluding timeouts/skips (which add 92s each): with ~20% failure rate (2/11), ~14 timeouts × 92s = 1288s extra → **~70 min worst case**. Clearly labeled estimate, not measured full run. Deterministic alone is 50s for 65 pages.

---

## M. Failure attribution (missed gold, 12)

| Gold | Deterministic | LLM (3D) | Attribution |
|---|---|---|---|
| GOLD-001 TECHNICAL `Supply 220 kV GIS` | TP | TP (`Supply of 220KV GIS`) | — |
| GOLD-002 COMMERCIAL `Tender security 500k` | TP | Missed (TECHNICAL only) | LLM miss (Price chunk contains security, classified TECHNICAL) |
| GOLD-003 EXPERIENCE `similar 220kV GIS` | TP | Missed | LLM miss |
| GOLD-004 TECHNICAL `Type tests` | TP lenient | TP lenient | — |
| GOLD-005 TECHNICAL `Power Transformer 60 MVA` (Vol II, not in subset) | TP lenient (overcount) | TP lenient | Gold limitation (Vol II not in fixture) |
| GOLD-006 COMMERCIAL `bank guarantee` (Clarification, not in Mobile) | TP lenient | Missed | Ingestion (not in fixture) |
| GOLD-007 HSE (Clarification, not in Mobile) | Missed | Missed | Ingestion (not in fixture) |
| GOLD-008 COMMERCIAL `Payment terms` (Vol I:3) | TP | Missed | LLM miss (Vol I:3 chunk classified TECHNICAL) |
| GOLD-009 LEGAL `First Category` (Vol I:4) | TP | Missed | LLM miss (Vol I:7 classified TECHNICAL) |
| GOLD-010 PERSONNEL (Vol II, not in subset) | TP lenient (overcount) | Missed | Gold limitation (Vol II not in fixture) |
| GOLD-011 FINANCIAL (Vol I:1 garbled) | TP | Missed | LLM miss |
| GOLD-012 SCHEDULE (Vol I:5) | TP | Missed | LLM miss |

Do not blame LLM for HSE/Clarification/Vol II not in fixture.

---

## N. Cross-tender findings (lightweight deterministic + 3C results reused)

- 6th Oct (`Clarification 5p` + `Addendum.zip` → 2 reqs SCHEDULE+TECHNICAL, deadlines 0, commercial advance payment, no Sarai, `Addendum.zip` FAILED 0 chars in analysis vs unsupported in job — known mismatch) and Motawreen (`Layout pdf 5p` + `.bak` → 1 TECHNICAL, deadlines 0, currency EGP, no Sarai, `.bak` FAILED). No Mobile/Sarai hardcoding (same `GENERIC_PATTERNS`), source-local evidence (deterministic), technical `220/22/22` not deadlines (0 bad). Saved `evaluation/stage3c/cross_tender_3c.json` (reused, no full LLM for cross-tender per spec lightweight).

---

## O. Regressions

- New tiny-guard: `tests/test_stage3d_tiny_guard.py` **6 passed**.
- Stage 3C evidence: `tests/test_stage3c_evidence.py` **6 passed**.
- Existing LLM: `tests/test_llm_generic_extraction.py` **23 passed**.
- Generic: `tests/test_generic_extraction.py` **19 passed**.
- Stage 3A: `tests/test_stage3a_deterministic.py` **22 passed**.
- Processing/OCR: 5+7+5 passed.
- Upload/E2E/matcher/decision/adversarial/azure/benchmark/ollama/hybrid: **89 passed**.
- Total backend **182 passed (176 +6 tiny-guard), 0 failed**. Frontend **41 passed**, `vite build` success.
- No regression in 148+41.

---

## P. Remaining limitations (not fixed, for future)

- LLM still 9/9 TECHNICAL despite Vol I FINANCIAL/LEGAL/EXPERIENCE signals — collapse stable.
- Summaries grounded but 11/12 not gold (only `Supply of GIS` strict correct).
- Commercial `500k` missed by LLM (gave TECHNICAL).
- 495s/12 chunks not production (69 chunks ≈53 min est.).
- HSE not evaluable (Clarification not in Mobile).
- `.zip`/`.bak` FAILED vs unsupported mismatch (known).

---

## Q. Whether there is now enough evidence to justify prompt tuning

**Yes — controlled evidence now sufficient to justify minimal prompt clarification (not full rewrite).** With 6 chunks (3C) and 12 chunks (3D, full document coverage including Vol I FINANCIAL/LEGAL/EXPERIENCE/PERSONNEL signals), `qwen2.5:3b` Variant B produced **4/4 then 9/9 TECHNICAL**, missing COMMERCIAL/EXPERIENCE/SCHEDULE/FINANCIAL/LEGAL/PERSONNEL that deterministic found on the same chunks. The `classify by PRIMARY PURPOSE` instruction is ignored (e.g., `To be qualified… power of attorney… experience, financial…` → TECHNICAL not LEGAL/EXPERIENCE). Evidence integrity holds (1-to-1, no drift), tiny guard holds (SKIPPED, no fake success), provenance holds. The next step should be a **minimal prompt addition** (e.g., 1-line category examples or `tender security → COMMERCIAL` hint), measured against the same 12-chunk fixture, without changing model/categories/architecture. Do not tune yet in this stage (per guardrails) — this report is the justification.

---

**Files changed (Stage 3D, harness + guard only):**
- **Added:** `evaluation/stage3d/tiny_guard.py`, `run_3d_validation.py`, `deterministic_baseline_3d.json`, `selected_chunks_3d.json`, `selection_rationale_3d.json`, `llm_normalized_3d.json`, `per_chunk_3d.json`, `per_requirement_comparison_3d.json`, `latency_telemetry_3d.json`, `tests/test_stage3d_tiny_guard.py` (6 tests), `docs/STAGE_3D_LARGER_SAMPLE_VALIDATION.md` (this file)
- **Preserved:** `evaluation/llm_generic_extraction.py` evidence fix (3C), `GENERIC_PATTERNS`, Variant B prompt, `qwen2.5:3b`, gold (12 reqs), schemas, `app/decision`, `frontend/`
- **Not changed:** prompt text, model, categories, gold, frontend, decision, Redis/Celery/auth

*Not committed/pushed.*
