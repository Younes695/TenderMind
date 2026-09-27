# Stage 3I — Pre-Segmented Single-Purpose Variant B Validation

**Date:** 2026-09-25
**Fixture:** 16 single-purpose candidates pre-segmented from 12 Mobile parent chunks (`evaluation/fixtures/mobile_llm_representative.json`, verbatim source text with spans; see `evaluation/stage3i/generated_candidates.json`)
**Model:** `qwen2.5:3b` at `http://localhost:11434` (available, `OK` all runs), temperature 0, timeout 90s — same settings as the existing LLM evaluator
**Variant B:** byte-for-byte unchanged (hash `9aa3e11254f672cd`), called through the existing `call_ollama_for_chunk` interface
**Branch:** `main` at `d58cbb2` (origin/main in sync) + uncommitted Stage 3A/3C/3D/3E/3F/3G/3H work + Stage 3I harness (evaluation-only, no push)

---

## 1. Objective

Test whether Variant B's TECHNICAL collapse decreases when segmentation is solved deterministically before the LLM call: split multi-requirement parent chunks into small single-purpose candidates with the existing deterministic signals, then send each candidate independently through the unchanged Variant B interface (expected: one requirement per candidate).

## 2. Hypothesis

Two contributors are suspected: (1) multi-requirement discovery/segmentation, (2) Variant B task/output-contract complexity. If contributor (1) dominates, pre-segmented single-purpose inputs should recover non-technical categories toward Stage 3H-A/B levels (7–8/12). If collapse persists at 3D/3E/3F levels (all TECHNICAL), contributor (2) or model capability dominates.

## 3. Exact controls

- Same 16 candidates in fixed order for A/B/C (3i-01…3i-16).
- Same model, endpoint, temperature 0, `stream: False`, JSON mode, timeout 90.
- Test A: minimal normalization prompt; Test B: A + concise definitions (both from Stage 3H, unchanged); Test C: unchanged production Variant B path.
- Only the prompt/task interface differs. No full-tender run, no Sarai, no production changes, gold untouched (obvious-purpose labels recorded in `generated_candidates.json`, same mapping as 3G/3H).

## 4. Segmentation method

Evaluation-only splitter (`evaluation/stage3i/presegment.py`, rules in `segmentation_rules.md`): split on newlines then abbreviation-safe sentence boundaries (`(?<=[.;?!])\s+(?=[A-Z0-9"\u201c])`, keeps `No. (1)` intact); run production `GENERIC_PATTERNS` per sentence; quality gate rejects `empty`, `tiny` (<20 chars), `ocr_garbage` (printable <0.7), `no_signal`, `mixed_multi_category` (3+ distinct hits). Accepted candidates carry verbatim text, spans, signal list, parent document/page. 12 parents → 16 accepted + 21 rejected.

## 5. Candidate quality

- **Parent chunks (12):** chunk-0000/0001/0002/0003/0004/0005/0007/0008/0009/0010/0011/0012 — multi-category ones prioritized (0000 has 6 requirements, 0001 commercial+financial, 0002 experience+financial+legal, 0005 commercial+financial+HSE+QA_QC, 0010 personnel+subcontractor).
- **Generated candidates (16 accepted):** one dominant purpose each (11 single-signal, 5 dual-signal where the second signal is a substring artifact, e.g., EXPERIENCE+TECHNICAL via `220kV`). Gold: TECHNICAL×1, COMMERCIAL×3, EXPERIENCE×1, SCHEDULE×2, LEGAL×2, FINANCIAL×2, EQUIPMENT×1, HSE×1, QA_QC×1, PERSONNEL×1, SUBCONTRACTOR×1. SUBMISSION uncovered — no deterministic pattern maps to it (`CVs must be submitted.` → `no_signal`), a reported deterministic gap.
- **Rejected (21):** `tiny` (e.g., `2- 220 kV GIS`, `Currency: EGP.`), `no_signal` (headers, `Deadline: submission 15 of March, 2024.` — the SCHEDULE pattern lacks `deadline`/`submission` terms; `Manufacturer: Hyosung…`, `OEM authorization…`, `CVs must be submitted.`), `mixed_multi_category` (the `Schedule No. (1) Bill of Quantities … 220/22/22 kV …` title line: SCHEDULE+TECHNICAL+COMMERCIAL).
- **Known signal gaps (not fixed here):** TECHNICAL fires on the substring `gis` inside `re**gis**tered` (3i-12 carries a spurious TECHNICAL signal); SCHEDULE misses explicit `Deadline:`/`submission` language; SUBMISSION/manufacturer/OEM/validity have no patterns.

## 6. Variant B results

