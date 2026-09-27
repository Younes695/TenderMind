# Stage 3H — Pre-Segmented Single-Requirement Validation

**Date:** 2026-09-25
**Fixture:** 12 single-requirement snippets, verbatim substrings of `evaluation/fixtures/mobile_llm_representative.json` (see `evaluation/stage3h/snippets_3h.json` for test_id, gold category, source document/page, exact text, selection reason)
**Model:** `qwen2.5:3b` at `http://localhost:11434` (available, `OK` all runs), temperature 0, timeout 90s — same settings as the existing LLM evaluator
**Branch:** `main` at `d58cbb2` (origin/main in sync) + uncommitted Stage 3A/3C/3D/3E/3F work + Stage 3H harness (evaluation-only, no push)

---

## 1. Objective

Isolate requirement discovery/segmentation (A) from semantic normalization/classification (B): give the model ONE pre-segmented requirement per call so it is never responsible for discovering multiple requirements, and measure whether the TECHNICAL collapse observed in multi-requirement extraction (Stages 3D/3E/3F: 9/9, 9/9, 7/7 TECHNICAL) disappears.

## 2. Hypothesis

The TECHNICAL collapse is caused by the larger combined task (discovery + segmentation + normalization + classification + evidence/JSON generation). If so, single-requirement inputs should recover non-technical categories and materially improve accuracy; if collapse persists even single-req, the limiter is semantic classification or model capability.

## 3. Exact controls

- Same 12 snippets in fixed order for A/B/C (G3H-01…G3H-12, one per category: LEGAL, EXPERIENCE, FINANCIAL, PERSONNEL, COMMERCIAL, SCHEDULE, TECHNICAL, HSE, QA_QC, EQUIPMENT, SUBCONTRACTOR, SUBMISSION).
- Same model (`qwen2.5:3b`), endpoint, temperature 0, `stream: False`, JSON mode, timeout 90.
- Test A: minimal normalization prompt (single requirement → `{requirements: [{summary, category, mandatory, applicable_entity}]}`, exactly one object, no definitions).
- Test B: Test A text + the concise 12-category definitions from Stage 3G Task B (no tender-specific examples, no gold answers).
- Test C: unchanged production Variant B path (`call_ollama_for_chunk` default, candidate IDs, evidence, provenance, same validation as Stages 3C–3F).
- Only the prompt/task interface differs. No full-tender run, no Sarai, no production changes, gold untouched.

## 4. Fixture

All 12 source texts occur verbatim in `mobile_llm_representative.json` (enforced by test). Each contains exactly one intended requirement (<300 chars, ≤2 sentence terminators, enforced by test). Coverage: all 12 categories with clean one-requirement material; no invented text.

## 5. Task A (single-req normalization)

**7/12 = 0.58.** Correct: EXPERIENCE, FINANCIAL, TECHNICAL, HSE, QA_QC, SUBCONTRACTOR, SUBMISSION. Wrong: LEGAL→SUBMISSION (`Tenderer registration requirement`), PERSONNEL→EXPERIENCE (`Experience of Project Manager…`), COMMERCIAL→FINANCIAL (`security deposit of 500,000 EGP…`), SCHEDULE→SUBMISSION (`The submission deadline is…`), EQUIPMENT→TECHNICAL (`60 MVA… power transformer…`). Timeouts 0, malformed 0, empty 0, multi 0. All summaries grounded (e.g., `Candidates must provide their resumes.` for `CVs must be submitted.`). Mandatory: 1 non-null (G3H-01 LEGAL snippet → `true`, supported by `must`); applicable_entity all null. Avg latency ~6.6s (17.4s first call warmup, ~5.5s after), p95 ~6.2s.

## 6. Task B (single-req + definitions)

**8/12 = 0.67.** Correct: LEGAL, EXPERIENCE, FINANCIAL, PERSONNEL, SCHEDULE, TECHNICAL, HSE, QA_QC. Wrong: COMMERCIAL→FINANCIAL (same as A), EQUIPMENT→TECHNICAL (same as A), SUBCONTRACTOR→multi (malformed second object `{"mandatory": true}` with no summary/category — formatting/output error, counted as incorrect not coerced), SUBMISSION→PERSONNEL (`Staff qualifications must be submitted in the form of CVs.` — neighbor error toward personnel content). Fixed vs A: LEGAL, SCHEDULE, PERSONNEL. Broke vs A: SUBCONTRACTOR (ok→multi), SUBMISSION (ok→PERSONNEL). Timeouts 0. Avg latency ~5.8s, p95 ~6.6s.

## 7. Task C / Variant B (single-req snippets through extraction interface)

