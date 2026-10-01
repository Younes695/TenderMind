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

_FORM_REF = re.compile(r"\b((?:FORM|Exhibit|Annex(?:ure)?|Appendix)[ \t]*\n?[ \t]*[A-Z0-9][A-Z0-9.\-]*)", re.IGNORECASE)
_ROMAN = r"(?=[IVXLCM])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
_REF_ID = re.compile(r"^(FORM|EXHIBIT|ANNEX|ANNEXURE|APPENDIX) (" + _ROMAN
                     + r"|\d{1,5}(?:[.\-]\d{1,3})*[A-Z]?|[A-Z](?:[.\-]?\d{1,3})*)$")


def normalize_form_ref(raw: str):
    """'Appendix\\nV' -> 'APPENDIX V'. None for a following word that is not an
    identifier ('Appendix shall', 'Annexure to'), which flooded the missing list."""
    ref = re.sub(r"\s+", " ", raw or "").strip().rstrip(".-").upper()
    return ref if _REF_ID.match(ref) else None


@dataclass
class Gap:
    gap_id: str
    kind: str  # missing-file | unsupported-type | failed-extraction | partial-extraction |
               # empty-ocr | referenced-form-absent | empty-analysis
    description: str
    evidence: List[str] = field(default_factory=list)


def evidence_page(ev: Any):
    """'vol1.pdf#p7' -> ('vol1.pdf', '7'); a plain name -> (name, None). Only a
    page suffix is cut, so a file name with '#' in it ('Addendum #1.pdf') stays whole."""
    name, sep, page = str(ev).rpartition("#p")
    return (name, page) if sep and page.isdigit() else (str(ev), None)


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
        elif d.failed_pages:
            pages = sorted(set(d.failed_pages))
            shown = ", ".join(str(p) for p in pages[:20]) + (" …" if len(pages) > 20 else "")
            add("partial-extraction",
                f"{d.filename}: {len(pages)} page(s) could not be read (pages {shown}); "
                f"what is on them beyond any text layer they carry is not part of the analysis. "
                f"{d.error or ''}".strip(),
                [f"{d.filename}#p{p}" for p in pages])
    texts = {s.source_document: s for s in sources}
    for d in documents:
        # _entry never marks a zero-text document COMPLETE; this is PARTIAL
        # with pages read but nothing in them (a blank scan, a table-only file).
        if (d.status in ("COMPLETE", "PARTIAL") and d.page_count and d.total_text_chars == 0
                and not d.failed_pages):
            add("empty-ocr", f"{d.filename} extracted zero text (empty OCR/scan?)", [d.filename])
    # referenced forms absent: form refs in text with no matching document
    known = " ".join(d.filename for d in documents).lower()
    refs: Dict[str, List[str]] = {}
    for s in sources:
        for m in _FORM_REF.finditer(s.text or ""):
            ref = normalize_form_ref(m.group(1))
            if ref:
                refs.setdefault(ref, []).append(f"{s.source_document}#p{s.page_number}")
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
