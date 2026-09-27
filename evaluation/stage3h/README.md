# Stage 3H — Pre-Segmented Single-Requirement Extraction Test (evaluation-only)

Isolates requirement discovery/segmentation from semantic normalization:
each model call receives ONE pre-segmented requirement snippet.

- `snippets_3h.json` — 12 snippets, one requirement each, verbatim substrings of
  `evaluation/fixtures/mobile_llm_representative.json`, fixed order for A/B/C.
- `single_req_tasks.py` — Test A (minimal normalization) and Test B (+ concise
  definitions) prompts, shared helpers. Test C reuses the unchanged production
  Variant B path (`call_ollama_for_chunk` default). No production mutation.
- `run_3h.py` — runs A, then B, then C in fixed snippet order on `qwen2.5:3b`
  (temperature 0, timeout 90).
- `task_a_3h.json` / `task_b_3h.json` / `task_c_3h.json` — per-snippet raw
  outputs, parsed requirements, evidence (C only), status, latency.
- `comparison_3h.json` — accuracy, per-category, collapse counts, latencies,
  confusion matrices.

Reproduce: `python evaluation/stage3h/run_3h.py` (requires Ollama
`qwen2.5:3b` on `http://localhost:11434`).
