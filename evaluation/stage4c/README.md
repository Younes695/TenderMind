# Stage 4C — Routing Validation + Performance Benchmark (evaluation-only)

Validates qwen2.5:3b →(observable failure)→ gemma3:12b escalation. No production
change; qwen2.5:3b stays the default; no policy enabled anywhere in prod.

## Policies
- R0: qwen only (exact Stage 4B stored rows).
- R1: escalate on provider_error|timeout|malformed|wrong_shape|multi|
  bad_category|empty|empty_summary|UNKNOWN. No gold, no correctness, no
  difficulty input — enforced by function signatures.
- R2: R1 + deterministic degenerate heuristics (placeholder-like,
  token-repetition, blank). No confidence invented.
- Oracle: post-hoc diagnostic only (labeled DIAGNOSTIC).

## Files
- `run_4c.py` — `route` (R0/R1/R2 + fresh hash-verified gemma escalation calls),
  `analyze` (metrics, disagreement, oracle, invisible-error list), `concurrency`
  (small c=1 vs c=2 probe, fresh calls).
- `routing_manifest.json`, `r0_qwen_only_{primary,secondary}.json`,
  `r1_observable_failure_{...}.json`, `r2_strict_observable_{...}.json`,
  `routed_{primary,secondary}.json`, `escalations.json`,
  `invisible_errors_{primary,secondary}.json`, `disagreement.json`,
  `latency.json`, `resource_usage.json`, `concurrency_test.json`,
  `oracle_upper_bound.json`, `comparison_4c.json`.

## Headline (details in docs/STAGE_4C_ROUTING_VALIDATION.md)
R0 11/16 + 20/33 → R1 11/16 (+73s, 1 esc) + 21/33 (+26s, 1 esc); R2 == R1
(heuristics fired zero times). 16/49 scored errors invisible to any observable
signal. c=2 stable, all-ok, ~1.5× wall on warmed runs (small n — confirm in 4D).
