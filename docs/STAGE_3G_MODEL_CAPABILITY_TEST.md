# Stage 3G — Controlled Model Capability Test

**Date:** 2026-09-25
**Fixture:** 12 short snippets, verbatim substrings of `evaluation/fixtures/mobile_llm_representative.json` (see `evaluation/stage3g/snippets_3g.json` for test_id, gold category, source document/page, exact text, selection reason)
**Model:** `qwen2.5:3b` at `http://localhost:11434` (available, `OK`), temperature 0, timeout 90s — same settings as the existing LLM evaluator
**Branch:** `main` at `d58cbb2` (origin/main in sync) + uncommitted Stage 3A/3C/3D/3E/3F work + Stage 3G harness (evaluation-only, no push)

---

## 1. Objective

Isolate MODEL CAPABILITY from the TenderMind extraction pipeline: can `qwen2.5:3b` correctly classify clearly identifiable tender requirements into the existing 12 generic categories when the task is reduced to single-label classification (no multi-requirement extraction, no summaries, no evidence, no canonical IDs)?

## 2. Exact experimental controls

- Same 12 snippets in the same fixed order for Task A and Task B.
- Same model (`qwen2.5:3b`), endpoint (`http://localhost:11434`), temperature 0, `stream: False`, timeout 90.
- Task A system prompt: bare label list + `Return ONLY the category label` (no definitions).
- Task B system prompt: Task A text + 12 one-sentence category definitions (no tender-specific examples, no gold answers).
- Only the definition block differs. No full-tender run, no Sarai data, no new gold (gold categories are the fixture's own obvious categories).
- Normalization for scoring strips whitespace/fences/quotes and accepts only an exact allowed label; anything else is recorded as invalid, never coerced.

## 3. Selected snippets and gold categories

| test_id | gold | source | exact source_text |
|---|---|---|---|
| G3G-01 | LEGAL | Vol I p4 | The tenderer must be registered Egyptian Union for Construction Contractors First Category. |
| G3G-02 | EXPERIENCE | Price schedules p1 | Experience: similar 220kV GIS projects in last 5 years. |
| G3G-03 | FINANCIAL | Vol I p1 | Financial capacity: audited financials turnover 100M EGP. |
| G3G-04 | PERSONNEL | Vol II p2 | Key personnel — Project Manager 10 years experience |
| G3G-05 | COMMERCIAL | Price schedules p1 | Tender security EGP 500,000 valid for 180 days. |
| G3G-06 | SCHEDULE | Vol I p1 | Deadline: submission 15 of March, 2024. |
| G3G-07 | TECHNICAL | Vol I p2 | Type tests: Routine tests and type tests for GIS per IEC 62271-100. |
| G3G-08 | HSE | Clarification 1 p1 | HSE: Health, Safety and Environment program must be submitted. |
| G3G-09 | QA_QC | Clarification 1 p1 | QA/QC: Quality assurance plan per ISO 9001. |
| G3G-10 | EQUIPMENT | Vol II p1 | Power Transformer 60 MVA, 220/22-11kV, ONAN cooling |
| G3G-11 | SUBCONTRACTOR | Vol II p2 | Subcontractor: maximum 30% of works may be subcontracted, subcontractor experience required. |
| G3G-12 | SUBMISSION | Vol II p2 | CVs must be submitted. |

Each has one dominant, obvious category. All texts occur verbatim in the representative fixture (enforced by `tests/test_stage3g_capability.py`). Note: two snippets were sent with a trivial trailing period that was removed afterward to make them exact substrings; wording is otherwise identical and the change has no semantic content.

## 4. Task A results (bare labels)

**8/12 = 0.67.** Correct: EXPERIENCE, FINANCIAL, TECHNICAL, HSE, QA_QC, EQUIPMENT, SUBCONTRACTOR, SUBMISSION. Wrong: LEGAL→SUBMISSION, PERSONNEL→EXPERIENCE, COMMERCIAL→FINANCIAL, SCHEDULE→SUBMISSION. Timeouts 0, invalid 0 (all 12 outputs were clean single labels). TECHNICAL collapse count: **0** (no non-TECHNICAL snippet labeled TECHNICAL). UNKNOWN count: 0. Avg latency ~3.7s (13.6s first call including connection warmup, then ~2.7s each), p95 ~3.4s excluding warmup.

## 5. Task B results (concise definitions)

**9/12 = 0.75.** Correct: LEGAL, EXPERIENCE, FINANCIAL, SCHEDULE, TECHNICAL, QA_QC, EQUIPMENT, SUBCONTRACTOR, SUBMISSION. Wrong: PERSONNEL→EXPERIENCE, COMMERCIAL→FINANCIAL, HSE→SUBMISSION. Timeouts 0, invalid 0. TECHNICAL collapse count: **0**. UNKNOWN count: 0. Avg latency ~2.8s, p95 ~3.4s.

Net vs A: +2 fixed (LEGAL, SCHEDULE), −1 broken (HSE→SUBMISSION, was correct in A), +1 accuracy overall.

## 6. Confusion matrices

Task A (rows gold, columns predicted; only non-zero shown): LEGAL→SUBMISSION 1; EXPERIENCE→EXPERIENCE 1; FINANCIAL→FINANCIAL 1; PERSONNEL→EXPERIENCE 1; COMMERCIAL→FINANCIAL 1; SCHEDULE→SUBMISSION 1; TECHNICAL→TECHNICAL 1; HSE→HSE 1; QA_QC→QA_QC 1; EQUIPMENT→EQUIPMENT 1; SUBCONTRACTOR→SUBCONTRACTOR 1; SUBMISSION→SUBMISSION 1.

Task B: LEGAL→LEGAL 1; EXPERIENCE→EXPERIENCE 1; FINANCIAL→FINANCIAL 1; PERSONNEL→EXPERIENCE 1; COMMERCIAL→FINANCIAL 1; SCHEDULE→SCHEDULE 1; TECHNICAL→TECHNICAL 1; HSE→SUBMISSION 1; QA_QC→QA_QC 1; EQUIPMENT→EQUIPMENT 1; SUBCONTRACTOR→SUBCONTRACTOR 1; SUBMISSION→SUBMISSION 1.

Per-category accuracy A: 8 categories 1.00 (EXPERIENCE, FINANCIAL, TECHNICAL, HSE, QA_QC, EQUIPMENT, SUBCONTRACTOR, SUBMISSION), 4 categories 0.00 (LEGAL, PERSONNEL, COMMERCIAL, SCHEDULE). B: 9 categories 1.00 (adds LEGAL, SCHEDULE; loses HSE), 3 categories 0.00 (PERSONNEL, COMMERCIAL, HSE).

## 7. Raw outputs

Task A raw (in order): `SUBMISSION`, `EXPERIENCE`, `FINANCIAL`, `EXPERIENCE`, `FINANCIAL`, `SUBMISSION`, `TECHNICAL`, `HSE`, `QA_QC`, `EQUIPMENT`, `SUBCONTRACTOR`, `SUBMISSION` (see `evaluation/stage3g/task_a_3g.json` for latencies).
Task B raw (in order): `LEGAL`, `EXPERIENCE`, `FINANCIAL`, `EXPERIENCE`, `FINANCIAL`, `SCHEDULE`, `TECHNICAL`, `SUBMISSION`, `QA_QC`, `EQUIPMENT`, `SUBCONTRACTOR`, `SUBMISSION` (see `evaluation/stage3g/task_b_3g.json`).
All outputs were clean single labels with no fences, explanations, or extra tokens.

## 8. Latency / timeouts

Task A total ~44s for 12 calls (13.6s first call, ~2.7s each after); Task B total ~34s (~2.7–3.4s each). Timeouts 0/12 both, invalid 0/12 both. Single-label classification is ~15× faster per call than full extraction (~45s avg in Stages 3C–3F).

## 9. Interpretation

1. **Can qwen2.5:3b perform simple single-label tender classification at all?** Preliminary evidence supports yes for most categories: 8/12 bare and 9/12 with definitions on obvious snippets, with clean formatting and no timeouts.
2. **Does it still classify unrelated obvious categories as TECHNICAL?** No — TECHNICAL collapse count is 0 in both tasks. The 9/9 TECHNICAL collapse seen in Stages 3E/3F extraction does not reproduce in pure classification.
3. **Does adding concise category definitions materially improve accuracy?** Modestly: 0.67 → 0.75 (+1 net; +2 fixed LEGAL/SCHEDULE, −1 broken HSE→SUBMISSION). Preliminary indication of small improvement, not a dramatic fix.
4. **Which categories are consistently confused with TECHNICAL?** None in this test. Persistent confusions are PERSONNEL→EXPERIENCE (both tasks; `Project Manager 10 years experience` contains experience language), COMMERCIAL→FINANCIAL (both tasks; tender-security overlaps financial language), and *-→SUBMISSION for document-flavored sentences (LEGAL `must be registered…`, SCHEDULE `Deadline: submission…` in A; HSE `…program must be submitted` in B — the word `submitted`/`submission` appears to attract SUBMISSION).
5. **Are errors semantic, formatting-related, or timeout-related?** Entirely semantic (plausible neighbor-category confusions); 0 formatting/invalid and 0 timeouts.
6. **Does the result support the hypothesis that the 3B model is the limiting factor?** Evidence is inconclusive for raw category knowledge but supports a narrower claim: the model *knows* the categories well enough for 8–9/12 obvious single-label cases, so the 9/9 TECHNICAL collapse in full extraction is likely related to the larger extraction task/prompt/representation (long chunks, multi-requirement output, prompt-example ID copying, JSON structure) rather than pure inability to distinguish categories.
7. **Does the result justify a model-selection experiment?** Preliminary indication: not yet on category-knowledge grounds alone. The evidence supports first testing extraction-task simplifications (e.g., per-requirement chunking or constrained decoding that already works in the pure task) before concluding a bigger model is required. A model-selection experiment remains reasonable only if task-simplification experiments also fail.

## 10. Limitations

- Tiny sample (12 snippets, one per category at most); per-category accuracy is 0/1 or 1/1 and must not be overread.
- Snippets are high-signal by design; real chunks are longer, noisier, and multi-requirement.
- Single run each; temperature 0 but Ollama 3B showed run-to-run wording variance in Stages 3E/3F, so small wording differences should not be over-interpreted (categories here were stable except HSE).
- SUBMISSION gold for `CVs must be submitted.` is mildly ambiguous (could be read as personnel-adjacent); it was classified SUBMISSION in both tasks, consistent with the document-submission reading.
- Two snippets had trivial trailing-period differences at run time vs the final verbatim fixture; no semantic difference.

## 11. Recommendation for next experiment

Keep the model. Next test whether constraining the extraction task toward single-label-like decisions recovers categories — e.g., run the existing Variant B/C/D pipeline on pre-segmented single-requirement chunks (one dominant requirement per chunk, using deterministic pattern hits to split) and measure whether category diversity returns. If categories recover on short single-purpose chunks but collapse on long multi-requirement chunks, the limiter is task representation/context handling, and the fix belongs in chunking/decoding rather than model selection. Only if that also fails would a controlled model-selection experiment (same 12 snippets + same 12 chunks, larger model) be justified.

---

**Files changed (Stage 3G, evaluation-only):**
- **Added:** `evaluation/stage3g/classification_tasks.py`, `snippets_3g.json`, `run_3g_capability.py`, `task_a_3g.json`, `task_b_3g.json`, `capability_summary_3g.json`, `README.md`, `tests/test_stage3g_capability.py` (7 tests), `docs/STAGE_3G_MODEL_CAPABILITY_TEST.md` (this file)
- **Not changed:** model, Variant B/C/D prompts, schema, evidence/provenance logic, gold, frontend/backend behavior, chunking, timeouts/decoding beyond reuse

*Not committed/pushed.*
