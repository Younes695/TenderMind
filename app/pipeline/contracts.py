"""Stage 4A — core domain pipeline contracts.

Principle: RAW SOURCE != CANDIDATE != LLM OUTPUT != CANONICAL REQUIREMENT != EVIDENCE.
Each stage has explicit input/output boundaries; these dataclasses are the boundaries.
Implementation-neutral (plain dataclasses, JSON-serializable via asdict()).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class NotConfigured:
    """Sentinel for capabilities with no backend yet. Never fake support."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "NOT_CONFIGURED"

    def __bool__(self) -> bool:
        return False


NOT_CONFIGURED = NotConfigured()


class FailureCode(str, Enum):
    """Explicit failure taxonomy. No silent recovery anywhere in the pipeline."""

    OK = "ok"
    # discovery / compression
    SKIPPED_TINY_INPUT = "SKIPPED_TINY_INPUT"
    REJECTED_NO_SIGNAL = "no_signal"
    REJECTED_MIXED_MULTI = "mixed_multi_category"
    REJECTED_OCR_GARBAGE = "ocr_garbage"
    REJECTED_TINY = "tiny"
    REJECTED_EMPTY = "empty"
    MERGED_DUPLICATE = "merged_duplicate"
    FILTERED_LOW_PRIORITY = "filtered_low_priority"
    # LLM transport / contract
    LLM_TIMEOUT = "timeout"
    LLM_HTTP_ERROR = "http_error"
    LLM_TRANSPORT_ERROR = "transport_error"
    LLM_EMPTY = "empty"
    LLM_MALFORMED = "malformed"
    LLM_WRONG_SHAPE = "wrong_shape"
    LLM_MULTI = "multi"
    LLM_BAD_CATEGORY = "bad_category"
    # deterministic validation
    VALIDATION_GROUNDING_FAILED = "grounding_failed"
    VALIDATION_PROVENANCE_DRIFT = "provenance_drift"
    # document level
    DOC_FAILED = "FAILED"
    DOC_PARTIAL = "PARTIAL"
    DOC_COMPLETE = "COMPLETE"
    DOC_UNSUPPORTED = "UNSUPPORTED"


# ---------------------------------------------------------------------------
# Stage 0/1: source artifacts
# ---------------------------------------------------------------------------

@dataclass
class DocumentArtifact:
    """A stored source document with its extraction outcome."""

    filename: str
    full_path: str
    extension: str
    size_bytes: int = 0
    status: str = FailureCode.DOC_COMPLETE.value  # COMPLETE|PARTIAL|FAILED|UNSUPPORTED
    page_count: int = 0
    total_text_chars: int = 0
    extraction_method: str = ""
    error: Optional[str] = None
    missing: bool = False
    failed_pages: List[int] = field(default_factory=list)  # pages that could not be read


@dataclass
class SourceText:
    """Normalized text of one page (or sheet) of a DocumentArtifact."""

    source_document: str
    page_number: int
    text: str
    method: str = ""
    ocr_applied: bool = False


@dataclass
class StructuredTable:
    """Normalized rows from a structured source (e.g. XLSX sheet)."""

    source_document: str
    sheet: str
    columns: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)
    row_count: int = 0


@dataclass
class FormRecord:
    """A key/value form-like record (adapter boundary; generic only)."""

    source_document: str
    location: str  # sheet name / page ref
    fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommercialLineItem:
    """Price-schedule style line item (adapter boundary)."""

    source_document: str
    location: str
    item: Optional[str] = None
    description: Optional[str] = None
    description_ar: Optional[str] = None  # Arabic-script segment when bilingual
    unit: Optional[str] = None
    quantity: Optional[str] = None
    unit_price: Optional[str] = None
    total_price: Optional[str] = None


@dataclass
class ProjectExperienceRecord:
    """Project-history style record (adapter boundary; generic FORM-D slots)."""

    source_document: str
    location: str
    project: Optional[str] = None
    client: Optional[str] = None
    employer: Optional[str] = None
    country: Optional[str] = None
    location_detail: Optional[str] = None
    scope: Optional[str] = None
    award_date: Optional[str] = None
    completion_date: Optional[str] = None
    delivery_date: Optional[str] = None
    total_value: Optional[str] = None
    contact: Optional[str] = None
    year: Optional[str] = None
    description: Optional[str] = None


