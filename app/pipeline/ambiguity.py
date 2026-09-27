"""Stage 4F — ambiguity analysis (safe deterministic contract).

Input: validated requirement/clause. Output: typed ambiguity with source
evidence + clarification_needed / human_review_required flags. Generic types
only; no business severity, ever.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.pipeline.contracts import ValidatedRequirement

_AMBIG_MARKERS = ("tbd", "to be determined", "to be advised", "tba", "???", "as applicable",
                  "if applicable", "as required", "as necessary", "to be agreed")
_RELATIVE_DATE = re.compile(r"within\s+\d+\s+(day|days|week|weeks|month|months|year|years)\s+(from|after|of)\b", re.IGNORECASE)


@dataclass
class Ambiguity:
    ambiguity_id: str
    requirement_id: str
    ambiguity_type: str  # missing-value | unclear-date-anchor | conflicting-wording |
                         # undefined-term | incomplete-reference | unclear-applicability |
                         # cross-document-inconsistency
    description: str
    evidence: List[str] = field(default_factory=list)
    clarification_needed: bool = True
    human_review_required: bool = True


_OBLIGATION = re.compile(r"\b(shall|must|is required|are required|mandatory|obliged)\b", re.IGNORECASE)


def analyze_ambiguity(requirements: List[ValidatedRequirement]) -> List[Ambiguity]:
    """Deterministic detectors over validated requirements."""
    out: List[Ambiguity] = []
    n = 0

    def add(req, typ, desc):
        nonlocal n
        n += 1
        out.append(Ambiguity(
            ambiguity_id=f"AMB-{n:03d}", requirement_id=req.requirement_id,
            ambiguity_type=typ, description=desc,
            evidence=[f"{req.source_document}#p{req.page_number}"]))

    for r in sorted(requirements, key=lambda x: x.requirement_id):
        text = (r.summary or "") + " " + (r.source_text or "")
        low = text.lower()
        if any(m in low for m in _AMBIG_MARKERS):
            add(r, "missing-value", "requirement contains an explicit TBD/applicability marker")
        if _RELATIVE_DATE.search(text) and r.category in ("SCHEDULE", "COMMERCIAL"):
            add(r, "unclear-date-anchor",
                "relative duration without an explicit anchor date in the requirement")
        if r.category == "UNKNOWN":
            add(r, "undefined-term", "model abstained: requirement meaning unclear from the fragment")
        if r.mandatory is None and _OBLIGATION.search(text):
            add(r, "unclear-applicability",
                "obligation wording present but mandatory flag is null: binding force unclear")
    return out


def ambiguity_dicts(items: List[Ambiguity]) -> List[Dict[str, Any]]:
    return [{"ambiguity_id": a.ambiguity_id, "requirement_id": a.requirement_id,
             "ambiguity_type": a.ambiguity_type, "description": a.description,
             "evidence": a.evidence, "clarification_needed": a.clarification_needed,
             "human_review_required": a.human_review_required} for a in items]
