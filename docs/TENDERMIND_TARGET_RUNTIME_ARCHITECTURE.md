# TenderMind — Target Runtime Architecture (Stage 4E)

```
UI upload → inventory → format-specific extraction → structured extraction
(where applicable) → discovery → compression → capability routing (lanes A–E)
→ fast semantic normalization → deterministic validation/provenance
→ commercial/schedule analysis → gap/ambiguity analysis → cross-document
reconciliation → risk signals → management synthesis → canonical analysis → UI
```

Extraction, interpretation, and synthesis are separate stages — never one AI
call. Lane contracts: `docs/AI_CAPABILITY_LANES.md`. Model tiers abstract with
env-configured names; one model serves many lanes.

## Performance model (`evaluation/stage4e/workload_model.json`)
wall ≈ Σlatencies/workers + overhead, anchored ONLY on measured figures:
ingestion ~56–64s (941pp), discovery seg 1.9s / 2545 candidates, qwen 5.2s avg
(p95 6.3), c2 factor 1.64, escalation rates 4–14%, gemma 26–73s warm (~90s
cold). Projections: per-100 qwen ~10min c1; full-Mobile qwen ~4h c1 / ~2.5h c2;
gemma full-tender ~23h single-worker (escalation-only role — not recommended).
No figures for untested models. No SLAs.

## Parallelization (`concurrency_config.json`, `WorkerConfig`)
MAX_AI_WORKERS default 2, range 1–8, production default OFF (batch opt-in).
Bounded queue (4×workers, explicit shed → PARTIAL). Risks documented: GPU
contention (avg scales with c), single-model residency (reload ~86–92s gemma;
batch per-model, no interleave), memory pressure. No global pool yet; durable
queue out of scope.

## Decision support
Requirements + evidence + deadlines + commercial + gaps + ambiguities +
cross-doc issues + grounded risk signals (no severity) + cited summary.
Auto BID/NO-BID banned; severity/impact/probabilities never invented
(tested absent).