@dataclass
class EquipmentRecord:
    """Equipment form record (generic; e.g. FORM-D style slots)."""

    source_document: str
    location: str  # sheet + row/cell range where feasible
    form_id: Optional[str] = None
    equipment_type: Optional[str] = None
    component: Optional[str] = None
    subcontracted: Optional[bool] = None
    subcontractor_name: Optional[str] = None
    origin_country: Optional[str] = None
    voltage: Optional[str] = None
    quantity: Optional[str] = None
    test_status: Optional[str] = None  # e.g. type tests YES/NO (recorded, never judged)
    delivery_date: Optional[str] = None
    commissioning_date: Optional[str] = None
    project_reference: Optional[str] = None


@dataclass
class ScheduleRecord:
    """Delivery/completion schedule fact (deterministic or lane-B AI)."""

    source_document: str
    location: str
    kind: Optional[str] = None  # delivery | completion | validity | submission
    value: Optional[str] = None
    normalized_date: Optional[str] = None


@dataclass
class ClarificationRecord:
    """Bidder-question / owner-response pair (reference inputs for future
    reconciliation; never plain-text-only)."""

    source_document: str
    location: str  # page or sheet + row
    reference: Optional[str] = None
    question: Optional[str] = None
    response: Optional[str] = None


@dataclass
class AddendumRecord:
    """Amendment pointer (feeds future supersession logic)."""

    source_document: str
    location: str
    amendment: Optional[str] = None
    affected_item: Optional[str] = None
    affected_section: Optional[str] = None


# ---------------------------------------------------------------------------
# Stage 2: candidate discovery (deterministic, no LLM)
# ---------------------------------------------------------------------------

@dataclass
class RequirementCandidate:
    """One deterministic candidate. Carries provenance, never conclusions."""

    candidate_id: str  # native chunk-XXXX-seg-YY scheme
    parent_chunk_id: str
    source_document: str
    page: int
    source_text: str
    span: List[int] = field(default_factory=list)  # [start, end] in parent text
    deterministic_signal_categories: List[str] = field(default_factory=list)
    quality_flags: List[str] = field(default_factory=list)
    merged_from: List[str] = field(default_factory=list)  # populated by compression


# ---------------------------------------------------------------------------
# Stage 3: LLM output (minimal contract ONLY — no IDs, no provenance, ever)
# ---------------------------------------------------------------------------

@dataclass
class LLMNormalizationResult:
    """Exactly what the model may return. Nothing else is accepted."""

    summary: str
    category: str
    mandatory: Optional[bool] = None
    applicable_entity: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Stage 4: canonical requirement + evidence (deterministic)
# ---------------------------------------------------------------------------

@dataclass
class ValidatedRequirement:
    """Canonical requirement: LLM semantics + deterministic provenance/identity."""

    requirement_id: str  # REQ-XXX canonical
    candidate_id: str
    parent_chunk_id: Optional[str]
    summary: str
    category: str
    mandatory: Optional[bool]
    applicable_entity: Optional[str]
    source_document: str
    page_number: int
    source_text: str
    provenance: Dict[str, Any] = field(default_factory=dict)
    extraction_method: str = "two-stage"
    confidence: Optional[float] = None


@dataclass
class EvidenceLink:
    """Deterministic 1-to-1 evidence. fact == requirement summary by construction."""

    evidence_id: str
    requirement_id: str
    candidate_id: str
    fact: str
    source_document: str
    page_number: int
    provenance: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    applicable_entity: Optional[str] = None
    valid_until: Optional[str] = None
    reusable: bool = False


# ---------------------------------------------------------------------------
# Stage 5: results / telemetry containers
# ---------------------------------------------------------------------------

@dataclass
class ProcessingStageResult:
    """Truthful per-stage outcome: real counts, never fake percentages."""

    stage: str
    status: str  # COMPLETED | PARTIAL | FAILED
    counts: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    latency_s: float = 0.0


@dataclass
class TenderAnalysisResult:
    """Canonical analysis payload (superset-compatible with the UI contract)."""

    tender_id: str
    status: str  # COMPLETED | PARTIAL | FAILED
    documents: List[Dict[str, Any]] = field(default_factory=list)
    requirements: List[ValidatedRequirement] = field(default_factory=list)
    evidence: List[EvidenceLink] = field(default_factory=list)
    deadlines: List[Dict[str, Any]] = field(default_factory=list)
    commercial: Optional[Dict[str, Any]] = None
    risks: List[Dict[str, Any]] = field(default_factory=list)
    derived_features: Dict[str, Any] = field(default_factory=dict)
    processing: Dict[str, Any] = field(default_factory=dict)
    stage_results: List[ProcessingStageResult] = field(default_factory=list)
    document_failures: List[Dict[str, str]] = field(default_factory=list)
    candidate_failures: List[Dict[str, str]] = field(default_factory=list)
