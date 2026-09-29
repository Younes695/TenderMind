"""Stage 7 — certificates and approvals the tender demands, and from whom.

First section of the decision pack (user request): before spending effort on a tender the team
must see whether it holds the certificates and approvals required — or needs a partner or
supplier that does (e.g. a foreign contractor or an approved manufacturer).

Each demand is read from the tender's own words with file, page and quote, and assigned to:
  bidder   — the company must hold it: compared with Settings -> capabilities (HELD / MISSING / CHECK)
  partner  — a manufacturer / supplier / subcontractor must hold it: "needs a partner that holds it"
  unclear  — the sentence does not say who: CHECK
Deterministic; nothing is inferred beyond the sentence.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.eligibility import _COMPANY, _THIRD_PARTY, _sentence

# management-system certificates (not test standards such as ISO 12944 paint tests)
_ISO = re.compile(r"\b(?:ISO|OHSAS)\s*[-:]?\s*(9001|14001|45001|18001|27001|50001|17025)\b", re.IGNORECASE)
_CERT_CONTEXT = re.compile(r"certif|accredit|registered|quality (management )?system|management system", re.IGNORECASE)
_PREQUAL = re.compile(r"\bpre-?qualif(?:ied|ication)\b", re.IGNORECASE)
_APPROVED_LIST = re.compile(r"\bapproved\s+(?:list\s+of\s+)?(manufacturers?|vendors?|suppliers?|sub-?contractors?)\b|"
                            r"\bvendor list\b|\bprequalified list of manufacturers\b", re.IGNORECASE)
_TYPE_TEST = re.compile(r"\btype\W{0,3}(?:\(design\)\s*)?test(?:ed)?\s+(certificates?|reports?)\b|\b(KEMA|CESI)\b",
                        re.IGNORECASE)
_COMPETENCY = re.compile(r"\bcertificates?\s+of\s+competency\b|\bcertified\s+(?:terminator|jointer|welder|splicer|"
                         r"operator|electrician)s?\b", re.IGNORECASE)
_PRODUCT = re.compile(r"\bSASO\s+certifi\w*|\bSABER\b", re.IGNORECASE)
_LOCAL_CONTENT = re.compile(r"\blocal content certificate\b", re.IGNORECASE)
_CLASSIFICATION = re.compile(r"\bcontractors?\W{0,2}\s*classification\b|\bclassification\s+(grade|certificate)\b",
                             re.IGNORECASE)
_SUBCONTRACT_RULE = re.compile(r"not\s+pre-?qualified.{0,120}\bsub-?contract", re.IGNORECASE)
_OPTIONAL = re.compile(r"\(if any\)|\bif applicable\b|\boptional\b", re.IGNORECASE)
_SCAN_PAGES = 1600
PARTNER_DISCIPLINE = "Primary electrical (GIS / transformers)"

NAMES = {
    "prequal": "Prequalification (invited / approved bidders)",
    "prequal_partner": "Pre-qualified subcontractor for the parts you are not pre-qualified in",
    "approved_list": "Approved / prequalified manufacturers and vendors",
    "type_test": "Type-test certificates (KEMA / CESI / IEC) of the equipment",
    "competency": "Certificates of competency for staff (welders, jointers, operators)",
    "product": "Product certificates of the equipment (SASO / SABER)",
    "local_content": "Local content certificates of suppliers",
    "classification": "Contractor classification certificate",
}


def _demands_in(text: str):
    """(name, kind, start, end) for every demand on one page."""
    for m in _ISO.finditer(text):
        if _CERT_CONTEXT.search(_sentence(text, m.start(), m.end())):
            yield (("OHSAS " if m.group(0).upper().startswith("OHSAS") else "ISO ") + m.group(1), "iso", m.start(), m.end())
    for m in _PREQUAL.finditer(text):
        sent = _sentence(text, m.start(), m.end())
        if _SUBCONTRACT_RULE.search(sent):
            yield (NAMES["prequal_partner"], "prequal_partner", m.start(), m.end())
        elif _THIRD_PARTY.search(sent):  # "list of pre-qualified manufacturers"
            yield (NAMES["approved_list"], "approved_list", m.start(), m.end())
        else:
            yield (NAMES["prequal"], "prequal", m.start(), m.end())
    for kind, rx in (("approved_list", _APPROVED_LIST), ("type_test", _TYPE_TEST), ("competency", _COMPETENCY),
                     ("product", _PRODUCT), ("local_content", _LOCAL_CONTENT),
                     ("classification", _CLASSIFICATION)):
        for m in rx.finditer(text):
            yield (NAMES[kind], kind, m.start(), m.end())


_PARTNER_KINDS = {"prequal_partner", "approved_list", "type_test", "product", "local_content"}


def _who(sentence: str, kind: str) -> str:
    if kind in _PARTNER_KINDS:
        return "partner"
    if kind == "competency":
        return "staff"
    if _THIRD_PARTY.search(sentence):
        return "partner"
    if _COMPANY.search(sentence):
        return "bidder"
    return "unclear"


def _held(name: str, kind: str, cap: Optional[Dict[str, Any]]) -> Optional[bool]:
    """True/False against the capability profile; None when the profile says nothing."""
    certs = [c.lower() for c in (cap or {}).get("certifications") or []]
    regs = [r.lower() for r in (cap or {}).get("registrations") or []]
    if kind == "iso":
        if not certs:
            return None
        num = name.split()[-1]
        return any(num in c for c in certs)
    if kind in ("prequal", "classification"):
        if not regs:
            return None
        keys = ("classification",) if kind == "classification" else ("prequal", "approved", "vendor list", "invited")
        return any(k in r for r in regs for k in keys)
    return None


def find(sources, cap: Optional[Dict[str, Any]] = None, suppliers: Optional[Dict[str, list]] = None
         ) -> List[Dict[str, Any]]:
    """Every certificate / approval demanded, grouped by (name, who), strongest first."""
    from app.sections import discipline_of
    groups: Dict[tuple, Dict[str, Any]] = {}
    for s in list(sources)[:_SCAN_PAGES]:
        text = s.text or ""
        for name, kind, a, b in _demands_in(text):
            sent = " ".join(_sentence(text, a, b).split())
            who = _who(sent, kind)
            g = groups.setdefault((name, who), {"name": name, "kind": kind, "who": who, "evidence": [],
                                                 "disciplines": set()})
            if len(g["evidence"]) < 3:
                g["evidence"].append({"file": s.source_document, "page": s.page_number, "quote": sent[:300]})
            g["optional"] = g.get("optional", True) and bool(_OPTIONAL.search(sent))
            if who == "partner":
                g["disciplines"].add(PARTNER_DISCIPLINE if kind in ("type_test", "approved_list") else discipline_of(sent))
    out = []
    for g in groups.values():
        disc = sorted(g.pop("disciplines"))
        if g["who"] == "partner":
            g["status"] = "PARTNER_NEEDED"
            g["disciplines"] = disc
            g["suggested"] = [x for d in disc for x in (suppliers or {}).get(d, [])][:5]
        elif g["who"] == "staff":
            g["status"] = "CHECK"  # the team must field certified people
        else:
            held = _held(g["name"], g["kind"], cap)
            g["status"] = "CHECK" if held is None or g["who"] == "unclear" else ("HELD" if held else "MISSING")
        out.append(g)
    order = {"MISSING": 0, "PARTNER_NEEDED": 1, "CHECK": 2, "HELD": 3}
    out.sort(key=lambda g: (order[g["status"]], g["name"]))
    return out


def summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    c = {k: sum(1 for i in items if i["status"] == k) for k in ("MISSING", "PARTNER_NEEDED", "CHECK", "HELD")}
    c["needs_partner"] = c["PARTNER_NEEDED"] > 0 or c["MISSING"] > 0
    return c


_CACHE: Dict[str, Any] = {}


def tender_certifications(tender_id: str, cap: Optional[Dict[str, Any]], suppliers: Optional[Dict[str, list]]):
    """Memoised on the extraction cache + the inputs (profile, suppliers) — the pack loads fast."""
    import json
    from app.pipeline.checkpoint import cache_dir
    from app.sections import sources_from_cache
    d = cache_dir(tender_id)
    stamp = (tuple(sorted((f.name, f.stat().st_mtime) for f in d.glob("extract-v*.json"))) if d.is_dir() else (),
             json.dumps([cap, suppliers], sort_keys=True, default=str))
    hit = _CACHE.get(tender_id)
    if hit and hit[0] == stamp:
        return hit[1]
    res = find(sources_from_cache(tender_id), cap, suppliers) if stamp[0] else []
    _CACHE[tender_id] = (stamp, res)
    return res
