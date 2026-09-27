"""Stage 4A — production pipeline package (additive, evaluation untouched).

Layout:
    contracts.py            domain dataclasses (RAW != CANDIDATE != LLM_OUT != CANONICAL != EVIDENCE)
    candidate_discovery.py  deterministic discovery service (no LLM)
    candidate_compression.py exact/normalized/near-duplicate compression (no LLM)
    ai_router.py            AITask -> Router -> ModelProvider (qwen2.5:3b only for now)
    postprocessing.py       deterministic validation + canonical IDs + evidence
    provenance.py           single reusable provenance-integrity validator
    format_extraction.py    format classification matrix (policy, no behavior change)
    structured_data.py      StructuredDataAdapter boundary + generic XLSX adapter
    reconciliation.py       future cross-document contract (NOT_CONFIGURED)
    risk.py                 gap/ambiguity/risk/synthesis boundaries (deterministic gaps only)
    capabilities.py         machine-readable AI capability registry
    jobs.py                 stage model, telemetry, pipeline versioning, terminal states
    config.py               centralized env configuration (no hardcoded machine paths)
    two_stage_runner.py     flag-gated production two-stage runner
"""
