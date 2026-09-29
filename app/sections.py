"""Stage 6 — split the RFP into its parts (with page ranges) and suggest past
suppliers / subcontractors for each part.

Sections come from the document's own headings (SECTION / PART / SCHEDULE /
APPENDIX / ANNEX / EXHIBIT and numbered upper-case titles); table-of-contents
lines are ignored. Each section gets a discipline by keyword weight. Suppliers
are the account's own history: every contractor who quoted on a past RFQ of the
same discipline, ranked by times selected, then average technical fit.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

# Keyword in any case, then a real identifier (number, Roman numeral or one capital
# letter, optionally quoted) — "SECTION NO. DESCRIPTION" table headers and
# "Section modulus" are not headings.
_HEAD = re.compile(r"^\s*((?i:SECTION|PART|CHAPTER|SCHEDULE|APPENDIX|ANNEX(?:URE)?|EXHIBIT|ATTACHMENT)\b"
                   r"\s*[-\u2013]?\s*(?:(?i:NO)\.?\s*)?[\"\u201c\u2018']?(?:\d{1,3}(?:\.\d{1,2})?|[IVXL]{1,6}|[A-Z])[\"\u201d\u2019']?"
                   r"(?![\-\u2013][A-Z]\b)(?=[\s:.,\-\u2013\u2014]|$).{0,90})$")
_NUM_HEAD = re.compile(r"^\s*(\d{1,2})(?:\.0)?\.?\s+([A-Z][A-Z0-9 &/,()\-]{5,70})\s*$")
_NOTE = re.compile(r"\b(shall|must|will|should|is|are|be|refer|provided|see)\b", re.IGNORECASE)
_TOC = re.compile(r"(\.{3,}|\t|\s{3,})\s*[A-Z]?-?\d{1,4}\s*$")
MAX_SECTIONS_PER_DOC = 40

# Specific disciplines first: on a tie the more specific one wins.
DISCIPLINES = {
    "HVAC": r"hvac|air.condition|ventilation|chiller",
    "Fire protection": r"fire (alarm|fighting|protection|suppression|detection)",
    "SCADA & telecom": r"scada|telecom|\brtu\b|fib(er|re)|communication|opgw",
    "Protection & control": r"protection|relay|control panel|interlock|\bscheme",
    "Cables": r"\bcables?\b|termination|cable joint|trench",
    "LV / DC & lighting": r"lighting|\blv\b|dc system|batter(y|ies)|charger|\bups\b",
    "Quality": r"quality|inspection and test|\bitp\b",
    "HSE": r"safety|health|environment",
    "Commercial": r"pric(e|ing)|payment|bond|guarantee|invoice|local content",
    "Legal / contract terms": r"terms and conditions|general conditions|liabilit|termination of|arbitration|indemn",
    "Primary electrical (GIS / transformers)": r"switchgear|\bgis\b|transformer|busbar|circuit breaker|disconnector|\d+\s?kv",
    "Civil & structural": r"civil|concrete|foundation|building|excavation|steel structure|fence|road|drainage|gatehouse",
}
NON_TECHNICAL_DISCIPLINES = {"Commercial", "Legal / contract terms", "HSE", "Quality", "General"}
_DISC_RX = {k: re.compile(v, re.IGNORECASE) for k, v in DISCIPLINES.items()}


def discipline_of(title: str, body: str = "") -> str:
    best, score = "General", 0
    for name, rx in _DISC_RX.items():
        s = 5 * len(rx.findall(title or "")) + len(rx.findall((body or "")[:6000]))
        if s > score:
            best, score = name, s
    return best


def _headings(text: str, numbered: bool = True):
    for line in (text or "").splitlines()[:80]:
        if len(line) > 120 or _TOC.search(line):
            continue
        m = _HEAD.match(line)
        if m:
            yield " ".join(m.group(1).split())
            continue
        n = _NUM_HEAD.match(line) if numbered else None
        # a numbered heading is a short title, not a drawing note ("3. CONTRACTOR SHALL REFER TO ...")
        if (n and int(n.group(1)) <= 30 and sum(ch.isalpha() for ch in n.group(2)) >= 5 and len(n.group(2).split()) <= 8
                and not _NOTE.search(n.group(2))):
            yield f"{n.group(1)}. {' '.join(n.group(2).split()).title()}\u200b"  # marker: level-1 numbered


def split_sections(sources) -> List[Dict[str, Any]]:
    """sources: SourceText-like objects (source_document, page_number, text)."""
    by_doc = defaultdict(list)
    for s in sources:
        by_doc[s.source_document].append(s)
    out = []
    for doc, pages in sorted(by_doc.items()):
        pages.sort(key=lambda s: s.page_number)
        secs: List[Dict[str, Any]] = []
        seen = set()
        for p in pages:
            # numbered titles on scanned (OCR) pages are drawing notes / labels, not document parts
            for h in _headings(p.text, numbered=not getattr(p, "ocr_applied", False)):
                key = " ".join(h.lower().replace(",", " ").split()[:2]) if _HEAD.match(h) else h.lower()
                if key in seen:
                    continue
                seen.add(key)
                if secs and secs[-1]["page_from"] == p.page_number and not secs[-1]["_body"]:
                    secs[-1]["_more"] = secs[-1].get("_more", 0) + 1  # more headings on the same page
                    continue
                secs.append({"document": doc, "title": h.rstrip("\u200b")[:160], "page_from": p.page_number,
                             "_body": "", "_level1": h.endswith("\u200b")})
            if secs:
                secs[-1]["_body"] += (p.text or "")[:3000] if len(secs[-1]["_body"]) < 6000 else ""
        # a numbered title that repeats with other numbers ("6. Data Schedule", "7. Data Schedule")
        # is a table header, not a part of the document
        rep = defaultdict(int)
        for x in secs:
            if x.get("_level1"):
                rep[x["title"].split(". ", 1)[-1].lower()] += 1
        secs = [x for x in secs if not (x.get("_level1") and rep[x["title"].split(". ", 1)[-1].lower()] > 1)]
        if not secs:
            secs = [{"document": doc, "title": doc.rsplit(".", 1)[0], "page_from": pages[0].page_number,
                     "_body": " ".join((p.text or "")[:1500] for p in pages[:4])}]
        elif secs[0]["page_from"] > pages[0].page_number:
            secs.insert(0, {"document": doc, "title": "Front matter", "page_from": pages[0].page_number,
                            "_body": pages[0].text or ""})
        if len(secs) > MAX_SECTIONS_PER_DOC:  # keep the top-level parts only
            # keep the parts (SECTION/APPENDIX...) and level-1 numbered headings, then parts only
            top = [secs[0]] + [s for s in secs[1:] if _HEAD.match(s["title"]) or s.get("_level1")]
            if len(top) > MAX_SECTIONS_PER_DOC:
                top = [secs[0]] + [s for s in secs[1:] if _HEAD.match(s["title"])]
            secs = top[:MAX_SECTIONS_PER_DOC]
        if len(pages) == 1 and len(secs) == 1:  # a one-page file (Word/Excel): its name says more
            secs[0]["title"], secs[0]["_more"] = doc.rsplit(".", 1)[0], 0
        last = pages[-1].page_number
        for i, s in enumerate(secs):
            s["page_to"] = (secs[i + 1]["page_from"] - 1) if i + 1 < len(secs) else last
            s["page_to"] = max(s["page_to"], s["page_from"])
            s["discipline"] = discipline_of(s["title"], s.pop("_body"))
            more = s.pop("_more", 0)
            if more:
                s["title"] = f"{s['title']} (+{more})"
            s.pop("_level1", None)
        out.extend(secs)
    return out


_SRC: Dict[str, Any] = {}


def sources_from_cache(tender_id: str):
    """Page texts saved by the extraction checkpoint, parsed once per cache state."""
    from app.pipeline.checkpoint import cache_dir
    d = cache_dir(tender_id)
    stamp = tuple(sorted((f.name, f.stat().st_mtime) for f in d.glob("extract-v*.json"))) if d.is_dir() else ()
    hit = _SRC.get(tender_id)
    if hit and hit[0] == stamp:
        return hit[1]
    res = _read_sources(tender_id)
    if len(_SRC) > 16:
        _SRC.clear()
    _SRC[tender_id] = (stamp, res)
    return res


def _read_sources(tender_id: str):
    from app.pipeline.checkpoint import cache_dir
    from app.pipeline.two_stage_runner import adapt_doc_results
    d = cache_dir(tender_id)
    doc_results: Dict[str, Any] = {}
    if d.is_dir():
        for f in sorted(d.glob("extract-v*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for e in data.get("entries") or []:
                    doc_results[e["name"]] = e["result"]
            except Exception:
                continue
    return adapt_doc_results(doc_results)[0] if doc_results else []


def _norm(name: str) -> str:
    return " ".join((name or "").split()).strip()


def suppliers_by_discipline(db, tender_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Contractors that quoted on RFQs of the given (the account's) tenders."""
    from app.models import Quotation, Rfq
    if not tender_ids:
        return {}
    agg: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    rows = (db.query(Quotation, Rfq).join(Rfq, Quotation.rfq_id == Rfq.id)
            .filter(Rfq.tender_id.in_(tender_ids)).all())
    for q, rfq in rows:
        disc = discipline_of(f"{rfq.discipline or ''} {rfq.package_name or ''}", rfq.scope or "")
        name = _norm(q.contractor)
        if not name:
            continue
        a = agg[disc].setdefault(name.lower(), {"contractor": name, "quotes": 0, "selected": 0, "_fit": [],
                                                "tenders": set()})
        a["quotes"] += 1
        a["selected"] += 1 if q.selected else 0
        a["_fit"].append(float(q.technical_fit or 0))
        a["tenders"].add(rfq.tender_id)
    out = {}
    for disc, items in agg.items():
        lst = []
        for a in items.values():
            fits = a.pop("_fit")
            a["avg_fit"] = round(sum(fits) / len(fits), 1) if fits else None
            a["tenders"] = sorted(a["tenders"])
            lst.append(a)
        lst.sort(key=lambda a: (-a["selected"], -(a["avg_fit"] or 0), -a["quotes"], a["contractor"].lower()))
        out[disc] = lst[:5]
    return out


_CACHE: Dict[str, Any] = {}


def tender_sections(tender_id: str) -> List[Dict[str, Any]]:
    """Sections for a processed tender; memoised on the cache folder's state."""
    from app.pipeline.checkpoint import cache_dir
    d = cache_dir(tender_id)
    stamp = (tuple(sorted((f.name, f.stat().st_mtime) for f in d.glob("extract-v*.json"))) if d.is_dir() else ())
    hit: Optional[tuple] = _CACHE.get(tender_id)
    if hit and hit[0] == stamp:
        return hit[1]
    secs = split_sections(sources_from_cache(tender_id))
    _CACHE[tender_id] = (stamp, secs)
    return secs