**6/12 = 0.50.** Correct: LEGAL, EXPERIENCE, FINANCIAL, SCHEDULE, TECHNICAL, HSE. Wrong: PERSONNEL→EXPERIENCE, COMMERCIAL→FINANCIAL (same neighbor errors as A/B), QA_QC→TECHNICAL, EQUIPMENT→TECHNICAL, SUBCONTRACTOR→TECHNICAL, SUBMISSION→TECHNICAL with degenerate summary `...` (output-quality failure: literal ellipsis as summary and quote). Every snippet produced exactly 1 requirement + 1 evidence (12/12 correct split — no under/over-split at single-input level). All evidence 1-to-1 within-call and source-local per call (correct document/page per snippet); candidate IDs are all identical copies of the prompt example (`chunk-0001-item-01` / `chunk-0001-ev-01`), which the production 3C harness corrects to chunk-local IDs — without that correction they would collide if merged. Mandatory: 1 non-null (G3H-01 LEGAL → `true`, supported by `must be registered`); rest null, no unsupported inference. Avg latency ~25.9s (≈4–5× slower than A/B due to the larger Variant B output contract: candidate IDs, evidence, provenance, requirement_type). Timeouts 0, malformed 0.

## 8. Confusion matrices

Task A non-zero cells: LEGAL→SUBMISSION 1; EXPERIENCE→EXPERIENCE 1; FINANCIAL→FINANCIAL 1; PERSONNEL→EXPERIENCE 1; COMMERCIAL→FINANCIAL 1; SCHEDULE→SUBMISSION 1; TECHNICAL→TECHNICAL 1; HSE→HSE 1; QA_QC→QA_QC 1; EQUIPMENT→TECHNICAL 1; SUBCONTRACTOR→SUBCONTRACTOR 1; SUBMISSION→SUBMISSION 1.
Task B non-zero cells: same except LEGAL→LEGAL, SCHEDULE→SCHEDULE, PERSONNEL→PERSONNEL, SUBCONTRACTOR→multi (no prediction), SUBMISSION→PERSONNEL.
Task C non-zero cells: LEGAL→LEGAL, EXPERIENCE→EXPERIENCE, FINANCIAL→FINANCIAL, PERSONNEL→EXPERIENCE, COMMERCIAL→FINANCIAL, SCHEDULE→SCHEDULE, TECHNICAL→TECHNICAL, HSE→HSE, QA_QC→TECHNICAL, EQUIPMENT→TECHNICAL, SUBCONTRACTOR→TECHNICAL, SUBMISSION→TECHNICAL.
Per-category accuracy is 0/1 or 1/1 throughout (one snippet per category) and must not be overread. Full matrices in `evaluation/stage3h/comparison_3h.json`.

## 9. Raw outputs

Preserved verbatim in `task_a_3h.json`, `task_b_3h.json`, `task_c_3h.json` (requirement objects, evidence for C, status, latency per snippet). Nothing coerced: `bad_category`/`multi`/`malformed`/`empty`/`timeout` are recorded as incorrect with the raw text kept.

## 10. Latency

| Test | Total (12 calls) | Avg | p95 | Timeouts | Malformed | Empty/multi |
|---|---|---|---|---|---|---|
| A | ~79s | ~6.6s | ~6.2s | 0 | 0 | 0/0 |
| B | ~70s | ~5.8s | ~6.6s | 0 | 0 (1 multi) | 0/1 |
| C | ~311s | ~25.9s | ~29.3s | 0 | 0 | 0/0 |

Single-requirement calls are fast and reliable (0 timeouts across 36 calls); Variant B's larger contract costs ~4–5× latency vs minimal normalization even on identical inputs.

## 11. Error taxonomy (based on actual raw outputs)

- **Correct (A 7, B 8, C 6):** exact gold category with grounded summary.
- **Semantic neighbor error (A 4, B 3, C 2):** PERSONNEL→EXPERIENCE (all three; `Project Manager 10 years experience` contains experience language), COMMERCIAL→FINANCIAL (all three; tender-security overlaps financial language), SCHEDULE→SUBMISSION (A only; `submission deadline` contains submission), SUBMISSION→PERSONNEL (B only; `Staff qualifications… CVs` contains personnel content). Plausible adjacent-category confusions, never TECHNICAL.
- **TECHNICAL collapse (A 1, B 1, C 4):** EQUIPMENT→TECHNICAL in all three interfaces (stable: equipment characteristics read as technical specs — likely a schema-boundary overlap, not random); plus C-only QA_QC→TECHNICAL, SUBCONTRACTOR→TECHNICAL, SUBMISSION(`...`)→TECHNICAL.
- **UNKNOWN (0 all):** model never abstained.
- **Hallucination (0):** no summaries invented from nothing; all paraphrase the snippet (C copies source nearly verbatim).
- **Formatting/output error (B 1, C 1):** B G3H-11 returned a second fragment object `{"mandatory": true}` (multi); C G3H-12 returned literal `...` as summary and quote (degenerate, counted incorrect).
- **Timeout (0 all):** 36/36 calls succeeded.