**9/16 = 0.56.** Correct: TECHNICAL (3i-01), COMMERCIAL (3i-06), EXPERIENCE (3i-03), SCHEDULE (3i-04, 3i-15), FINANCIAL (3i-07, 3i-08), HSE (3i-10), LEGAL (3i-12, with `mandatory: True` supported by `must be registered`). Wrong: COMMERCIAL→FINANCIAL (3i-02, 3i-16), LEGAL→TECHNICAL (3i-05, degenerate `...` summary), EQUIPMENT→TECHNICAL (3i-09, `...`), QA_QC→TECHNICAL (3i-11), PERSONNEL→EXPERIENCE (3i-13), SUBCONTRACTOR→TECHNICAL (3i-14). Every candidate produced exactly 1 requirement + 1 evidence (16/16 exact-one rate, 0 multi, 0 empty). Mandatory: 1 explicit supported value (3i-12 `true`); rest null, no unsupported inference. Avg latency ~26.6s (≈4–5× A/B due to Variant B's larger output contract), p95 ~30.5s, timeouts 0, malformed 0.

## 7. Confusion matrix

C non-zero cells: TECHNICAL→TECHNICAL 1; COMMERCIAL→{FINANCIAL 2, COMMERCIAL 1}; EXPERIENCE→EXPERIENCE 1; SCHEDULE→SCHEDULE 2; LEGAL→{TECHNICAL 1, LEGAL 1}; FINANCIAL→FINANCIAL 2; EQUIPMENT→TECHNICAL 1; HSE→HSE 1; QA_QC→TECHNICAL 1; PERSONNEL→EXPERIENCE 1; SUBCONTRACTOR→TECHNICAL 1. Per-category accuracy is 0/1–2/2 (1–3 samples each) and must not be overread. Full matrices in `comparison_3i.json` / `confusion_matrix_3i.json`.

## 8. Stage 3H comparison

| Test | Accuracy | Collapse (non-TECHNICAL→TECHNICAL) |
|---|---|---|
| 3H-A minimal (12 snippets) | 7/12 = 0.58 | 1 (EQUIPMENT) |
| 3H-B minimal+defs (12) | 8/12 = 0.67 | 1 (EQUIPMENT) |
| 3H-C Variant B (12) | 6/12 = 0.50 | 4 (QA_QC, EQUIPMENT, SUBCONTRACTOR, SUBMISSION) |
| **3I-A minimal (16 candidates)** | **11/16 = 0.69** | **1 (EQUIPMENT)** |
| **3I-B minimal+defs (16)** | **11/16 = 0.69** | **1 (EQUIPMENT)** |
| **3I-C Variant B (16)** | **9/16 = 0.56** | **4 (LEGAL-consortium, EQUIPMENT, QA_QC, SUBCONTRACTOR)** |

Variant B on pre-segmented candidates (9/16) beats Variant B on raw snippets (6/12) by recovering SCHEDULE (2/2), FINANCIAL (2/2), LEGAL First-Category (1/2), HSE (1/1), but still collapses 4. Minimal prompts on the same candidates reach 11/16 with 1 collapse.

## 9. Parent-chunk traces (6 required + 1 mixed)

- **Legal (chunk-0008 → 3i-12 First-Category):** deterministic signals [TECHNICAL] (spurious `gis`-in-`registered`); Variant B raw → LEGAL, summary copies source verbatim, `mandatory: True`, evidence 1/1 source-local; gold LEGAL; **correct**. Trace: parent `Vol I p4` → candidate `3i-12` → B `LEGAL` → gold LEGAL → correct.
- **Financial (chunk-0002 → 3i-08 `Financial capacity: audited…`):** signals [COMMERCIAL, FINANCIAL]; B → FINANCIAL; gold FINANCIAL; **correct**.
- **Experience/personnel (chunk-0010 → 3i-13 `Personnel requirements: Key personnel…`):** signals [EXPERIENCE, PERSONNEL]; B → EXPERIENCE (summary copies full text incl. `Design Manager, Site Manager`); gold PERSONNEL; **semantic neighbor error** (same as 3G/3H everywhere).
- **Commercial/schedule (chunk-0001 → 3i-06 `Commercial terms: Fixed price…`):** signals [SCHEDULE, COMMERCIAL]; B → COMMERCIAL with full-text summary; gold COMMERCIAL; **correct**.
- **Technical (chunk-0003 → 3i TECHNICAL `Type tests… IEC 62271-100` — via 3H snippet set, and 3i-01 `Supply and installation…`):** B → TECHNICAL; gold TECHNICAL; **correct**.
- **Mixed/problematic (chunk-0000 title → rejected `mixed_multi_category`):** never sent to the model; correctly kept out. Mixed (chunk-0008 → 3i-12 carried spurious TECHNICAL signal yet B still classified LEGAL — signal mismatch did not force the outcome).

## 10. Error taxonomy (C, based on raw outputs)

- Correct 9 (all with verbatim-copy summaries, grounded).
- Semantic neighbor error 2: PERSONNEL→EXPERIENCE (3i-13), COMMERCIAL→FINANCIAL (3i-02, 3i-16 — same stable confusions as every prior stage).
- TECHNICAL collapse 4: LEGAL-consortium (3i-05, degenerate `...` summary), EQUIPMENT (3i-09, `...`), QA_QC (3i-11), SUBCONTRACTOR (3i-14).
- UNKNOWN 0, hallucination 0 (all summaries copy source; no invented quantities/BID), formatting/output error 2 (the two `...` degenerate summaries), timeout 0, ambiguous-candidate 0 (gate held: no mixed candidate was sent).

## 11. Latency

| Test | Total (16 calls) | Avg | p95 | Timeouts |
|---|---|---|---|---|
| A | ~102s | ~6.4s | ~20.7s (first-call warmup) | 0 |
| B | ~90s | ~5.6s | ~7.0s | 0 |
| C | ~426s | ~26.6s | ~30.5s | 0 |

Single-requirement calls are fast and reliable (48/48 succeeded across A/B/C). Variant B costs ~4–5× the minimal interface on identical inputs.

## 12. Limitations

- 16 candidates, 1–3 per category: per-category rates are binary and must not be overread; no significance claimed.
- Candidates derive from one tender's fixture; cross-tender check was deterministic-only (3C results reused: 6th Oct 2 reqs, Motawreen 1 req, no Sarai leakage, `220/22/22` not deadlines).
- SUBMISSION has no candidate (deterministic gap) so Variant B's SUBMISSION→TECHNICAL collapse from 3H-C could not be retested here.
- Single run per variant; temperature 0 but Ollama 3B showed wording variance in 3E/3F, so wording differences are not the measured signal (categories are).
- The two `...` degenerate C outputs suggest output-contract fragility on short inputs, distinct from classification.

## 13. Decision: B) PARTIALLY SUPPORTS TWO-STAGE PIPELINE

Collapse drops somewhat (3H-C on raw snippets: 4/12 collapse with 6/12 accuracy → 3I-C on pre-segmented: 4/16 collapse with 9/16 accuracy; category diversity rises from 6 distinct correct to 7), and exact-one output rate is perfect (16/16) with source-local evidence (16/16) — segmentation clearly helps structure. But important categories (QA_QC, EQUIPMENT, SUBCONTRACTOR, consortium-LEGAL) still collapse toward TECHNICAL under unchanged Variant B, while minimal prompts on the same candidates recover QA_QC/SUBCONTRACTOR/SCHEDULE/LEGAL-First-Category. So segmentation is necessary but not sufficient: Variant B's own output-contract complexity contributes independently. Not a total success (A requires diversity increase + mostly neighbor errors — diversity increased 6→7 correct categories but 4 TECHNICAL collapses remain), not a refutation (collapse rate nearly halved: 4/12 → 4/16 with broader coverage), not inconclusive (candidate quality is good: verbatim, single-purpose, spans recorded).

## 14. Recommended next stage

Narrow the remaining gap with a minimal output-contract experiment on the same 16 candidates: keep Variant B's wording but constrain the response to exactly the Test-A shape (single `{summary, category, mandatory, applicable_entity}` object, no candidate IDs/evidence/provenance in the model output; attach provenance deterministically afterward as the harness already can). If categories recover toward A/B levels (11/16), the limiter is output-contract complexity and the fix belongs in response shaping. If QA_QC/EQUIPMENT/SUBCONTRACTOR/consortium-LEGAL still collapse there, the limiter is semantic classification and only then is a model-capability experiment justified. No new categories, no few-shot, no BID logic, no Si fine-tuning.

---

**Files changed (Stage 3I, evaluation-only):**
- **Added:** `evaluation/stage3i/presegment.py`, `segmentation_rules.md`, `parent_chunks_3i.json`, `generated_candidates.json`, `rejected_candidates.json`, `run_3i.py`, `task_a_3i.json`, `task_b_3i.json`, `variant_b_outputs_3i.json`, `comparison_3i.json`, `confusion_matrix_3i.json`, `latency_3i.json`, `build_candidates.py`, `inspect_split.py`, `split_preview.txt`, `README.md`, `tests/test_stage3i_presegment.py` (8 tests), `docs/STAGE_3I_PRESEGMENTED_VARIANT_B_VALIDATION.md` (this file)
- **Not changed:** Variant B/C/D prompts, model, schema, evidence/provenance logic, chunking globally, deterministic extractor semantics, gold, frontend/backend, timeouts/decoding beyond reuse

*Not committed/pushed.*
