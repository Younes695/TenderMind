"""Stage 4F — structured-first optimization + compression hardening.

Before any LLM call: a candidate whose information is already captured by
deterministic structured/text facts (BOQ rows, schedule facts, equipment
records, deadline/commercial facts) is marked STRUCTURED_COVERED with
provenance to the covering fact, and bypasses the LLM. Conservative by design:
coverage requires substantial token overlap with a structured row/fact; any
candidate needing semantic interpretation is NEVER suppressed.

Compression stage chain (measured, in order):
raw -> exact -> normalized -> near -> merged -> structured-covered -> AI queue.
Every reduction retains source IDs/document/page/text/merged_from/reason.
False-merge guards: never merge across different commercial terms, deadlines,
equipment items, or obligations just for shared vocabulary — enforced by
(signal-compatibility AND same-document default AND near-dup threshold).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from app.pipeline.contracts import CommercialLineItem, RequirementCandidate

_WS = re.compile(r"\s+")
_STOP = frozenset(
    "the a an and or of to in on for with must shall will be is are was were by from as at "
    "it its this that these those which who whose whom their there here all any each every no "
    "not only also than then so such into over under again once per via must be shall be".split())


def _content_tokens(text: str) -> List[str]:
    toks = re.findall(r"[A-Za-z0-9\u0600-\u06FF]+", (text or "").lower())
    return [t for t in toks if len(t) > 2 and t not in _STOP]


def _row_text(item: CommercialLineItem) -> str:
    return " ".join(x for x in (item.item or "", item.description or "",
                                item.unit or "", item.quantity or "",
                                item.unit_price or "", item.total_price or "") if x)


@dataclass
class StructuredCoverage:
    candidate_id: str
    covered_by: str  # structured fact identity, e.g. "BOQ:sched.xlsx!Sheet1!R5"
    kind: str        # boq-row | schedule-fact | equipment-fact | commercial-fact
    overlap: float
    source_document: str
    location: str


@dataclass
class StructuredFirstReport:
    before: int = 0
    covered: int = 0
    sent_to_ai: int = 0
    coverages: List[StructuredCoverage] = field(default_factory=list)

    @property
    def reduction_pct(self) -> float:
        return round(100.0 * self.covered / self.before, 2) if self.before else 0.0


def _overlap(a: List[str], b: List[str]) -> float:
    if not a:
        return 0.0
    sb = set(b)
    return sum(1 for t in a if t in sb) / len(a)


def structured_first_filter(
    candidates: List[RequirementCandidate],
    line_items: List[CommercialLineItem],
    fact_texts: List[Dict[str, str]] | None = None,
    threshold: float = 0.6,
) -> Tuple[List[RequirementCandidate], StructuredFirstReport]:
    """Split candidates into (ai_queue, report). Conservative: overlap of the
    candidate's content tokens with a structured row/fact >= threshold, AND the
    candidate must carry a commercial/schedule/equipment-type signal (never
    suppress LEGAL/PERSONNEL/EXPERIENCE/HSE/QA_QC/SUBCONTRACTOR semantics).

    fact_texts: [{kind, text, source_document, location, identity}] for
    schedule/equipment/commercial facts.
    """
    report = StructuredFirstReport(before=len(candidates))
    facts = list(fact_texts or [])
    for li in line_items:
        facts.append({"kind": "boq-row", "text": _row_text(li),
                      "source_document": li.source_document, "location": li.location,
                      "identity": f"BOQ:{li.source_document}!{li.location}"})
    suppressible = {"COMMERCIAL", "SCHEDULE", "TECHNICAL", "EQUIPMENT", "FINANCIAL"}
    ai_queue: List[RequirementCandidate] = []
    for c in sorted(candidates, key=lambda x: x.candidate_id):
        ctoks = _content_tokens(c.source_text)
        if not ctoks or not (set(c.deterministic_signal_categories) <= suppressible
                             and set(c.deterministic_signal_categories)):
            ai_queue.append(c)
            continue
        best = None
        for f in facts:
            ov = _overlap(ctoks, _content_tokens(f["text"]))
            if ov >= threshold and (best is None or ov > best[0]):
                best = (ov, f)
        if best is None:
            ai_queue.append(c)
            continue
        ov, f = best
        report.covered += 1
        report.coverages.append(StructuredCoverage(
            candidate_id=c.candidate_id, covered_by=f["identity"], kind=f["kind"],
            overlap=round(ov, 3), source_document=f["source_document"], location=f["location"]))
    report.sent_to_ai = len(ai_queue)
    return ai_queue, report
