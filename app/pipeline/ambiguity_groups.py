"""Stage 4H — ambiguity aggregation (deterministic, presentation-level).

Raw ambiguity signals -> normalize -> exact/near-duplicate grouping ->
source-local grouping. Reduces noisy presentation while preserving source
coverage. Every grouped item keeps: contributing signal IDs, document,
page/location, exact evidence, original raw signals.

Grouping rules (all must hold to merge):
- same ambiguity_type, AND
- same source document (NO cross-document merge without an explicit
  relationship), AND
- (exact normalized description) OR (near-duplicate >= 0.9 token Jaccard
  AND same page).
Anything else is rejected from grouping and stays standalone. No severity,
no suppression: every raw signal appears in exactly one group.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.pipeline.ambiguity import Ambiguity
from app.pipeline.candidate_compression import jaccard, normalize_text
from app.pipeline.gaps import evidence_page

_WS = re.compile(r"\s+")
NEAR_DUP_THRESHOLD = 0.9


@dataclass
class AmbiguityGroup:
    group_id: str
    ambiguity_type: str
    description: str  # representative (longest) description
    signal_ids: List[str] = field(default_factory=list)
    source_document: str = ""
    pages: List[int] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    raw_signals: List[Dict[str, Any]] = field(default_factory=list)
    clarification_needed: bool = True
    human_review_required: bool = True


def _norm_desc(text: str) -> str:
    return _WS.sub(" ", normalize_text(text)).strip()


def _same_page(pages: List[int]) -> bool:
    return len(set(pages)) == 1


def _page_of(evidence: List[str]) -> List[int]:
    pages = []
    for e in evidence or []:
        page = evidence_page(e)[1]  # the trailing page mark, as _doc_of reads it
        if page:
            pages.append(int(page))
    return pages


def _doc_of(evidence: List[str]) -> str:
    if evidence:
        return evidence_page(evidence[0])[0]  # 'Addendum #1.pdf#p3' -> 'Addendum #1.pdf'
    return ""


def aggregate_ambiguities(signals: List[Ambiguity]) -> tuple:
    """Returns (groups, report). Report: raw/grouped counts, reduction %,
    accepted group examples, rejected-from-grouping examples."""
    groups: List[AmbiguityGroup] = []
    rejected: List[Dict[str, str]] = []
    ordered = sorted(signals, key=lambda a: (a.ambiguity_type, a.ambiguity_id))
    for amb in ordered:
        placed = False
        nd = _norm_desc(amb.description)
        toks = set(nd.split())
        for g in groups:
            if g.ambiguity_type != amb.ambiguity_type:
                continue
            if _doc_of(amb.evidence) != g.source_document or not g.source_document:
                if not (not _doc_of(amb.evidence) and not g.source_document):
                    continue
            gtoks = set(_norm_desc(g.description).split())
            exact = nd == _norm_desc(g.description)
            pages = _page_of(amb.evidence) + list(g.pages)
            near = (jaccard(toks, gtoks) >= NEAR_DUP_THRESHOLD and _same_page(pages))
            if exact or near:
                g.signal_ids.append(amb.ambiguity_id)
                g.pages = sorted(set(g.pages + _page_of(amb.evidence)))
                g.evidence.extend([e for e in amb.evidence if e not in g.evidence])
                g.raw_signals.append({"ambiguity_id": amb.ambiguity_id,
                                      "requirement_id": amb.requirement_id,
                                      "description": amb.description,
                                      "evidence": amb.evidence})
                if len(amb.description) > len(g.description):
                    g.description = amb.description
                placed = True
                break
        if not placed:
            if any(g.ambiguity_type == amb.ambiguity_type and
                   _doc_of(amb.evidence) != g.source_document for g in groups):
                rejected.append({"ambiguity_id": amb.ambiguity_id,
                                 "reason": "cross-document without explicit relationship"})
            groups.append(AmbiguityGroup(
                group_id=f"AMBG-{len(groups) + 1:03d}", ambiguity_type=amb.ambiguity_type,
                description=amb.description, signal_ids=[amb.ambiguity_id],
                source_document=_doc_of(amb.evidence), pages=_page_of(amb.evidence),
                evidence=list(amb.evidence or []),
                raw_signals=[{"ambiguity_id": amb.ambiguity_id,
                              "requirement_id": amb.requirement_id,
                              "description": amb.description, "evidence": amb.evidence}],
                clarification_needed=amb.clarification_needed,
                human_review_required=amb.human_review_required))
    # coverage audit: every raw signal in exactly one group
    covered = sorted(s for g in groups for s in g.signal_ids)
    assert covered == sorted(a.ambiguity_id for a in signals), "signal loss in grouping"
    raw, grouped = len(signals), len(groups)
    report = {"raw_signals": raw, "grouped_items": grouped,
              "reduction_pct": round(100 * (raw - grouped) / raw, 1) if raw else 0.0,
              "accepted_examples": [{"group_id": g.group_id, "signals": len(g.signal_ids),
                                     "type": g.ambiguity_type} for g in groups if len(g.signal_ids) > 1][:5],
              "rejected_examples": rejected[:5]}
    return groups, report


def group_dicts(groups: List[AmbiguityGroup]) -> List[Dict[str, Any]]:
    return [{"group_id": g.group_id, "ambiguity_type": g.ambiguity_type,
             "description": g.description, "signal_count": len(g.signal_ids),
             "signal_ids": g.signal_ids, "source_document": g.source_document,
             "pages": g.pages, "evidence": g.evidence, "raw_signals": g.raw_signals,
             "clarification_needed": g.clarification_needed,
             "human_review_required": g.human_review_required} for g in groups]
