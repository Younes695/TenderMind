# Stage 4F — Production Intelligence + Throughput (evaluation/production-flagged)

## Flow
`app/pipeline/intelligence_runner.py`: discovery → compression →
structured-first → bounded AI (qwen minimal-1) → validation/provenance →
commercial/schedule → gaps → ambiguity → reconciliation MVP → risk → synthesis.
`run_4f.py`: `throughput` (Mobile 12-parent, real qwen, baseline vs BOQ) +
`concurrency` (c1 vs c2, n=38, warmed).

## Files
`throughput_baseline.json` (38 calls/202.4s), `throughput_optimized.json`
(26 calls/140.9s), `candidate_reduction.json` (31.6%, 26/26 retained),
`structured_coverage.json` (1 table/128 items), `concurrency_results.json`
(202.9→134.9s, 0 failures), `{reconciliation,gap,ambiguity,risk,synthesis}_samples.json`.

## Headline
Structured-first removes 31.6% of AI calls with zero semantic loss; c2 1.50×
with 0 failures; reconciliation MVP finds real BOQ conflicts; gaps/ambiguity/
risk/synthesis all grounded with explicit unknowns. Flag-gated; default path
byte-identical; qwen2.5:3b default; no auto-escalation; no new models.
