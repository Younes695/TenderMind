"""Stage 4F — grounded risk signals + management synthesis MVP.

RISK_SIGNAL: traceable observations only — risk_type, description, supporting
evidence, source document/location, requires_management_review=true. NEVER
severity, probability, monetary/business impact, or BID/NO-BID. Anything not
explicitly supplied by source or business rules is left absent, not invented.

SYNTHESIS MVP: deterministic template over validated findings (counts, facts,
empty states). Neutral, grounded, uncertainty-preserving. AI synthesis stays
NOT_CONFIGURED; this MVP is what ships.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.pipeline.ambiguity import Ambiguity
from app.pipeline.commercial_schedule import CommercialFacts
from app.pipeline.contracts import ValidatedRequirement
from app.pipeline.gaps import Gap
from app.pipeline.reconciliation_mvp import Conflict


@dataclass
class RiskSignal:
    risk_id: str
    risk_type: str  # missing-security | short-validity | unsupported-docs |
                    # failed-extraction | unresolved-conflict | open-ambiguity |
                    # deadline-pressure (explicit dates only)
    description: str
    evidence: List[str] = field(default_factory=list)
    source_document: str = ""
    source_location: str = ""
    requires_management_review: bool = True


def derive_risk_signals(gaps: List[Gap], ambiguities: List[Ambiguity],
                        conflicts: List[Conflict], commercial: CommercialFacts,
                        requirements: List[ValidatedRequirement]) -> List[RiskSignal]:
    """Grounded signals only. No severity/probability/impact, ever."""
    out: List[RiskSignal] = []
    n = 0

    def add(rtype, desc, ev, doc="", loc=""):
        nonlocal n
        n += 1
        out.append(RiskSignal(risk_id=f"RISK-{n:03d}", risk_type=rtype, description=desc,
                              evidence=list(ev)[:4], source_document=doc, source_location=loc))

    if commercial.bid_security is None:
        add("missing-security", "no explicit bid-security terms found in extracted material",
            ["commercial:bid_security=null"])
    for g in gaps:
        if g.kind in ("failed-extraction", "unsupported-type", "missing-file"):
            add("failed-extraction" if g.kind == "failed-extraction" else "unsupported-docs",
                f"package completeness issue: {g.description}", g.evidence,
                (g.evidence[0] if g.evidence else ""))
    for c in conflicts:
        add("unresolved-conflict", f"conflicting sources preserved for review: {c.reason}",
            c.evidence)
    n_amb = len(ambiguities)
    if n_amb:
        add("open-ambiguity", f"{n_amb} requirement(s) need clarification before commitment",
            [a.ambiguity_id for a in ambiguities])
    return out


def risk_dicts(signals: List[RiskSignal]) -> List[Dict[str, Any]]:
    return [{"risk_id": s.risk_id, "risk_type": s.risk_type, "description": s.description,
             "evidence": s.evidence, "source_document": s.source_document,
             "source_location": s.source_location,
             "requires_management_review": s.requires_management_review} for s in signals]


def synthesize(requirements: List[ValidatedRequirement], deadlines: List[Dict[str, Any]],
               commercial: CommercialFacts, gaps: List[Gap], ambiguities: List[Ambiguity],
               conflicts: List[Conflict], risks: List[RiskSignal],
               doc_status: Dict[str, int]) -> Dict[str, Any]:
    """Deterministic management synthesis. Empty states explicit; no invention."""
    from collections import Counter
    cats = Counter(r.category for r in requirements)
    Naj = lambda x: x if x else "not available in validated material"
    return {
        "status": "SYNTHESIS_MVP_DETERMINISTIC",
        "key_obligations": Naj([f"{r.requirement_id}: {r.summary}"
                                 for r in requirements if r.mandatory is True][:20]),
        "obligation_count": sum(1 for r in requirements if r.mandatory is True),
        "requirements_by_category": dict(cats),
        "important_deadlines": deadlines[:10] if deadlines else "not available in validated material",
        "commercial_facts": {
            "currency": commercial.currency or "not available in validated material",
            "payment_terms": commercial.payment_terms or "not available in validated material",
            "bid_security": commercial.bid_security or "not available in validated material",
            "validity": commercial.validity or "not available in validated material"},
        "missing_unsupported": ([g.description for g in gaps]
                                if gaps else "no package gaps detected"),
        "ambiguities_requiring_clarification": (
            [a.description for a in ambiguities] if ambiguities
            else "no ambiguities flagged"),
        "conflicts_requiring_review": (
            [c.reason for c in conflicts] if conflicts
            else "no unresolved conflicts"),
        "risk_observations": ([s.description for s in risks] if risks
                               else "no grounded risk signals"),
        "document_status": doc_status,
        "uncertainty_note": ("counts reflect validated material only; null/UNKNOWN fields "
                             "mean unknown, not negative"),
    }
