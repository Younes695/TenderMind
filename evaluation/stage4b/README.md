# Stage 4B — Controlled Model Shootout (evaluation-only)

Benchmarks qwen2.5:3b / qwen3:4b / gemma3:12b / phi4-mini through the SAME
hardened two-stage task: identical candidates, order, text, minimal-1 contract,
parser, temperature 0, timeout 90s. Gemini 3.8 Flash = NOT_RUN (no credentials).

## Files
- `providers.py` — one ModelProvider per model (shared transport/parser; qwen3
  think:false recorded as comparability control; Gemini adapter reports
  provider_not_configured without secrets).
- `run_4b.py` — `probe <model>`, `run <model> [primary|secondary|both]`
  (incremental + resumable), `analyze` (scores, confusion, agreement, router sim).
- `*_primary_raw.jsonl` / `*_secondary_raw.jsonl` — per-candidate records
  (prediction, summary, status, latency, raw, fixture_sha).
- `{qwen25,qwen3,gemma,phi}_results.json`, `gemini_results.json` (NOT_RUN),
  `comparison_4b.json`, `per_candidate_comparison{,_primary,_secondary}.json`,
  `confusion_matrices.json`, `latency_comparison.json`, `resource_comparison.json`,
  `model_agreement{,_primary,_secondary}.json`, `router_simulation.json`,
  `language_robustness.json`, `benchmark_manifest.json`, `model_registry_snapshot.json`.

## Datasets
- primary: exact 16 Stage 3I candidates (balanced golds, 11 categories).
- secondary: exact 41 Stage 3K-A candidates (TECHNICAL-heavy + 2 MULTI excluded
  from accuracy; 6 Arabic-source rows scored ONLY in language_robustness.json).
- 150-candidate B sample: NOT rerun (per-candidate source_text not persisted;
  re-derivation cannot re-link run-local IDs — documented, not faked).

## Production safety
No production file is modified by this stage; providers live here, not in
app/pipeline. Production default stays qwen2.5:3b. No keys stored.
