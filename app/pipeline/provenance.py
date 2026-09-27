"""Stage 4A — provenance as a first-class invariant.

Single reusable validator for provenance integrity. Every final requirement
must trace to: original document, original page, original source text,
candidate (and parent chunk where available). Every evidence object must
resolve back to the same source. No cross-document drift, no cross-page
drift, no model-generated source identity.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.pipeline.contracts import EvidenceLink, RequirementCandidate, ValidatedRequirement


def validate_provenance(
    requirements: List[ValidatedRequirement],
    evidence: List[EvidenceLink],
    candidates_by_id: Dict[str, RequirementCandidate],
    require_canonical_ids: bool = True,
) -> List[Dict[str, Any]]:
    """Return a list of violations (empty == integrity holds). Checks:

    R1 requirement fields match its candidate (document, page, source_text).
    R2 candidate carries a parent chunk reference where the pipeline provides one.
    R3 evidence links an existing requirement of the same candidate.
    R4 evidence source (document, page) equals the requirement's.
    R5 evidence fact equals the requirement summary.
    R6 final requirement IDs are canonical (REQ-XXX), never candidate/model IDs.
    """
    violations: List[Dict[str, Any]] = []
    req_by_id = {r.requirement_id: r for r in requirements}

    for r in requirements:
        ctx = {"requirement_id": r.requirement_id, "candidate_id": r.candidate_id}
        cand = candidates_by_id.get(r.candidate_id)
        if cand is None:
            violations.append({**ctx, "check": "R1", "reason": "unknown_candidate"})
            continue
        if r.source_document != cand.source_document:
            violations.append({**ctx, "check": "R1", "reason": "cross_document_drift"})
        if r.page_number != cand.page:
            violations.append({**ctx, "check": "R1", "reason": "cross_page_drift"})
        if r.source_text != cand.source_text:
            violations.append({**ctx, "check": "R1", "reason": "source_text_mismatch"})
        if not cand.parent_chunk_id:
            violations.append({**ctx, "check": "R2", "reason": "missing_parent_chunk"})
        if require_canonical_ids and (
                r.requirement_id == r.candidate_id or not r.requirement_id.startswith("REQ-")):
            violations.append({**ctx, "check": "R6", "reason": "non_canonical_id"})

    for e in evidence:
        ctx = {"evidence_id": e.evidence_id, "requirement_id": e.requirement_id}
        req = req_by_id.get(e.requirement_id)
        if req is None:
            violations.append({**ctx, "check": "R3", "reason": "orphan_evidence"})
            continue
        if e.candidate_id != req.candidate_id:
            violations.append({**ctx, "check": "R3", "reason": "candidate_mismatch"})
        if e.source_document != req.source_document:
            violations.append({**ctx, "check": "R4", "reason": "cross_document_drift"})
        if e.page_number != req.page_number:
            violations.append({**ctx, "check": "R4", "reason": "cross_page_drift"})
        if e.fact != req.summary:
            violations.append({**ctx, "check": "R5", "reason": "fact_summary_mismatch"})

    return violations
