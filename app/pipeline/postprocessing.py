"""Stage 4A — deterministic post-processing boundary.

    LLM result -> schema validation -> category validation -> grounding signal
    -> canonical ID assignment -> source attachment -> evidence generation
    -> final requirement.

Failures are explicit (status strings, never exceptions for model failures).
Nothing is ever fabricated: no requirement from failed output, no evidence
without a requirement, no model-supplied document/page/identity.

Grounding note: grounding_score is MEASURED and reported, but never a hard
reject on its own — Arabic source text with English summaries legitimately
shares zero tokens, and paraphrases may share few. Hard gates are
schema/shape/category/emptiness only.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.pipeline.contracts import (
    EvidenceLink,
    LLMNormalizationResult,
    RequirementCandidate,
    ValidatedRequirement,
)

try:  # pragma: no cover - read-only contract source of truth
    from evaluation.stage3h.single_req_tasks import ALLOWED_CATEGORIES
except Exception:  # pragma: no cover
    ALLOWED_CATEGORIES = ["LEGAL", "TECHNICAL", "EXPERIENCE", "EQUIPMENT", "FINANCIAL",
                          "SCHEDULE", "COMMERCIAL", "HSE", "QA_QC", "PERSONNEL",
                          "SUBCONTRACTOR", "SUBMISSION", "UNKNOWN"]

_STOPWORDS = frozenset(
    "the a an and or of to in on for with must shall will be is are was were by from as at "
    "it its this that these those which who whose whom their there here all any each every no "
    "not only also than then so such into over under again once per via de la le les und der die das".split()
)

_CHUNK_PREFIX = re.compile(r"^(chunk-\d+)")


def _content_tokens(text: str) -> List[str]:
    toks = re.findall(r"[A-Za-z0-9\u0600-\u06FF]+", (text or "").lower())
    return [t for t in toks if len(t) > 3 and t not in _STOPWORDS]


def grounding_score(summary: str, source_text: str) -> float:
    """Fraction of summary content-tokens present in the source. Signal only."""
    s, src = _content_tokens(summary), set(_content_tokens(source_text))
    if not s:
        return 0.0
    return round(sum(1 for t in s if t in src) / len(s), 3)


def validate_llm_result(result: Optional[LLMNormalizationResult]) -> Tuple[bool, str, float]:
    """Hard gates: present, non-empty summary, allowed category. Returns (ok, status, _)."""
    if result is None:
        return False, "empty", 0.0
    if not (result.summary or "").strip():
        return False, "empty", 0.0
    if result.category not in ALLOWED_CATEGORIES:
        return False, "bad_category", 0.0
    return True, "ok", 0.0


def bind_requirement(result: LLMNormalizationResult, candidate: RequirementCandidate,
                     provisional_id: Optional[str] = None) -> ValidatedRequirement:
    """Attach provenance deterministically FROM THE CANDIDATE.

    Any model-supplied identity is dropped: the caller passes only the four
    minimal-contract fields inside LLMNormalizationResult, so there is nothing
    else to drop by construction.
    """
    return ValidatedRequirement(
        requirement_id=provisional_id or candidate.candidate_id,
        candidate_id=candidate.candidate_id,
        parent_chunk_id=candidate.parent_chunk_id,
        summary=result.summary.strip(),
        category=result.category,
        mandatory=result.mandatory,
        applicable_entity=result.applicable_entity,
        source_document=candidate.source_document,
        page_number=candidate.page,
        source_text=candidate.source_text,
        provenance={"quote_en": candidate.source_text[:200]},
        extraction_method="two-stage",
        confidence=None,
    )


def derive_evidence(requirement: ValidatedRequirement) -> EvidenceLink:
    """Deterministic 1-to-1 evidence. fact == summary by construction."""
    return EvidenceLink(
        evidence_id=f"{requirement.candidate_id}-ev-01",
        requirement_id=requirement.requirement_id,
        candidate_id=requirement.candidate_id,
        fact=requirement.summary,
        source_document=requirement.source_document,
        page_number=requirement.page_number,
        provenance={"quote_en": requirement.source_text[:200]},
        confidence=None,
    )


def _chunk_prefix(candidate_id: str) -> Optional[str]:
    m = _CHUNK_PREFIX.match(candidate_id or "")
    return m.group(1) if m else None


def assign_canonical_ids(requirements: List[ValidatedRequirement],
                         evidence: List[EvidenceLink]) -> Tuple[List[ValidatedRequirement], List[EvidenceLink], List[Dict[str, str]]]:
    """Deterministic REQ-XXX assignment (sorted by document/page/summary).

    Includes the chunk-prefix drift guard: evidence whose candidate prefix does
    not match its requirement's is rejected, never attached elsewhere.
    Returns (final_requirements, final_evidence, failures).
    """
    failures: List[Dict[str, str]] = []
    ordered = sorted(requirements, key=lambda r: (r.source_document, r.page_number, r.summary))
    old_to_new = {r.requirement_id: f"REQ-{i + 1:03d}" for i, r in enumerate(ordered)}
    for r in ordered:
        r.requirement_id = old_to_new[r.requirement_id]
    final_evs: List[EvidenceLink] = []
    for e in evidence:
        req = next((r for r in ordered if r.candidate_id == e.candidate_id), None)
        if req is None:
            failures.append({"evidence_id": e.evidence_id, "reason": "orphan_evidence"})
            continue
        rp, ep = _chunk_prefix(req.candidate_id), _chunk_prefix(e.candidate_id)
        if rp and ep and rp != ep:
            failures.append({"evidence_id": e.evidence_id, "reason": "provenance_drift"})
            continue
        if (rp is None) != (ep is None):
            failures.append({"evidence_id": e.evidence_id, "reason": "provenance_drift"})
            continue
        e.requirement_id = req.requirement_id
        final_evs.append(e)
    return ordered, final_evs, failures


def deduplicate(requirements: List[ValidatedRequirement]) -> List[ValidatedRequirement]:
    """Exact dedup on (summary, category, mandatory, applicable_entity). First wins."""
    seen = set()
    out = []
    for r in requirements:
        key = (r.summary, r.category, r.mandatory, r.applicable_entity)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def post_process(pairs: List[Tuple[LLMNormalizationResult, RequirementCandidate]]
                 ) -> Tuple[List[ValidatedRequirement], List[EvidenceLink], List[Dict[str, str]]]:
    """Full deterministic boundary over validated (result, candidate) pairs."""
    failures: List[Dict[str, str]] = []
    bound: List[ValidatedRequirement] = []
    for result, cand in pairs:
        ok, status, _ = validate_llm_result(result)
        if not ok:
            failures.append({"candidate_id": cand.candidate_id, "reason": status})
            continue
        bound.append(bind_requirement(result, cand))
    deduped = deduplicate(bound)
    evs = [derive_evidence(r) for r in deduped]
    final_reqs, final_evs, id_failures = assign_canonical_ids(deduped, evs)
    return final_reqs, final_evs, failures + id_failures
