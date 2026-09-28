"""Stage 4A — processing-job architecture: stages, telemetry, versioning.

New stage model (truthful counts, no fake percentages):
  QUEUED -> INGESTING -> EXTRACTING -> BUILDING_CANDIDATES -> COMPRESSING_CANDIDATES
  -> AI_ANALYSIS -> VALIDATING -> FINALIZING -> COMPLETED / PARTIAL / FAILED

Terminal-state rule (mirrors the existing honest semantics in
app/processing.py): all-ok -> COMPLETED; some failures -> PARTIAL with the
failures listed; nothing usable -> FAILED; unsupported-only -> PARTIAL.

Pipeline version metadata is stamped on every analysis; previous analysis
identity is never overwritten (new ANALYSIS-<id> row per job).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List

PIPELINE_VERSION_2STAGE = "2-stage-1.0"
PIPELINE_VERSION_LEGACY = "1.0"
NORMALIZER_CONTRACT_VERSION = "minimal-1"
CANDIDATE_DISCOVERY_VERSION = "discovery-1"
COMPRESSION_VERSION = "compress-1"


class PipelineStage(str, Enum):
    QUEUED = "QUEUED"
    INGESTING = "INGESTING"
    EXTRACTING = "EXTRACTING"
    BUILDING_CANDIDATES = "BUILDING_CANDIDATES"
    COMPRESSING_CANDIDATES = "COMPRESSING_CANDIDATES"
    AI_ANALYSIS = "AI_ANALYSIS"
    VALIDATING = "VALIDATING"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


# Legacy stage names still emitted by the flag-off path (unchanged behavior).
LEGACY_STAGES = ["INVENTORY", "EXTRACTION", "CLASSIFICATION", "DETERMINISTIC",
                 "SEMANTIC", "VALIDATION", "PERSISTENCE", "COMPLETED"]


def resolve_terminal_status(documents_total: int, documents_processed: int,
                            documents_failed: int, documents_unsupported: int,
                            requirements_final: int = 0) -> str:
    """Honest terminal status from real counts. Never invents COMPLETED."""
    if documents_total == 0:
        return PipelineStage.COMPLETED.value if requirements_final >= 0 else PipelineStage.FAILED.value
    if documents_failed == 0 and documents_unsupported == 0:
        return PipelineStage.COMPLETED.value
    if documents_processed > 0 or documents_unsupported > 0:
        return PipelineStage.PARTIAL.value
    return PipelineStage.FAILED.value


def resolve_coverage(documents_total: int, documents_processed: int,
                     documents_failed: int, documents_unsupported: int) -> dict:
    """Additive coverage representation (Stage 4H). NEVER changes the terminal
    status derivation above; it only makes the distinction explicit:

    - processing_status: what the job did (existing COMPLETED/PARTIAL/FAILED)
    - analysis_coverage: COMPLETE only when zero failed AND zero unsupported;
      PARTIAL otherwise (some material honestly unanalyzed)
    - document_status_counts: truthful per-state counts
    """
    total = int(documents_total or 0)
    failed = int(documents_failed or 0)
    unsupported = int(documents_unsupported or 0)
    processed = int(documents_processed or 0)
    coverage = "COMPLETE" if (failed == 0 and unsupported == 0) else "PARTIAL"
    return {"analysis_coverage": coverage,
            "document_status_counts": {"complete": processed, "failed": failed,
                                       "unsupported": unsupported, "total": total}}


@dataclass
class JobTelemetry:
    """Structured telemetry at stage boundaries. No raw tender content logged."""

    job_id: str = ""
    tender_id: str = ""
    pipeline_version: str = PIPELINE_VERSION_2STAGE
    model_name: str = ""
    normalizer_contract_version: str = NORMALIZER_CONTRACT_VERSION
    candidate_discovery_version: str = CANDIDATE_DISCOVERY_VERSION
    # counts
    documents_total: int = 0
    documents_processed: int = 0
    documents_failed: int = 0
    documents_unsupported: int = 0
    candidates_generated: int = 0
    candidates_rejected: int = 0
    candidates_compressed: int = 0
    candidates_sent_to_ai: int = 0
    model_call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    requirements_final: int = 0
    evidence_final: int = 0
    # latency
    avg_latency_s: float = 0.0
    p95_latency_s: float = 0.0
    total_wall_s: float = 0.0
    compression_pct: float = 0.0
    stage_results: List[Dict[str, Any]] = field(default_factory=list)
    # Stage 4E additive telemetry (optional; defaults preserve 4A behavior)
    lane: str = ""
    capability_tier: str = ""
    max_workers: int = 1
    structured_tables: int = 0
    structured_line_items: int = 0
    # Stage 4F additive telemetry (optional; defaults preserve prior behavior)
    candidates_structured_covered: int = 0
    gaps_final: int = 0
    ambiguities_final: int = 0
    conflicts_final: int = 0
    risk_signals_final: int = 0
    synthesis_status: str = ""
    # Stage 5H: normalizations reused from an interrupted run's checkpoint
    ai_cache_hits: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _prompt_version() -> str:
    from app.pipeline.ai_router import active_prompt_version
    return active_prompt_version()


def pipeline_version_metadata(model_name: str = "") -> Dict[str, str]:
    return {
        "pipeline_version": PIPELINE_VERSION_2STAGE,
        "model": model_name,
        "normalizer_contract_version": NORMALIZER_CONTRACT_VERSION,
        "prompt_version": _prompt_version(),
        "candidate_discovery_version": CANDIDATE_DISCOVERY_VERSION,
        "compression_version": COMPRESSION_VERSION,
    }
