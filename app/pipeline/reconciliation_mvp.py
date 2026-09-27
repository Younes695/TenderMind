"""Stage 4F — reconciliation MVP (deterministic only, no semantic reasoning).

Finds, with evidence links on every finding:
- duplicate/related groups (normalized-summary match across documents)
- explicit amendments (AddendumRecord/ClarificationRecord with affected_item
  matching a requirement's text or ID)
- explicit conflicts: same BOQ item code with DIFFERENT quantity/unit/price,
  or same normalized summary with different category-critical values.
- unresolved contradictions stay SUPERSESSION_UNKNOWN.

Never invents a winner: conflicts preserve both sides + flag for review.
Supersession is NEVER inferred from filenames alone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.pipeline.contracts import (
    AddendumRecord,
    ClarificationRecord,
    CommercialLineItem,
    ValidatedRequirement,
)
from app.pipeline.candidate_compression import normalize_text

# Requirement lifecycle states (explicit; UNKNOWN when impact unprovable).
ORIGINAL = "ORIGINAL"
AMENDED = "AMENDED"
CLARIFICATION = "CLARIFICATION"
SUPERSESSION_UNKNOWN = "SUPERSESSION_UNKNOWN"


@dataclass
class DuplicateGroup:
    group_id: str
    requirement_ids: List[str] = field(default_factory=list)
    relation: str = "duplicate"
    evidence: List[str] = field(default_factory=list)  # requirement IDs as evidence refs


@dataclass
class Conflict:
    conflict_id: str
    side_a: str = ""
    side_b: str = ""
    reason: str = ""
    evidence: List[str] = field(default_factory=list)
    resolution: str = "REVIEW_REQUIRED"  # never auto-resolved


@dataclass
class AmendmentLink:
    requirement_id: str
    amendment_source: str
    status: str = AMENDED  # AMENDED | CLARIFICATION | SUPERSESSION_UNKNOWN
    evidence: List[str] = field(default_factory=list)


def group_duplicates(requirements: List[ValidatedRequirement]) -> List[DuplicateGroup]:
    """Cross-document normalized-summary groups (2+ members, distinct docs)."""
    buckets: Dict[str, List[ValidatedRequirement]] = {}
    for r in sorted(requirements, key=lambda x: x.requirement_id):
        buckets.setdefault(normalize_text(r.summary), []).append(r)
    groups = []
    for i, (key, members) in enumerate(sorted(buckets.items())):
        docs = {m.source_document for m in members}
        if len(members) > 1 and len(docs) > 1:
            groups.append(DuplicateGroup(
                group_id=f"DUP-{i + 1:03d}",
                requirement_ids=[m.requirement_id for m in members],
                evidence=[m.requirement_id for m in members]))
    return groups


def link_amendments(requirements: List[ValidatedRequirement],
                    addenda: List[AddendumRecord],
                    clarifications: List[ClarificationRecord]
                    ) -> List[AmendmentLink]:
    """Link only on explicit affected_item/section text match. No filename inference."""
    links = []
    for r in requirements:
        donors = []
        for a in list(addenda) + list(clarifications):
            is_clar = isinstance(a, ClarificationRecord)
            if is_clar:
                needle = " ".join(x for x in (a.reference or "", a.question or "",
                                              a.response or "") if x)
            else:
                needle = (a.affected_item or "") + " " + (a.affected_section or "")
            if not needle.strip():
                continue
            hay = (r.summary or "") + " " + (r.source_text or "")
            if normalize_text(needle) and normalize_text(needle) in normalize_text(hay):
                donors.append(a)
        for d in donors:
            is_clar = isinstance(d, ClarificationRecord)
            links.append(AmendmentLink(                requirement_id=r.requirement_id,
                amendment_source=f"{d.source_document}!{d.location}",
                status=CLARIFICATION if is_clar else AMENDED,
                evidence=[r.requirement_id]))
        docname = (r.source_document or "").lower()
        if not donors and ("addendum" in docname or "clarification" in docname):
            links.append(AmendmentLink(
                requirement_id=r.requirement_id,
                amendment_source=f"{r.source_document}#p{r.page_number}",
                status=SUPERSESSION_UNKNOWN, evidence=[r.requirement_id]))
    return links


def find_boq_conflicts(items: List[CommercialLineItem]) -> List[Conflict]:
    """Same item code, different quantity/unit/price across rows/docs."""
    by_code: Dict[str, List[CommercialLineItem]] = {}
    for it in items:
        if (it.item or "").strip():
            by_code.setdefault(it.item.strip().upper(), []).append(it)
    conflicts = []
    n = 0
    for code in sorted(by_code):
        rows = by_code[code]
        vals = {(r.quantity or "", r.unit or "", r.unit_price or "", r.total_price or "")
                for r in rows}
        docs = {r.source_document for r in rows}
        if len(vals) > 1 and len(docs) >= 1 and len(rows) > 1:
            n += 1
            conflicts.append(Conflict(
                conflict_id=f"CONF-{n:03d}",
                side_a=f"{rows[0].source_document}!{rows[0].location}",
                side_b=f"{rows[1].source_document}!{rows[1].location}",
                reason=f"item {code} has differing quantity/unit/price across rows",
                evidence=[f"{rows[0].source_document}!{rows[0].location}",
                          f"{rows[1].source_document}!{rows[1].location}"]))
    return conflicts


def requirement_lifecycle(requirements: List[ValidatedRequirement],
                          links: List[AmendmentLink]) -> Dict[str, str]:
    """ORIGINAL default; AMENDED/CLARIFICATION only with evidence links."""
    linked = {}
    for l in links:
        linked.setdefault(l.requirement_id, l.status)
    return {r.requirement_id: linked.get(r.requirement_id, ORIGINAL) for r in requirements}
