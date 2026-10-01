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
from typing import Any, Dict, List, Optional, Set, Tuple

from app.pipeline.contracts import DocumentArtifact, SourceText

_ROMAN = r"(?=[IVXLCM])M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})"
# I-1 is not I. Sub-number separators are explicit, so a long digit run cannot backtrack exponentially.
_ID = (_ROMAN + r"(?:[.\-]\d{1,3})*|\d{1,5}(?:[.\-]\d{1,3})*[A-Z]?|[A-Z](?:\d{1,3})?(?:[.\-]\d{1,3})*")
_REF_ID = re.compile(r"^(FORM|EXHIBIT|ANNEX|ANNEXURE|APPENDIX) (" + _ID + r")$")
_DASHES = "\\-\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
_GAP = r"[ \t]*(?:\n[ \t]*){0,2}"  # TOC lines put 'APPENDIX', the id and the title on separate lines
_SEP = r"(?:[ \t]+(?:\n[ \t]*){0,2}|[ \t]*(?:\n[ \t]*){1,2})"  # at least one space or line break
# The word is matched case-insensitively, the identifier case-sensitively ('Appendix shall' is no reference);
# a separator is required ('LIST OF ANNEXURES' is no ANNEXURE S).
_REF = re.compile(r"\b(?P<word>(?i:FORM|EXHIBIT|ANNEXURE|ANNEX|APPENDIX))(?:" + _GAP + r"[" + _DASHES + r"]"
                  + _GAP + r"|" + _SEP + r")(?P<id>" + _ID + r")(?![A-Za-z0-9+])")
_PROSE_WORDS = {"FORM", "EXHIBIT"}  # 'rectangular form R+jX', 'the bids exhibit a spread'
_NOT_APPLICABLE = re.compile(r"\bNOT\s+APPLICABLE\b|\(\s*N/A\s*\)", re.IGNORECASE)
_NOT_APPLICABLE_ONLY = re.compile(r"[\s(" + _DASHES + r"]*(?:NOT\s+APPLICABLE|N/A)[\s)]*", re.IGNORECASE)
_STOPWORDS = {"the", "and", "for", "of", "to", "in", "with", "as", "shall", "be", "is", "are", "per", "see",
              "refer", "this", "that", "which", "will", "by", "or", "on", "at", "from", "under", "a", "an"}
_CONNECTORS = _STOPWORDS | {"specified", "including", "following", "&"}
_TOP_UNITS = 3     # a heading must open the page / sheet: at most this many text units before it
_LIST_REFS = 3     # a page opening this many different references on their own lines is a list / contents page
_LIST_TOP_REFS, _LIST_TOP_UNITS = 2, 15  # ... or two of them within its first 15 units (a short list)

RefKey = Tuple[str, str]


def normalize_form_ref(raw: str):
    """'Appendix\\nV' -> 'APPENDIX V', 'ANNEXURE-II' -> 'ANNEXURE II'. None for a following word that is
    not an identifier ('Appendix shall', 'Annexure to'), which flooded the missing list."""
    ref = re.sub(r"\s+", " ", raw or "").strip().rstrip(".-").upper()
    ref = re.sub(r"^(FORM|EXHIBIT|ANNEXURE|ANNEX|APPENDIX)\s*[" + _DASHES + r"]\s*", r"\1 ", ref)
    return ref if _REF_ID.match(ref) else None


def _refs_in(text: str):
    """(key, display, match) for every reference; ANNEX and ANNEXURE are one family."""
    for m in _REF.finditer(text or ""):
        word = m.group("word")
        if word.upper() in _PROSE_WORDS and word == word.lower():
            continue
        family = word.upper()
        yield ("ANNEX" if family == "ANNEXURE" else family, m.group("id")), f"{family} {m.group('id')}", m


def _unit_start(text: str, pos: int) -> int:
    """Start of the line or table cell that holds pos."""
    return max(text.rfind("\n", 0, pos), text.rfind("|", 0, pos)) + 1


def _units_before(text: str, start: int) -> List[str]:
    return [u.strip() for u in re.split(r"[\n|]", text[:start]) if u.strip()]


def _unit_rest(text: str, end: int) -> str:
    m = re.compile(r"[\n|]").search(text, end)
    return text[end:m.start() if m else len(text)].strip()


def _next_units(text: str, end: int, n: int = 1) -> List[str]:
    m = re.compile(r"[\n|]").search(text, end)
    return [u.strip() for u in re.split(r"[\n|]", text[m.end():] if m else "") if u.strip()][:n]


def _next_unit(text: str, end: int) -> str:
    return (_next_units(text, end) or [""])[0]


def _is_title(s: str) -> bool:
    """'TO MAIN SOW/TS', 'Template Administration' - not 'and this PTS shall be applied'."""
    s = s.lstrip(_DASHES + ":. \t")
    if not s or not (s[0].isupper() or s[0].isdigit() or s[0] == "("):
        return False
    return not any(w in _STOPWORDS for w in re.findall(r"[a-z]+", s))


