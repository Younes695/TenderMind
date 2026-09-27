# Stage 4D — Uncertainty Signals + Warmed Concurrency + Harder-Tender Validation

Evaluation/research only. Production default (qwen2.5:3b), contracts, provenance,
and UI all untouched; auto-routing stays OFF.

## Experiments
- A) Uncertainty signals on stored 4B/4C qwen rows (gold-free definitions,
  gold used post-hoc for evaluation only) + fresh qwen×2 self-consistency
  (n=16) + logprobs check (unavailable — documented, no config change).
- B) Warmed concurrency c=1/2/4/8 at n=32 fixed requests (fresh qwen calls).
- C) Harder tender: 6th October (Clarification + Transformer Specs + VOL1 pp1–30,
  native text, no OCR) → 282 candidates → explicit 22-row subset → 21 scored +
  1 AMBIGUOUS golds (manual dominant-purpose, provenance in manifest) →
  R0/R1/R3 with fresh calls. Mobile R3 reported as stored-row diagnostic.

## Files
`run_4d.py` (`signals|concurrency|harder_run`); `signal_catalog.json`;
`signal_evaluation.json`; `self_consistency.json`; `concurrency_results.json`;
`harder_all_candidates.json`; `harder_subset_unlabeled.json`; `harder_gold.json`;
`harder_tender_manifest.json`; `harder_qwen_rows.json`; `harder_escalations.json`;
`harder_tender_{r0,r1,r3,comparison}.json`; `cross_tender_comparison.json`;
`latency.json`; `resource_usage.json`; `environment_snapshot.json`.

## Headline
Signals: UNKNOWN/INVALID perfect-precision tiny-recall; KEYWORD_MISMATCH
rec 0.89/FPR 0.19 (best independent); SIGNAL_MISMATCH rec 0.72 but partly
circular (2 correct-override FPs); SLOW/LENGTH/VERBATIM/DEGENERATE useless;
self-consistency 16/16 agree (useless at temp 0); logprobs unavailable.
Concurrency: c2 best (1.64×, 0 errors); c4/c8 flat (contention); c2 safe, not
"production safe". Harder: R0 7/21 → R1 8/21 (3 esc) → R3 8/21 (11 esc, fixed 2
more but broke 2 correct — FPR cost demonstrated). Verdicts: signals WEAK
overall (keyword PROMISING-with-cost); routing PARTIAL; concurrency factual.
