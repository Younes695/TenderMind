# Stage 3J — Minimal Output-Contract A/B Test (evaluation-only)

Tests whether simplifying Variant B's output contract restores category
diversity on the exact 16 Stage 3I candidates, without changing semantics.

- `minimal_contract_prompt.py` — evaluation-only prompt: Variant B's semantic
  intent (role, grounding, allowed categories, PRIMARY PURPOSE definitions,
  UNKNOWN rule) with the output contract reduced to a single
  `{summary, category, mandatory, applicable_entity}` object. No IDs, evidence,
  provenance, or linkage requested. `attach_provenance` / `derive_evidence`
  are deterministic (fixture-driven, never model-generated).
- `run_3j.py` — runs the minimal contract on the exact 16 Stage 3I candidates
  in fixed order (`qwen2.5:3b`, temperature 0, timeout 90).
- `task_c_3j.json` — per-candidate raw outputs, parsed requirements,
  deterministically attached provenance/evidence, status, latency.
- `comparison_3j.json` / `confusion_matrix_3j.json` / `latency_3j.json`.

Reproduce: `python evaluation/stage3j/run_3j.py` (requires Ollama
`qwen2.5:3b`). Baseline is the stored Stage 3I artifact
(`evaluation/stage3i/variant_b_outputs_3i.json`: 9/16, collapse 4/16),
verified from disk rather than hardcoded.
