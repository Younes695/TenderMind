"""Stage 4A — deterministic candidate discovery service.

Promotes the validated Stage 3I/3K segmentation concept into a reusable,
production-side service with explicit input/output contracts.

Rules:
- Deterministic and reproducible: inputs are sorted by (document, page, offset),
  so candidate IDs are stable regardless of ingestion order.
- Native candidate IDs: chunk-XXXX-seg-YY (keeps the assign_canonical_ids
  chunk-prefix drift guard effective; run-local relabels are NOT used here).
- No LLM calls. Ever. This module must not import any model client.
- Tiny inputs (<300 chars at parent level) are SKIPPED_TINY_INPUT (Stage 3D guard).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from app.pipeline.contracts import FailureCode, RequirementCandidate, SourceText

# Read-only reuse of the single production pattern source of truth.
# (Documented seam: evaluation.generic_extraction.GENERIC_PATTERNS. Values are
# never mutated here; a future move of the constant keeps this import working
# via the same name.)
try:  # pragma: no cover - import path varies by runner cwd
    from evaluation.generic_extraction import GENERIC_PATTERNS
except Exception:  # pragma: no cover
    GENERIC_PATTERNS = []

TINY_PARENT_THRESHOLD = 300
MIN_CANDIDATE_CHARS = 20
MAX_MIXED_CATEGORIES = 2
MIN_PRINTABLE_RATIO = 0.7
MAX_PER_PARENT = 20

_SENTENCE_SPLIT = re.compile(r"(?<=[.;?!])\s+(?=[A-Z0-9\"\u201c])")


def split_sentences(text: str) -> List[Tuple[str, int, int]]:
    """Split into (sentence, start, end) spans. Newlines first, then boundaries."""
    spans: List[Tuple[str, int, int]] = []
    line_start = 0
    lines: List[Tuple[str, int, int]] = []
    for m in re.finditer(r"\n", text):
        lines.append((text[line_start:m.start()], line_start, m.start()))
        line_start = m.end()
    lines.append((text[line_start:], line_start, len(text)))
    for line, base, _ in lines:
        if not line.strip():
            continue
        parts = _SENTENCE_SPLIT.split(line)
        offset = 0
        for part in parts:
            idx = line.find(part, offset)
            s, e = base + idx, base + idx + len(part)
            if part.strip():
                spans.append((part.strip(), s, e))
            offset = idx + len(part)
    return spans


def pattern_hits(sentence: str) -> List[str]:
    """Deterministic category signals for one sentence (production patterns)."""
    low = sentence.lower()
    hits: List[str] = []
    for pat, cat, _ in GENERIC_PATTERNS:
        try:
            if re.search(pat.lower(), low):
                hits.append(cat)
        except Exception:
            continue
    seen: List[str] = []
    for h in hits:
        if h not in seen:
            seen.append(h)
    return seen


def printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    ok = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    return ok / max(len(text), 1)


@dataclass
class DiscoveryMetrics:
    parents: int = 0
    accepted: int = 0
    rejected: int = 0
    skipped_tiny: int = 0
    rejected_by_reason: Dict[str, int] = field(default_factory=dict)


def _reject(parent_id: str, source_document: str, page: int, text: str,
            span: List[int], reason: str, hits: List[str]) -> Dict[str, Any]:
    return {
        "parent_chunk_id": parent_id,
        "source_document": source_document,
        "page": page,
        "source_text": text[:200],
        "span": span,
        "deterministic_signal_categories": hits,
        "rejection_reason": reason,
        "status": reason,
    }


def discover_from_parents(parents: List[Dict[str, Any]]) -> Tuple[List[RequirementCandidate], List[Dict[str, Any]], DiscoveryMetrics]:
    """Segment explicit parent chunks. Parents sorted by (document, page, id).

    Parent shape: {chunk_id, source_document, page_number|page, text}.
    Returns (accepted_candidates, rejected, metrics).
    """
    metrics = DiscoveryMetrics()
    ordered = sorted(parents, key=lambda p: (
        str(p.get("source_document", "")), int(p.get("page_number", p.get("page", 1)) or 1),
        str(p.get("chunk_id", ""))))
    accepted: List[RequirementCandidate] = []
    rejected: List[Dict[str, Any]] = []
    for parent in ordered:
        metrics.parents += 1
        pid = str(parent.get("chunk_id", f"chunk-{metrics.parents:04d}"))
        doc = str(parent.get("source_document", ""))
        page = int(parent.get("page_number", parent.get("page", 1)) or 1)
        text = parent.get("text", "") or ""
        if len(text.strip()) < TINY_PARENT_THRESHOLD:
            metrics.skipped_tiny += 1
            metrics.rejected_by_reason[FailureCode.SKIPPED_TINY_INPUT.value] = \
                metrics.rejected_by_reason.get(FailureCode.SKIPPED_TINY_INPUT.value, 0) + 1
            continue
        seq = 0
        for sent, start, end in split_sentences(text):
            hits = pattern_hits(sent)
            reason = None
            if len(sent) < MIN_CANDIDATE_CHARS:
                reason = FailureCode.REJECTED_TINY.value
            elif printable_ratio(sent) < MIN_PRINTABLE_RATIO:
                reason = FailureCode.REJECTED_OCR_GARBAGE.value
            elif len(hits) == 0:
                reason = FailureCode.REJECTED_NO_SIGNAL.value
            elif len(hits) > MAX_MIXED_CATEGORIES:
                reason = FailureCode.REJECTED_MIXED_MULTI.value
            if reason is not None:
                rejected.append(_reject(pid, doc, page, sent, [start, end], reason, hits))
                metrics.rejected += 1
                metrics.rejected_by_reason[reason] = metrics.rejected_by_reason.get(reason, 0) + 1
                continue
            if seq >= MAX_PER_PARENT:
                rejected.append(_reject(pid, doc, page, sent, [start, end], "over_parent_cap", hits))
                metrics.rejected += 1
                continue
            seq += 1
            accepted.append(RequirementCandidate(
                candidate_id=f"{pid}-seg-{seq:02d}",
                parent_chunk_id=pid,
                source_document=doc,
                page=page,
                source_text=sent,
                span=[start, end],
                deterministic_signal_categories=hits,
            ))
            metrics.accepted += 1
    return accepted, rejected, metrics


def discover_from_sources(sources: List[SourceText], max_chars: int = 3000) -> Tuple[List[RequirementCandidate], List[Dict[str, Any]], DiscoveryMetrics]:
    """Chunk page-level SourceTexts into parents, then segment.

    Parents are built per (document, page) in sorted order with paragraph-aware
    packing up to max_chars — the production analogue of chunk_documents.
    """
    ordered = sorted(sources, key=lambda s: (s.source_document, s.page_number))
    parents: List[Dict[str, Any]] = []
    seq = 0
    for src in ordered:
        paras = [p.strip() for p in (src.text or "").split("\n") if p.strip()]
        buf: List[str] = []
        cur = 0
        for p in paras:
            if buf and cur + len(p) + 1 > max_chars:
                seq += 1
                parents.append({
                    "chunk_id": f"chunk-{seq:04d}",
                    "source_document": src.source_document,
                    "page_number": src.page_number,
                    "text": "\n".join(buf),
                })
                buf, cur = [], 0
            buf.append(p)
            cur += len(p) + 1
        if buf:
            seq += 1
            parents.append({
                "chunk_id": f"chunk-{seq:04d}",
                "source_document": src.source_document,
                "page_number": src.page_number,
                "text": "\n".join(buf),
            })
    return discover_from_parents(parents)
