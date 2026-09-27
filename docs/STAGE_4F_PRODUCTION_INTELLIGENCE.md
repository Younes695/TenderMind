# Stage 4F — Production Intelligence Layer

Flag-gated (`TENDERMIND_TWO_STAGE_LLM=1`) intelligence flow over the hardened
pipeline; flag off = byte-identical legacy path. Production default stays
qwen2.5:3b; auto-escalation stays OFF; no new models.

## Flow (separate stages, never one call)
Inventory → extraction → structured tables → discovery → compression →
STRUCTURED-FIRST → bounded AI (qwen minimal-1) → validation/provenance →
commercial/schedule → gaps → ambiguity → reconciliation MVP → risk →
synthesis MVP → canonical analysis (new sections merge into `derived_features`
additively; no migration, no contract break).

## Capabilities operational in 4F
Lane A (runner + structured-first), Lane B deterministic (BOQ normalizer,
currency/payment/security/validity, explicit + relative dates with explicit
anchors), Lane C deterministic (GapSummary counts, ambiguity types), Lane D
MVP (duplicate groups, explicit amendment links, BOQ conflicts, lifecycle
ORIGINAL/AMENDED/CLARIFICATION/SUPERSESSION_UNKNOWN), Lane E MVP
(deterministic synthesis; AI synthesis NOT_CONFIGURED). Risk: grounded signals
only, severity never assigned. UI: additive intelligence section, fallbacks.

## Measured (Mobile 12-parent sample, real qwen)
Baseline 38 calls/202.4s/38 finals → optimized 26 calls/140.9s/26 finals:
**31.6% fewer AI calls, −61.5s**, 26/26 retained summaries identical (zero
semantic loss), 12 equipment candidates covered as structured facts. c1/c2
(n=38, warmed): 202.9s → 134.9s (**1.50×**), 0 failures, p95 6.18→8.11s.
