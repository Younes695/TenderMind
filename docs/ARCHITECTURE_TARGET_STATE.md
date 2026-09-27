# TenderMind — Target Architecture State (Stage 4A)

This is the target. Stage 4A implements the **boxed** items; the rest are explicit interfaces
with `NOT_CONFIGURED` backends so Stage 4B (model benchmark) plugs in without rewrites.

```
UI ──► Tender API ──► Durable processing job ──► ingestion / inventory
 ──► Format-specific extraction ──► Normalized source artifacts
 ──► [4A] Deterministic candidate discovery ──► [4A] Candidate compression
 ──► [4A] AI Router ──► LLM normalization (minimal contract, qwen2.5:3b only)
 ──► [4A] Deterministic validation ──► [4A] Provenance / evidence / IDs
 ──► [interface only] Cross-document reconciliation
 ──► Deadlines / commercial / gaps / ambiguities / risk signals (existing deterministic kept)
 ──► Management decision-support (existing engine untouched, still separate from pipeline)
 ──► Persisted canonical analysis (+ pipeline_version "2-stage-1.0") ──► UI
```

## Stage boundaries (truthful, no fake %)

`QUEUED → INGESTING → EXTRACTING → BUILDING_CANDIDATES → COMPRESSING_CANDIDATES → AI_ANALYSIS →
VALIDATING → FINALIZING → COMPLETED / PARTIAL / FAILED`

Each stage exposes real counts: documents_total/processed/failed/unsupported,
candidates_generated/rejected, candidates_sent_to_ai, ai_calls/ai_failures/timeouts,
requirements_final/evidence_final, latencies (avg/p95). Terminal states: COMPLETED (all ok),
PARTIAL (some doc/candidate/AI failures, explicitly listed), FAILED (nothing usable).

## Concept separations (non-negotiable)

`RAW SOURCE ≠ CANDIDATE ≠ LLM OUTPUT ≠ CANONICAL REQUIREMENT ≠ EVIDENCE`

Enforced by dataclasses in `app/pipeline/contracts.py`: `DocumentArtifact`, `SourceText`,
`StructuredTable` (+`FormRecord`, `CommercialLineItem`, `ProjectExperienceRecord`),
`RequirementCandidate`, `LLMNormalizationResult`, `ValidatedRequirement`, `EvidenceLink`,
`ProcessingStageResult`, `TenderAnalysisResult`. The LLM type carries **only**
`{summary, category, mandatory, applicable_entity}` — no IDs, no provenance, ever.

## [4A] Modules (additive under `app/pipeline/`, eval untouched)

| Module | Role |
|---|---|
| `contracts.py` | Types above + `PipelineStage` enum + `FailureCode` + `NOT_CONFIGURED` sentinel |
| `candidate_discovery.py` | Deterministic discovery service: source_document/page/source_text/parent-chunk ref/signal categories/candidate ID/span/quality flags. **No LLM calls. Reproducible** (sorted input order). |
| `candidate_compression.py` | exact → normalized → near-duplicate removal, safe merge (same-document default), priority/filtering, full metrics + reduction %. Deterministic, no LLM. |
| `ai_router.py` | `AITask` enum, `ModelProvider` ABC (`model_name/capabilities/normalize_requirement/health_check/metrics`), `Router.route()` + fallback policy + selection metadata. Only `REQUIREMENT_NORMALIZATION → qwen2.5:3b` wired; rest `NOT_CONFIGURED`. No fakes. |
| `postprocessing.py` | schema → category → grounding checks → canonical IDs → source attach → evidence gen. Explicit failures; never fabricates. |
| `provenance.py` | Single `validate_provenance()` for requirement↔evidence↔candidate↔source integrity. |
| `format_extraction.py` | Format classification matrix (PDF/DOC/DOCX/XLS/XLSX/TXT/CSV/LOG/images/archives/unsupported) + policy (never force OCR on text PDFs). |
| `structured_data.py` | `StructuredDataAdapter` ABC + generic XLSX adapter (safe subset of current openpyxl usage). Ganna's domain outputs = reference only, never copied. |
| `reconciliation.py` / `risk.py` | Future contracts only (`NOT_CONFIGURED`); deterministic existing outputs (deadlines/commercial/gaps) stay connected. No invented severity/impact, no auto BID/NO-BID. |
| `capabilities.py` | Machine-readable AI capability registry (task/input/output/model/fallback/enabled/timeout/retry/confidence or explicit `confidence: none`). |
| `jobs.py` | Stage enum, telemetry builder, `PIPELINE_VERSION="2-stage-1.0"` + model/contract/discovery versions. |
| `config.py` | Centralized env config (`DATABASE_URL`, `TENDERMIND_STORAGE_ROOT`, `OLLAMA_*`, `LLM_TIMEOUT`, `TENDERMIND_TWO_STAGE_LLM`). No hardcoded machine paths. |
| `two_stage_runner.py` | Flag-gated production runner reusing the validated minimal contract through the Router. Flag OFF = byte-identical legacy path. |

## Explicitly NOT in 4A (deferred, interfaces ready)

- New models (Qwen3/Gemma/Phi/Gemini/HF) — Stage 4B benchmarks against `ModelProvider`.
- AI reconciliation / ambiguity / risk / synthesis backends — contracts only.
- Redis/Celery — in-process BackgroundTasks retained; job states + incremental counts already
  make future workers possible; interfaces are worker-safe (candidate lists are values).
- Concurrency for AI calls — interfaces allow it; no threads introduced (GPU-contention risk,
  unmeasured).
- Fixing out-of-scope API bugs (evidence-by-tender filtering, recompute idempotency, Float
  counters) — recorded in current-state doc, untouched.

## Acceptance mapping

§27 items 1–18 map to: untouched legacy path + flag (1,3,4,5,6,14), frontend suite + build
(2), `scripts/check_no_hardcoded_paths`-style grep + config.py (7), discovery determinism test
(8), compression provenance tests (9), router abstraction (10,15), minimal-contract provider +
3C rules (11), postprocessing + provenance tests (12), per-document PARTIAL semantics + tests
(13), structured adapter + docs (16), risk/reconciliation NOT_CONFIGURED + untouched engine (17,18).
