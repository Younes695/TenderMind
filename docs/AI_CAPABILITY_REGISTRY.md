# TenderMind — AI Capability Registry (Stage 4A)

Machine-readable source: `app/pipeline/capabilities.py::AI_CAPABILITY_REGISTRY`.
This document is the human mirror; the dict is authoritative for code.

## Routing model

`AITask -> Router.route() -> ModelProvider | NOT_CONFIGURED`.
`ModelProvider` interface: `model_name`, `capabilities()`,
`normalize_requirement(candidate)`, `health_check()`, `metrics()`.
`Router` adds `register()`, `selection_metadata()` (task/model/provider/contract/
fallback), and `fallback_policy` (today: explicit failure, no silent fallback).
Future models (Stage 4B: Qwen3, Gemma, Phi, Gemini/API, HF) implement
`ModelProvider` and register per task — no pipeline rewrites.

## Registry

| Task | Input | Output | Model | Fallback | Enabled | Timeout | Retry | Confidence |
|---|---|---|---|---|---|---|---|---|
| REQUIREMENT_NORMALIZATION | RequirementCandidate | LLMNormalizationResult | qwen2.5:3b | none-configured | YES | 90s | 0 | none |
| CLAUSE_INTERPRETATION | RequirementCandidate | TBD | unassigned | none-configured | NO | 90s | 0 | none |
| AMBIGUITY_ANALYSIS | ValidatedRequirement[] | TBD | unassigned | none-configured | NO | 90s | 0 | none |
| RECONCILIATION | ReconciliationInput | ReconciliationResult | unassigned | none-configured | NO | 120s | 0 | none |
| SYNTHESIS | ValidatedRequirement[] | TBD | unassigned | none-configured | NO | 120s | 0 | none |

Notes:
- Confidence is `none` everywhere: qwen2.5:3b returns no calibrated confidence;
  none is invented. Stored requirement `confidence: 0.7` is a fixed pipeline
  constant (as in Stages 3D–3K), not a model claim.
- REQUIREMENT_NORMALIZATION uses the validated minimal contract (`minimal-1`):
  exactly one `{summary, category, mandatory, applicable_entity}` object;
  UNKNOWN preserved as quarantine; contract violations rejected with status.
- Disabled tasks return `NOT_CONFIGURED` (falsy sentinel) from both
  `Router.route()` and the boundary modules (`reconciliation.py`, `risk.py`).
  Support is never faked; the UI must render NOT_CONFIGURED states without
  fake values (already handles missing sections as "Not available").

## Future model-routing path (Stage 4B)

1. Implement `ModelProvider` for the candidate model (transport + contract mapping).
2. Register it for `REQUIREMENT_NORMALIZATION` (challenger) or a new task.
3. Benchmark through `two_stage_runner` with a stub-able transport — same
   candidates, same compression, same validator, comparable telemetry.
No changes to discovery/compression/post-processing/provenance required.
