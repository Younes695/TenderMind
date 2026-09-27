# Throughput & AI-Call Budget (Stage 4F)

## Method
Mobile 12-parent sample (38 candidates), real qwen2.5:3b, warmed model.
Baseline = intelligence runner without structured tables; optimized = with
Mobile BOQ table (128 line items). Same discovery/compression/LLM/validation.

## Results (`evaluation/stage4f/throughput_*.json`, `candidate_reduction.json`)
| | Baseline | Optimized |
|---|---|---|
| Candidates → AI | 38 | 26 |
| AI calls (all ok) | 38 | 26 (−31.6%) |
| Finals | 38 | 26 (26/26 summaries identical) |
| Structured-covered | 0 | 12 (equipment rows → BOQ facts) |
| Wall | 202.4s | 140.9s (−61.5s) |
| Avg / p95 | 5.32 / 6.18s | 5.41 / 6.22s |
| Conflicts found | 0 | 3 (BOQ same-code differing qty) |

## Concurrency (`concurrency_results.json`, n=38 warmed)
c1 202.9s → c2 134.9s (1.50×), 0 failures, VRAM 2335/4096 both arms, qwen
resident throughout. Consistent with 4D (1.64×, n=32). MAX_AI_WORKERS=2 stays.

## Budget rule
Every AI call must survive structured-first to run; every reduction retains
source IDs/document/page/text/merged_from/reason. No SLA extrapolated beyond
measured samples (full-tender projections live in 4E workload model).