## 12. Comparison with Stage 3G and 3D/3E/3F

- **3G pure classification:** A 8/12, B 9/12, collapse 0 both, 0 timeouts/invalid. **3H normalization:** A 7/12, B 8/12, C 6/12 — uniformly one point lower than the corresponding 3G interface, consistent with the JSON normalization task being harder than bare-label classification for this model.
- **3D/3E/3F multi-requirement extraction (Variant B/C/D on 69-chunk tender):** 9/9, 9/9, 7/7 TECHNICAL (collapse total). **3H single-requirement Variant B:** 4 collapse cases of 6 misses — collapse persists but is no longer total: LEGAL/EXPERIENCE/FINANCIAL/SCHEDULE/TECHNICAL/HSE are correctly normalized when pre-segmented, while QA_QC/EQUIPMENT/SUBCONTRACTOR/SUBMISSION still collapse.
- **Minimal prompts (A/B) vs Variant B (C) on identical snippets:** A/B recover QA_QC + SUBCONTRACTOR + SUBMISSION (+LEGAL/SCHEDULE/PERSONNEL in B) that C collapses — the Variant B interface itself contributes collapse beyond discovery/segmentation.
- **Stable across all interfaces (3G-A/B, 3H-A/B/C):** PERSONNEL→EXPERIENCE, COMMERCIAL→FINANCIAL, EQUIPMENT→TECHNICAL never resolve — model-level neighbor confusions and/or genuine schema overlaps, not prompt-specific.

## 13. Conclusion

TECHNICAL collapse **largely disappears when segmentation is solved AND the task interface is minimal** (A/B: 1 collapse case each, non-technical categories recovered), **but persists under Variant B even single-requirement** (C: 4 collapse cases). So the evidence supports a **combination**: (a) requirement discovery/segmentation is a major contributor (multi-req 9/9 collapse → single-req minimal 1/12 collapse-rate), (b) Variant B's prompt/output complexity is an independent contributor (same snippets: A/B recover QA_QC/SUBCONTRACTOR/SUBMISSION/LEGAL/SCHEDULE while C collapses them), (c) residual neighbor errors (PERSONNEL→EXPERIENCE, COMMERCIAL→FINANCIAL, EQUIPMENT→TECHNICAL) are stable model/schema-boundary confusions across all five interfaces tested.

## 14. Limitations

- 12 snippets, one per category: per-category accuracy is binary and must not be overread; no statistical significance claimed.
- High-signal snippets by design; real chunks are longer, noisier, multi-requirement — single-req accuracy overestimates production extraction accuracy.
- Single run per variant; temperature 0 but Ollama 3B showed wording variance in Stages 3E/3F, so small wording differences should not be over-interpreted (categories here were the measured signal).
- SUBMISSION gold for `CVs must be submitted.` is mildly ambiguous (personnel-adjacent); both readings are documented, not hidden.
- C candidate IDs all copy the prompt example (`chunk-0001-item-01`); production relies on the 3C harness correction — verified present, not re-tested here beyond recording raw IDs.

## 15. Recommended next stage

Do not change the model yet. Next controlled test: run Variant B on **deterministically pre-segmented single-purpose chunks** (split multi-requirement chunks by deterministic pattern hits so each chunk carries one dominant signal) and measure whether category diversity returns toward A/B levels. If it does, the fix belongs in chunking/task decomposition, not model selection. If Variant B still collapses QA_QC/EQUIPMENT/SUBCONTRACTOR/SUBMISSION on single-purpose chunks, that isolates prompt/output-complexity as the remaining cause and justifies a minimal Variant E that simplifies only the output contract (not categories, not examples). Model selection stays deferred until task-decomposition experiments also fail.

---

**Files changed (Stage 3H, evaluation-only):**
- **Added:** `evaluation/stage3h/snippets_3h.json`, `single_req_tasks.py`, `run_3h.py`, `task_a_3h.json`, `task_b_3h.json`, `task_c_3h.json`, `comparison_3h.json`, `README.md`, `tests/test_stage3h_single_req.py` (8 tests), `docs/STAGE_3H_SINGLE_REQUIREMENT_VALIDATION.md` (this file)
- **Not changed:** model, Variant B/C/D prompts, schema, evidence/provenance logic, chunking globally, deterministic extractor, gold, frontend/backend, timeouts/decoding beyond reuse

*Not committed/pushed.*
