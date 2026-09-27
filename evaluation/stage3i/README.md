# Stage 3I — Pre-Segmented Single-Purpose Variant B Test (evaluation-only)

Tests whether Variant B's TECHNICAL collapse decreases when segmentation is
solved deterministically before the LLM call. Variant B is unchanged.

- `parent_chunks_3i.json` — 12 parent chunks, verbatim from
  `evaluation/fixtures/mobile_llm_representative.json` (multi-category ones
  prioritized: chunk-0000/0001/0002/0004/0005/0007/0008/0010/0011/0012 + 0003/0009).
- `presegment.py` + `segmentation_rules.md` — deterministic splitter reusing
  production `GENERIC_PATTERNS`; see rules doc for gate and known gaps.
- `generated_candidates.json` — 16 accepted single-purpose candidates with
  verbatim text, spans, signal categories, and obvious-purpose gold.
- `rejected_candidates.json` — 21 rejected spans with reasons.
- `run_3i.py` — runs Test A (minimal normalization), Test B (+ definitions),
  Test C (unchanged Variant B) on the same 16 candidates in fixed order.
- `task_a_3i.json` / `task_b_3i.json` / `variant_b_outputs_3i.json` — raw outputs.
- `comparison_3i.json` / `confusion_matrix_3i.json` / `latency_3i.json`.

Reproduce: `python evaluation/stage3i/build_candidates.py` then
`python evaluation/stage3i/run_3i.py` (requires Ollama `qwen2.5:3b`).
