"""Stage 4F — gap / missing-document analysis (package completeness only).

Analyzes TENDER PACKAGE COMPLETENESS and ANALYSIS COVERAGE from available
material: missing files, unsupported types, failed extraction, empty OCR,
referenced-but-absent forms. NEVER bidder qualification scoring — there is no
company capability source in scope, so no claim of the form "company failed
requirement" is ever produced here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.pipeline.contracts import DocumentArtifact, SourceText

_FORM_REF = re.compile(r"\b(FORM\s+[A-Z0-9]+|Exhibit\s+[A-Z0-9]+|Annex(?:ure)?\s+[A-Z0-9]+|Appendix\s+[A-Z0-9]+)", re.IGNORECASE)


@dataclass
class Gap:
    gap_id: str
    kind: str  # missing-file | unsupported-type | failed-extraction | empty-ocr |
               # referenced-form-absent | empty-analysis
    description: str
    evidence: List[str] = field(default_factory=list)


def analyze_package_gaps(documents: List[DocumentArtifact],
                         sources: List[SourceText]) -> List[Gap]:
    """Deterministic completeness gaps. Evidence always attached."""
    gaps: List[Gap] = []
    n = 0

    def add(kind, desc, ev):
        nonlocal n
        n += 1
        gaps.append(Gap(gap_id=f"GAP-{n:03d}", kind=kind, description=desc, evidence=list(ev)))

    for d in sorted(documents, key=lambda x: x.filename):
        if d.missing:
            add("missing-file", f"{d.filename} listed but not found on storage", [d.filename])
        elif d.status == "UNSUPPORTED":
            add("unsupported-type", f"{d.filename} has no supported extractor", [d.filename])
        elif d.status == "FAILED":
            add("failed-extraction", f"{d.filename} failed: {d.error or 'unknown'}", [d.filename])
    texts = {s.source_document: s for s in sources}
    for d in documents:
        if d.status == "COMPLETE" and d.total_text_chars == 0:
            add("empty-ocr", f"{d.filename} extracted zero text (empty OCR/scan?)", [d.filename])
    # referenced forms absent: form refs in text with no matching document
    known = " ".join(d.filename for d in documents).lower()
    refs: Dict[str, List[str]] = {}
    for s in sources:
        for m in _FORM_REF.finditer(s.text or ""):
            refs.setdefault(m.group(1).upper(), []).append(f"{s.source_document}#p{s.page_number}")
    for ref in sorted(refs):
        token = re.sub(r"\W+", "", ref).lower()
        if token and token not in known.replace(" ", "").replace("_", "").replace("-", ""):
            add("referenced-form-absent",
                f"{ref} referenced but no matching document in package", refs[ref][:3])
    if not documents:
        add("empty-analysis", "tender package contains no documents", [])
    return gaps


def gap_dicts(gaps: List[Gap]) -> List[Dict[str, Any]]:
    return [{"gap_id": g.gap_id, "kind": g.kind, "description": g.description,
             "evidence": g.evidence} for g in gaps]
