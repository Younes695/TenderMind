"""Stage 4A — candidate compression (deterministic, no LLM).

Pipeline: discovery -> exact dedup -> normalized dedup -> near-duplicate
detection -> safe merge -> priority/filtering -> LLM queue.

Safety invariants (tested):
- Provenance survives every merge (merged_from + merged_sources audit trail).
- Same-document merge by default. Cross-document merge requires explicit
  allow_cross_document=True AND records the justification.
- Candidates with disjoint deterministic signal sets NEVER merge (clearly
  different requirements).
- Deterministic: inputs sorted by candidate_id; ties broken identically.
- No LLM involved. No source text is ever generated or altered on the winner
  (winner keeps its own source_text verbatim).
"""
from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.pipeline.contracts import RequirementCandidate

_WS = re.compile(r"\s+")
_PUNCT = str.maketrans("", "", string.punctuation + "«»“”‘’—–…")


def normalize_text(text: str) -> str:
    """Comparison form: lowercase, punctuation stripped, whitespace collapsed."""
    t = (text or "").lower().translate(_PUNCT)
    return _WS.sub(" ", t).strip()


def token_set(text: str) -> set:
    return set(normalize_text(text).split())


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class CompressionMetrics:
    raw_candidates: int = 0
    exact_duplicates: int = 0
    normalized_duplicates: int = 0
    near_duplicates: int = 0
    merged_candidates: int = 0
    filtered_low_priority: int = 0
    final_ai_candidates: int = 0

    @property
    def reduction_pct(self) -> float:
        if not self.raw_candidates:
            return 0.0
        return round(100.0 * (self.raw_candidates - self.final_ai_candidates) / self.raw_candidates, 2)


@dataclass
class CompressionReport:
    metrics: CompressionMetrics = field(default_factory=CompressionMetrics)
    merge_groups: List[Dict[str, Any]] = field(default_factory=list)
    filtered: List[Dict[str, str]] = field(default_factory=list)


def _signals_compatible(a: RequirementCandidate, b: RequirementCandidate) -> bool:
    sa, sb = set(a.deterministic_signal_categories), set(b.deterministic_signal_categories)
    if not sa or not sb:
        return True  # no signal info -> cannot prove difference; other gates still apply
    return bool(sa & sb)


def _same_document(a: RequirementCandidate, b: RequirementCandidate) -> bool:
    return a.source_document == b.source_document


def _record_merge(winner: RequirementCandidate, absorbed: RequirementCandidate, kind: str,
                  report: CompressionReport, justification: str = "") -> None:
    winner.merged_from.append(absorbed.candidate_id)
    report.merge_groups.append({
        "winner": winner.candidate_id,
        "absorbed": absorbed.candidate_id,
        "kind": kind,
        "winner_document": winner.source_document,
        "winner_page": winner.page,
        "absorbed_document": absorbed.source_document,
        "absorbed_page": absorbed.page,
        "justification": justification,
    })


def compress_candidates(
    candidates: List[RequirementCandidate],
    allow_cross_document: bool = False,
    cross_document_justification: str = "",
    priority_categories: Optional[List[str]] = None,
    max_ai_candidates: Optional[int] = None,
    near_dup_threshold: float = 0.85,
) -> Tuple[List[RequirementCandidate], CompressionReport]:
    """Compress deterministically. Returns (ai_queue, report)."""
    report = CompressionReport()
    ordered = sorted(candidates, key=lambda c: c.candidate_id)
    report.metrics.raw_candidates = len(ordered)

    # Pass 1: exact duplicates (byte-identical source_text).
    seen_exact: Dict[str, RequirementCandidate] = {}
    survivors: List[RequirementCandidate] = []
    for c in ordered:
        w = seen_exact.get(c.source_text)
        if w is not None and _signals_compatible(w, c) and (
                _same_document(w, c) or allow_cross_document):
            _record_merge(w, c, "exact",
                          report, cross_document_justification if not _same_document(w, c) else "")
            report.metrics.exact_duplicates += 1
            continue
        seen_exact.setdefault(c.source_text, c)
        survivors.append(c)

    # Pass 2: normalized duplicates.
    seen_norm: Dict[str, RequirementCandidate] = {}
    survivors2: List[RequirementCandidate] = []
    for c in survivors:
        key = normalize_text(c.source_text)
        w = seen_norm.get(key)
        if w is not None and _signals_compatible(w, c) and (
                _same_document(w, c) or allow_cross_document):
            _record_merge(w, c, "normalized",
                          report, cross_document_justification if not _same_document(w, c) else "")
            report.metrics.normalized_duplicates += 1
            continue
        seen_norm.setdefault(key, c)
        survivors2.append(c)

    # Pass 3: near duplicates (Jaccard on normalized token sets).
    winners: List[RequirementCandidate] = []
    for c in survivors2:
        c_tokens = token_set(c.source_text)
        merged = False
        for w in winners:
            if not _signals_compatible(w, c):
                continue
            if not _same_document(w, c) and not allow_cross_document:
                continue
            if jaccard(token_set(w.source_text), c_tokens) >= near_dup_threshold:
                _record_merge(w, c, "near_duplicate",
                              report, cross_document_justification if not _same_document(w, c) else "")
                report.metrics.near_duplicates += 1
                merged = True
                break
        if not merged:
            winners.append(c)

    report.metrics.merged_candidates = (
        report.metrics.exact_duplicates + report.metrics.normalized_duplicates
        + report.metrics.near_duplicates)

    # Pass 4: priority / filtering (deterministic order; filtered items reported).
    ai_queue: List[RequirementCandidate] = []
    if priority_categories:
        prio = set(priority_categories)
        for c in winners:
            if set(c.deterministic_signal_categories) & prio:
                ai_queue.append(c)
            else:
                report.filtered.append({"candidate_id": c.candidate_id, "reason": "filtered_low_priority"})
                report.metrics.filtered_low_priority += 1
    else:
        ai_queue = list(winners)

    # Deterministic priority order: more signals first, then longer text, then id.
    ai_queue.sort(key=lambda c: (-len(c.deterministic_signal_categories),
                                 -len(c.source_text), c.candidate_id))
    if max_ai_candidates is not None and len(ai_queue) > max_ai_candidates:
        dropped = ai_queue[max_ai_candidates:]
        ai_queue = ai_queue[:max_ai_candidates]
        for c in dropped:
            report.filtered.append({"candidate_id": c.candidate_id, "reason": "over_ai_cap"})
        report.metrics.filtered_low_priority = len(report.filtered)

    report.metrics.final_ai_candidates = len(ai_queue)
    return ai_queue, report
