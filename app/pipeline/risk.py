"""Stage 4A — GAP / AMBIGUITY / RISK / SYNTHESIS boundaries.

Separate capabilities, decision-support only:
- No invented risk severity, no invented business impact.
- No automatic BID / NO-BID / GO / NO-GO (the existing decision engine is
  untouched and remains disconnected from this pipeline).
- Only the deterministic gap summary below is connected: it counts what is
  already explicit on ValidatedRequirement (mandatory is None, missing source).
  Everything interpretive (ambiguity, risk, synthesis) is NOT_CONFIGURED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.pipeline.contracts import NOT_CONFIGURED, ValidatedRequirement


@dataclass
class GapSummary:
    total_requirements: int = 0
    mandatory_unknown: int = 0  # mandatory is None -> needs human review
    missing_source: int = 0
    unknown_category: int = 0  # quarantined abstentions, filter before surfacing
    requirement_ids_needing_review: List[str] = field(default_factory=list)


def summarize_gaps(requirements: List[ValidatedRequirement]) -> GapSummary:
    """Pure deterministic gap counts. No severity, no impact, no decisions."""
    out = GapSummary(total_requirements=len(requirements))
    for r in requirements:
        needs = False
        if r.mandatory is None:
            out.mandatory_unknown += 1
            needs = True
        if not r.source_document:
            out.missing_source += 1
            needs = True
        if r.category == "UNKNOWN":
            out.unknown_category += 1
            needs = True
        if needs:
            out.requirement_ids_needing_review.append(r.requirement_id)
    return out


def analyze_ambiguity(_requirements: List[ValidatedRequirement]) -> Dict[str, Any]:
    """No backend in 4A."""
    return {"status": "NOT_CONFIGURED", "backend": NOT_CONFIGURED}


def identify_risks(_requirements: List[ValidatedRequirement]) -> Dict[str, Any]:
    """No backend in 4A. Severity is never invented."""
    return {"status": "NOT_CONFIGURED", "backend": NOT_CONFIGURED}


def synthesize(_requirements: List[ValidatedRequirement]) -> Dict[str, Any]:
    """No backend in 4A."""
    return {"status": "NOT_CONFIGURED", "backend": NOT_CONFIGURED}
