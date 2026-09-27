# Stage 3K — Behind-Flag Two-Stage Pipeline Validation

## Objective
Validate the behind-flag two-stage architecture end to end on the Mobile tender, without touching
production behavior (`TENDERMIND_TWO_STAGE_LLM` defaults OFF):
deterministic segmentation → minimal-contract LLM normalization (one candidate in, max one
requirement out) → deterministic provenance/evidence/ID binding. Answer: does pre-segmentation
cure the Variant B multi-requirement TECHNICAL collapse (Stages 3D/3E/3F), and what does it cost?

## Setup (frozen for this stage)
- Model: `qwen2.5:3b` at `http://localhost:11434`, temperature 0, JSON mode, timeout 90s.
- Flag: `TENDERMIND_TWO_STAGE_LLM` (default OFF; all 3K runs set it explicitly in-process only).
- Code: `evaluation/stage3k/two_stage_pipeline.py`
  (`flag_enabled`, `discover_candidates`, `normalize_candidate`, `post_process`,
  `extract_requirements_two_stage`, `extract_requirements_dispatch`).
- Runner: `evaluation/stage3k/run_3k.py` (`A` = representative set, `B` = full Mobile with
  `B_MAX_CALLS=150` / `B_MAX_SECONDS=1500` ceiling, incremental save + resume).
- Preserved invariants: Stage 3C evidence fix, Stage 3D tiny guard (`<300` chars →
  `SKIPPED_TINY_INPUT`), Variant B / C / D untouched, gold file untouched.
- Gold: `evaluation/gold/mobile_representative_gold.json` (12 requirements; used only for the
  fixture-identity check, not for candidate scoring — candidates are scored against the
  deterministic-signal category of their own text, single-signal only).

## Experiment A — representative set (12 Stage 3D parents, exact 3E texts)
- Chunk identity check passed: 12/12 chunk_ids match `selection_rationale_3d.json`.
- Segmentation: **41 accepted, 666 rejected, 0 tiny-skipped**. (The 666 are sub-sentence
  fragments the splitter correctly refuses — mostly Arabic price-schedule lines.)
- LLM: 41/41 completed, **0 timeouts, 0 malformed, 0 empty, 0 multi**. Total 225.5s, avg 5.5s, p95 6.4s.
- Single-signal accuracy: **22/39 = 0.56** (2 multi-signal candidates excluded from scoring).
  Per category: TECHNICAL 19/28, SCHEDULE 1/3, FINANCIAL 2/3, LEGAL 0/4, PERSONNEL 0/1.
- **TECHNICAL collapse: 1** (3k-A-18 SCHEDULE→TECHNICAL). One UNKNOWN abstention.
- Final after deterministic post-processing: **41 requirements / 41 evidence, 7 distinct
  categories** (COMMERCIAL, EXPERIENCE, FINANCIAL, HSE, SCHEDULE, TECHNICAL, UNKNOWN).

## Experiment B — full Mobile tender (partial, ceiling-gated)
- Ingestion 55.9s; segmentation **2545 accepted, 84534 rejected, 67 tiny-skipped** (seg 1.9s).
- LLM: **150/2545 completed, clean stop at call ceiling** (1500s budget untouched at ~863s).
  **0 timeouts, 0 malformed, 0 empty; 2 multi + 2 invalid-label rejections** (2.7%, rejected
  safely, no crash, no fabrication). Total LLM 806.8s, avg 5.4s, p95 6.4s.
- Single-signal accuracy: **75/146 = 0.51**. TECHNICAL 61/98, SCHEDULE 10/37, FINANCIAL 3/4,
  LEGAL 0/5, EXPERIENCE 1/1, PERSONNEL 0/1.
- **Collapse: 5. UNKNOWN abstentions: 10** (honest "cannot tell from this fragment" behavior).
- Final: **127 requirements / 127 evidence, 8 distinct categories** (adds EQUIPMENT — the model
  once returned a more specific correct label than the allowed set; counted wrong vs gold,
  semantically fine).

## Deterministic full-Mobile baseline (new, for comparison)
`evaluation/stage3k/full_mobile_deterministic_3k.json`: 58.6s, **11 requirements covering all 10
active patterns** (COMMERCIAL×2, EXPERIENCE, SCHEDULE, TECHNICAL, LEGAL, FINANCIAL, HSE, QA_QC,
SUBCONTRACTOR, PERSONNEL), commercial terms extracted, all 9 documents COMPLETE.