def _section_evidence(text: str, m) -> bool:
    """The reference is the section's own heading, not a mention: it opens its line, the line before
    does not run into it, and it either opens the page / sheet or reads '<REF> TO <MAIN DOCUMENT>'.
    Drawing title blocks are not used: they repeat one label on many sheets and can name another part."""
    start = _unit_start(text, m.start())
    if text[start:m.start()].strip():
        return False
    before = _units_before(text, start)
    if before:
        last = re.findall(r"[A-Za-z&]+", before[-1])
        if last and last[-1].lower() in _CONNECTORS:
            return False
    rest, nxt = _unit_rest(text, m.end()), _next_unit(text, m.end())
    if rest[:1] in (",", ";") or rest in (".", ")"):
        return False
    if rest.startswith("."):
        rest = rest[1:].strip()
        if not rest:
            return False
    titled = _is_title(rest) if rest else not (nxt[:1].islower())
    if not titled:
        return False
    if len(before) < _TOP_UNITS:
        return True
    # '<REF> / TO MAIN SOW' - but not 'APPENDIX VII TO BE COMPLETED AND SIGNED'
    to_main = rest if rest else nxt
    if to_main == "TO":
        after = (_next_units(text, m.end(), 3)[1:2] if not rest else _next_units(text, m.end(), 1)) or [""]
        target = after[0].split()[:1]
    elif to_main.startswith("TO "):
        target = to_main[3:].split()[:1]
    else:
        return False
    return bool(target) and target[0].lower() not in _STOPWORDS


def _referenced_documents(documents: List[DocumentArtifact], sources: List[SourceText]):
    """-> (mentions {key: (display, [evidence])}, present keys, not-applicable keys)."""
    present: Set[RefKey] = set()
    for d in documents:  # 'ITB_Annexure_II.xlsx': '_' is a word character, so \b would not see the word;
        # a file name is no prose, so 'annex xvi losses.xlsx' is read upper-cased
        present.update(k for k, _d, _m in _refs_in(d.filename.replace("_", " ").upper()))
    mentions: Dict[RefKey, Tuple[str, List[str]]] = {}
    not_applicable: Set[RefKey] = set()
    for s in sources:
        text = s.text or ""
        found = list(_refs_in(text))
        for key, display, _m in found:
            mentions.setdefault(key, (display, []))[1].append(f"{s.source_document}#p{s.page_number}")
        leading = [(k, m) for k, _d, m in found if not text[_unit_start(text, m.start()):m.start()].strip()]
        top = {k for k, m in leading if len(_units_before(text, _unit_start(text, m.start()))) < _LIST_TOP_UNITS}
        if len({k for k, _m in leading}) >= _LIST_REFS or len(top) >= _LIST_TOP_REFS:
            # contents page or list of attachments: no evidence, but it can mark an entry NOT APPLICABLE -
            # on the entry's own title, or on a line of its own right after it, never a later line
            for i, (key, m) in enumerate(leading):
                entry_end = leading[i + 1][1].start() if i + 1 < len(leading) else len(text)
                rest = _unit_rest(text, m.end())
                units = [u.strip() for u in re.split(r"[\n|]", text[m.end():entry_end]) if u.strip()][:3]
                title = rest or (units[0] if units else "")
                if _NOT_APPLICABLE.search(title) or any(_NOT_APPLICABLE_ONLY.fullmatch(u) for u in units[:2]):
                    not_applicable.add(key)
            continue
        for key, m in leading:
            if key not in present and _section_evidence(text, m):
                present.add(key)
    return mentions, present, not_applicable


def _unread_pages(documents: List[DocumentArtifact]) -> int:
    """The same pages the partial / failed extraction gaps report: one number for the user."""
    return sum(len(set(d.failed_pages or [])) or ((d.page_count or 1) if d.status == "FAILED" else 0)
               for d in documents if not d.missing)


@dataclass
class Gap:
    gap_id: str
    kind: str  # missing-file | unsupported-type | failed-extraction | partial-extraction |
               # empty-ocr | referenced-form-absent | empty-analysis
    description: str
    evidence: List[str] = field(default_factory=list)
    note: str = ""  # coverage caveat, e.g. how many pages had no readable text


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

    def add(kind, desc, ev, note=""):
        nonlocal n
        n += 1
        gaps.append(Gap(gap_id=f"GAP-{n:03d}", kind=kind, description=desc, evidence=list(ev), note=note))

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
    # Referenced documents found neither as a file nor as a section of the text we could read.
    # Pages without readable text (scans without OCR, images) may still hold them, so the gap
    # says 'not found in the readable text' and carries how many pages that was.
    mentions, present, not_applicable = _referenced_documents(documents, sources)
    absent = sorted((display, ev) for key, (display, ev) in mentions.items()
                    if key not in present and key not in not_applicable)
    unread = _unread_pages(documents) if absent else 0
    note = f"{unread} page(s) of the package could not be read" if unread else ""
    for display, ev in absent:
        add("referenced-form-absent",
            f"{display} referenced but not found in the readable text of the package", ev[:3], note)
    if not documents:
        add("empty-analysis", "tender package contains no documents", [])
    return gaps


def gap_dicts(gaps: List[Gap]) -> List[Dict[str, Any]]:
    return [{"gap_id": g.gap_id, "kind": g.kind, "description": g.description,
             "evidence": g.evidence, **({"note": g.note} if g.note else {})} for g in gaps]
