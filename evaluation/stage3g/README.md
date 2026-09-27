# Stage 3G — Model Capability Test (evaluation-only)

Isolates MODEL CAPABILITY from the TenderMind extraction pipeline via pure
single-label classification on short, high-signal fixture snippets.

- `snippets_3g.json` — 12 snippets, verbatim substrings of
  `evaluation/fixtures/mobile_llm_representative.json`, one dominant category each.
- `classification_tasks.py` — Task A/B prompts, allowed labels, normalization,
  single-call helper. No production Variant B/C/D mutation.
- `run_3g_capability.py` — runs Task A then Task B in fixed snippet order on
  `qwen2.5:3b` via existing endpoint/settings (temperature 0, timeout 90).
- `task_a_3g.json` / `task_b_3g.json` — per-snippet raw outputs + latencies.
- `capability_summary_3g.json` — accuracy, per-category, confusion, collapse, latency.

Reproduce: `python evaluation/stage3g/run_3g_capability.py` (requires Ollama
`qwen2.5:3b` on `http://localhost:11434`).