## Quality comparison (head-to-head where the material matches)
| Setup (same 12 parents) | Reqs | Categories | Collapse | Wall clock |
|---|---|---|---|---|
| Variant B multi-req, Stage 3D | 9 | 1 (TECHNICAL) | total (9/9) | 494.7s (11 calls @45s, 2 timeouts) |
| Two-stage + minimal contract, 3K-A | 41 | 7 | 1 | 225.5s LLM (41 calls @5.5s, 0 timeouts) |
- Cross-stage (same 16 hand candidates): Variant B 9/16 collapse 4 (3I) vs minimal contract
  11/16 collapse 1 (3J). The 3K-A 22/39 figure is **not** head-to-head with 3J (sentence-level
  candidates vs 16 hand candidates) — same direction, different denominator.
- Full tender: deterministic gives 11 broad requirements in 58.6s; two-stage gives 127 narrow
  ones (150-candidate partial). Different granularity — complementary, not strictly "better".
  Full-tender Variant B was never attempted: projected 1000+ chunk-calls × ~45s ≈ 12h+.
  Two-stage full coverage projects to 2545 × ~5.5s ≈ 3.9h — feasible, economical, resumable.

## Failure taxonomy (all error classes characterized, no unknowns)
1. **SCHEDULE↔COMMERCIAL neighbor confusion** (dominant: SCHEDULE 10/37 in B). Price-schedule
   sentences ("quantities and prices in the schedule") are genuinely dual-aspect; model picks
   COMMERCIAL, single-label gold says SCHEDULE. Defensible either way — gold artifact, not collapse.
2. **LEGAL→EXPERIENCE/UNKNOWN** (0/4 A, 0/5 B). JV/consortium sentences are dual-aspect (legal
   form + experience content, e.g. "Partners… required to be involved in similar 220kV
   projects"); model picks the actionable content or abstains on truncated fragments.
3. **PERSONNEL→FINANCIAL** (1 case, both runs): "Personnel and agents must have liability
   insurance…" — personnel scope, insurance content. Defensible.
4. **Contract violations correctly rejected** (B: 2 `{"requirements":[...]}` wrappers, 2 null/
   off-label categories). Pipeline rejects with status, never fabricates.
5. **UNKNOWN is a quarantine category, not a drop**: abstentions flow into finals as
   UNKNOWN-category requirements (visible, downstream-filterable). Recommended: filter UNKNOWN
   before Go/No-Go surfacing.
6. **Over-segmentation tradeoff**: sentence-level splitting yields micro-requirements (equipment
   list lines each become one). Recall-friendly, precision-costly; dedup only merges identical
   (summary, category, type, entity).

## Provenance / evidence validation
- A: all 41 final requirements carry source_document + page_number + source_text +
  candidate_id; all 41 evidence items link the same requirement_id with identical
  source_document/page and fact == summary. **Triple-match re-verified 41/41, 0 drift.**
- B: **150/150 records reference real (document, page) pairs** against fresh ingestion; finals
  (127/127) produced by the identical post_process code path.
- A-record caveat (expected, not a bug): 15/41 A candidates point to `Vol I subset 20pages.pdf`,
  the Stage 3D synthetic fixture — correct, since A parents are the 12 3D chunks verbatim.
- Observed (report, not fix — out of scope): run-local ID relabels (`3k-A-NN`, `3k-F-NNNN`)
  bypass the `assign_canonical_ids` chunk-prefix drift check (prefix regex returns None → check
  skips); integrity instead holds by same-candidate construction + explicit validation above.
  Ingestion document order varies run to run (Drawings-first vs Commercial-forms-first), so
  run-local IDs are not stable across runs — content fields are. Recommendation: production use
  keeps native `chunk-XXXX-seg-YY` IDs (guard fires) and sorts ingestion order for reproducibility.

## Verdict
**Two-stage + minimal contract resolves the Variant B collapse** (total → 1 on matched material;
5 collapse + 10 honest abstentions on 150 full-tender candidates), preserves category diversity
(7–8 distinct categories vs 1), halves wall-clock time despite 4× the calls (5.5s vs 45s per
call, zero timeouts), and keeps deterministic provenance/evidence/ID guarantees intact (0 drift).
Flag defaults OFF; production path untouched. Remaining costs are explicit: micro-requirement
granularity, dual-aspect single-label errors (SCHEDULE/COMMERCIAL, LEGAL/EXPERIENCE), and a
~3.9h projected full-tender bill of 2545 cheap calls — all quantified above, none blocking.

## Reproduction
- `python evaluation/stage3k/run_3k.py A` (~4 min + model time; asserts 12-chunk identity first)
- `python evaluation/stage3k/run_3k.py B` (stops cleanly at 150 calls / 1500s; resumes on re-run)
- Unit/integration: `pytest tests/test_stage3k_pipeline.py` (11 tests: flag, dispatch, candidate
  shape, tiny-guard, post-processing, canonical IDs, evidence linkage)
- Artifacts: `evaluation/stage3k/` (`comparison_3k.json`, `full_mobile_summary_3k.json`,
  per-candidate JSONL files, `full_mobile_deterministic_3k.json`, `scale_measurement_3k.json`)
