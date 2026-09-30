"""RFQ packages — split a processed tender into supplier/subcontractor RFQs the way the
tender engineer does it by hand: one RFQ per equipment package (e.g. "132kV GIS / CB",
"Power transformer", "13.8kV switchgear", "Protection, control & SAS", "Communication"),
each bundle holding the same folders:

    1. Project brief            generated from the tender (client, location, dates)
    2. Scope of work            the pages of the tender's SOW that belong to the package
    3. Design criteria          the package's design-requirement pages
    4. Drawings                 drawing pages about the package
    5. Data schedules (to be filled)   the material specs (TMSS / data schedules) the supplier fills

Every page is scored against package keywords after dropping the header / footer lines
that repeat on most pages of the document. The section heading in effect adds context to
the pages under it. Material-spec numbers (e.g. 32-TMSS-01) quoted on a package's scope
pages link the spec's own pages (its data schedule) to that package.
"""
from __future__ import annotations

import io
import re
import zipfile
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

# key, name template, discipline (for past-supplier suggestions), keyword pattern
PACKAGES: List[Tuple[str, str, str, str]] = [
    ("hv_switchgear", "{kv} GIS / circuit breakers", "Primary electrical (GIS / transformers)",
     r"\bgis\b|gas.insulated|circuit.breakers?|disconnectors?|earthing.switch|\bsf6\b|busbar|bus.duct"),
    ("power_transformer", "Power transformers", "Primary electrical (GIS / transformers)",
     r"power.transformers?|\bmva\b|on.load.tap|\boltc\b|tap.changer|transformer.losses|principal.tap|windings?\b|bushings?"),
    ("mv_switchgear", "{kv} switchgear", "Primary electrical (GIS / transformers)",
     r"metal.clad|metal.enclosed|air.insulated.switchgear|mv.switchgear|medium.voltage.switchgear|ring.main.unit|\brmu\b|vacuum.circuit|capacitor.banks?|"
     r"(?:6\.6|11|13\.8|22|33)\s?kv.switchgear"),
    ("protection_sas", "Protection, control & SAS", "Protection & control",
     r"protection|relays?\b|\bieds?\b|substation.automation|\bsas\b|bay.control|interlock|annunciat|fault.recorder|"
     r"metering|revenue.meters?|control.panels?"),
    ("communication", "Communication & SCADA", "SCADA & telecom",
     r"telecom|\bscada\b|\brtu\b|fib(?:er|re).optic|\bopgw\b|mpls|ethernet.switch|multiplexer|cyber|\bdvm\b|\bnms\b"),
    ("cables", "Power cables & accessories", "Cables",
     r"power.cables?|\bxlpe\b|cable.terminations?|cable.joints?|termination.kits?|link.box|sheath|cable.accessor"),
    ("aux_power", "AC/DC auxiliary power", "LV / DC & lighting",
     r"\bdc.system|batter(?:y|ies)|chargers?\b|\bups\b|ac/dc|auxiliary.(?:power|system)|station.service.transformer|"
     r"lv.switchboard|distribution.boards?|lighting|receptacles?|grounding|earthing.system"),
    ("civil", "Civil & structural works", "Civil & structural",
     r"civil|concrete|foundations?|excavation|fence|asphalt|drainage|steel.structures?|rebars?|reinforcement.bar|"
     r"pre.engineered|geotechnical|backfill|manholes?|septic"),
    ("hvac", "HVAC & plumbing", "HVAC",
     r"\bhvac\b|air.condition|ventilation|chillers?|ductwork|exhaust.fans?|plumbing|smoke.purge"),
    ("fire", "Fire detection & fire fighting", "Fire protection",
     r"fire.(?:alarm|fighting|protection|suppression|detection)|fm.?200|sprinkler|deluge"),
]
_RX = {k: re.compile(p, re.IGNORECASE) for k, _, _, p in PACKAGES}
_META = {k: (name, disc) for k, name, disc, _ in PACKAGES}

_SPEC = re.compile(r"\b(\d{2})\s?-\s?(TMSS|SDMS|TES|SES|SMSS|SCS)\s?-\s?(\d{2,3})\b", re.IGNORECASE)
# a data-schedule page carries the schedule as its heading, not a passing mention in the scope
_SCHEDULE = re.compile(r"^\s*(?:\d{1,2}(?:\.0)?\.?\s*)?(?:data\s?schedule|technical\s+data\s+sheet|"
                       r"guaranteed\s+(?:technical\s+)?(?:particulars|values))|\(to\s+be\s+filled", re.IGNORECASE | re.MULTILINE)
# bid forms, price schedules and local-content forms are the bidder's own paperwork, not a supplier's scope
_NON_TECH_DOC = re.compile(r"bid.?form|pric|sch(?:edule)?\.?\s?c\b|\bpa\b|local.content|\blc\b|scorecard|commercial|"
                           r"terms|conditions|guideline|invitation|\bitb\b|\bstc\b|bond|agreement|consortium", re.IGNORECASE)
_DESIGN = re.compile(r"design\s+(?:criteria|requirements|parameters|basis)", re.IGNORECASE)
_DRAWING_DOC = re.compile(r"draw|dwg|\bsld\b|single\s*line|layout|plan\b", re.IGNORECASE)
_DRAWING_PAGE = re.compile(r"\bscale\b|\bnts\b|all\s+dimensions\s+are\s+in|drawing\s+no\b|\bdwg\b|elevation|section\s+[a-z]-[a-z]",
                           re.IGNORECASE)
_BRIEF = re.compile(r"project\s+(?:brief\s+)?description|scope\s+of\s+the\s+project|project\s+overview", re.IGNORECASE)
_HEADING = re.compile(r"^\s*(\d{1,2}\.\d{1,2}|\d{1,2}\.0?|SECTION\s+\S+|APPENDIX\s+\S+|ANNEX(?:URE)?\s+\S+)\s*[.:-]?\s+"
                      r"([A-Z][A-Z0-9 ,&/()\-]{4,80})\s*$")
_KV = re.compile(r"(\d{1,3}(?:\.\d)?)\s?kv\b", re.IGNORECASE)
MIN_SCORE = 3
KINDS = ("scope", "design", "drawings", "schedules")
FOLDERS = {"brief": "1. Project Brief Description", "scope": "2. Scope of Work", "design": "3. Design Criteria",
           "drawings": "4. Drawings", "schedules": "5. Data Schedules (to be filled)"}


def _clean_pages(pages) -> List[str]:
    """Page texts without the lines that repeat on most pages (title blocks, headers, footers)."""
    if len(pages) < 4:
        return [p.text or "" for p in pages]
    count = Counter()
    for p in pages:
        count.update({ln.strip() for ln in (p.text or "").splitlines() if ln.strip()})
    common = {ln for ln, n in count.items() if n >= max(3, 0.3 * len(pages))}
    return ["\n".join(ln for ln in (p.text or "").splitlines() if ln.strip() and ln.strip() not in common)
            for p in pages]


def _spec_ids(text: str) -> List[str]:
    return sorted({f"{a}-{b.upper()}-{c}" for a, b, c in _SPEC.findall(text or "")})


def _scores(text: str, heading: str) -> Dict[str, int]:
    out = {}
    for k, rx in _RX.items():
        s = len(rx.findall(text)) + 4 * len(rx.findall(heading))
        if s:
            out[k] = s
    return out


def classify_pages(sources) -> List[Dict[str, Any]]:
    """One record per page: document, page, package (or None), kind, spec ids quoted, own spec id."""
    by_doc = defaultdict(list)
    for s in sources:
        by_doc[s.source_document].append(s)
    out = []
    for doc, pages in sorted(by_doc.items()):
        pages.sort(key=lambda s: s.page_number)
        texts = _clean_pages(pages)
        heading = ""
        drawing_doc = bool(_DRAWING_DOC.search(doc))
        if _NON_TECH_DOC.search(doc):
            continue
        sheet = doc.lower().endswith((".xls", ".xlsx", ".xlsm"))
        for p, text in zip(pages, texts):
            heads = [m.group(2) for ln in text.splitlines()[:60] if (m := _HEADING.match(ln))]
            if heads:
                heading = " ".join(heads[:3])
            sc = _scores(text[:8000], heading + " " + (doc if len(pages) <= 3 else ""))
            best = max(sc, key=sc.get) if sc else None
            pkg = best if best and sc[best] >= MIN_SCORE else None
            if sheet or _SCHEDULE.search(text):
                kind = "schedules"
            elif drawing_doc or (getattr(p, "ocr_applied", False) and _DRAWING_PAGE.search(text)):
                kind = "drawings"
            elif _DESIGN.search(heading):
                kind = "design"
            else:
                kind = "scope"
            ids = _spec_ids(text)
            head_ids = _spec_ids("\n".join(text.splitlines()[:12]) + "\n" + "\n".join((p.text or "").splitlines()[:40]))
            out.append({"document": doc, "page": p.page_number, "package": pkg, "scores": sc, "kind": kind,
                        "specs": ids, "own_spec": head_ids[0] if kind == "schedules" and len(head_ids) == 1 else None,
                        "brief": bool(_BRIEF.search(heading)), "text": text,
                        "head": "\n".join((p.text or "").splitlines()[:8])})
    return out


def _ranges(pages: List[int]) -> List[Tuple[int, int]]:
    out: List[List[int]] = []
    for n in sorted(set(pages)):
        if out and n <= out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return [(a, b) for a, b in out]


def _kv_label(texts: List[str], lo: float, hi: float) -> Optional[str]:
    vals = Counter()
    for t in texts:
        for v in _KV.findall(t):
            f = float(v)
            if lo <= f <= hi:
                vals[f] += 1
    if not vals:
        return None
    v = vals.most_common(1)[0][0]
    return f"{v:g}kV"


def build(sources) -> List[Dict[str, Any]]:
    """Packages found in the tender, largest first, each with its page ranges per folder."""
    pages = classify_pages(sources)
    # a material spec's own pages (its data schedule) belong to the package whose scope quotes it
    spec_votes: Dict[str, Counter] = defaultdict(Counter)
    for r in pages:
        if r["package"] and r["kind"] != "schedules":
            for sid in r["specs"]:
                spec_votes[sid][r["package"]] += 1
    spec_pages: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in pages:
        if r["own_spec"]:
            spec_pages[r["own_spec"]].append(r)
    groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    specs_of: Dict[str, set] = defaultdict(set)
    with_schedule: set = set()  # specs whose own data schedule is in the tender come first
    for sid, votes in spec_votes.items():
        if len(votes) < 5 and sid not in spec_pages:  # quoted by most packages = general requirements
            specs_of[votes.most_common(1)[0][0]].add(sid)
    for sid, rows in spec_pages.items():
        # the spec's own title ("METAL-ENCLOSED AIR INSULATED SWITCHGEAR 11 kV through 34.5 kV") decides first;
        # the scope pages that quote the spec decide when the title says nothing
        title = Counter()
        for r in rows[:6]:
            title.update(_scores("", r["head"]))
        votes = spec_votes.get(sid) or Counter(r["package"] for r in rows if r["package"])
        if title and max(title.values()) >= MIN_SCORE:
            pkg = title.most_common(1)[0][0]
        elif votes:
            pkg = votes.most_common(1)[0][0]
        else:
            continue
        specs_of[pkg].add(sid)
        with_schedule.add(sid)
        for r in rows:
            r["_taken"] = True
            groups[pkg]["schedules"].append(r)
    for r in pages:
        if r.get("_taken") or not r["package"]:
            continue
        groups[r["package"]][r["kind"]].append(r)
    brief = [r for r in pages if r["brief"]][:4]
    out = []
    for key, kinds in groups.items():
        n = sum(len(v) for v in kinds.values())
        if n < 2:
            continue
        name, disc = _META[key]
        # the voltage comes from the scope pages; a spec's data schedule covers a whole range ("69 kV through 380 kV")
        texts = ([r["text"] for k, v in kinds.items() if k != "schedules" for r in v]
                 or [r["text"] for v in kinds.values() for r in v])
        label = {"key": name, "vars": {}}
        if key == "hv_switchgear":
            label["vars"] = {"kv": _kv_label(texts, 66, 765) or "HV"}
        elif key == "mv_switchgear":
            label["vars"] = {"kv": _kv_label(texts, 3.3, 36) or "MV"}
        name = name.format(**label["vars"])
        parts = {}
        for kind in KINDS:
            rows = kinds.get(kind) or []
            by_doc = defaultdict(list)
            for r in rows:
                by_doc[r["document"]].append(r["page"])
            parts[kind] = [{"document": d, "ranges": [list(x) for x in _ranges(ps)], "pages": len(set(ps))}
                           for d, ps in sorted(by_doc.items())]
        out.append({"key": key, "name": name, "label": label, "discipline": disc, "pages": n,
                    "parts": parts, "specs": sorted(specs_of.get(key, set()), key=lambda x: (x not in with_schedule, x))[:40],
                    "brief": [{"document": r["document"], "page": r["page"]} for r in brief]})
    order = [k for k, *_ in PACKAGES]
    out.sort(key=lambda p: order.index(p["key"]))
    return out


_CACHE: Dict[str, Any] = {}


def tender_packages(tender_id: str) -> List[Dict[str, Any]]:
    """Memoised on the extraction cache state (same stamp as the RFP sections)."""
    from app.pipeline.checkpoint import cache_dir
    from app.sections import sources_from_cache
    d = cache_dir(tender_id)
    stamp = tuple(sorted((f.name, f.stat().st_mtime) for f in d.glob("extract-v*.json"))) if d.is_dir() else ()
    hit = _CACHE.get(tender_id)
    if hit and hit[0] == stamp:
        return hit[1]
    res = build(sources_from_cache(tender_id))
    if len(_CACHE) > 16:
        _CACHE.clear()
    _CACHE[tender_id] = (stamp, res)
    return res


def scope_text(pkg: Dict[str, Any]) -> str:
    """Short scope line stored on the RFQ record."""
    bits = []
    for kind in KINDS:
        for part in pkg["parts"].get(kind) or []:
            rng = ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in part["ranges"][:8])
            bits.append(f"{FOLDERS[kind].split('. ', 1)[1]}: {part['document']} p.{rng}")
    if pkg.get("specs"):
        bits.append("Specs: " + ", ".join(pkg["specs"][:15]))
    return "; ".join(bits)[:1000]


# ---- the downloadable bundle
def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip()[:90] or "file"


def _brief_docx(tender: Dict[str, Any], pkg: Dict[str, Any], dates: List[Dict[str, Any]], company: Dict[str, Any],
                closes_at: Optional[str]) -> bytes:
    from docx import Document
    d = Document()
    d.add_heading(f"Request for Quotation — {pkg['name']}", level=1)
    rows = [("Project", tender.get("title") or tender.get("id")), ("Tender reference", tender.get("id")),
            ("Client", tender.get("client")), ("Location", tender.get("location")),
            ("Package", pkg["name"]), ("Quotation due", closes_at or "To be confirmed")]
    for label, val in rows:
        if val:
            d.add_paragraph(f"{label}: {val}")
    if dates:
        d.add_heading("Key tender dates", level=2)
        for x in dates:
            d.add_paragraph(f"{x['label']}: {x.get('date') or x.get('raw')}", style="List Bullet")
    d.add_heading("What is in this package", level=2)
    for kind in KINDS:
        for part in pkg["parts"].get(kind) or []:
            rng = ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in part["ranges"])
            d.add_paragraph(f"{FOLDERS[kind]}: {part['document']}, pages {rng}", style="List Bullet")
    if pkg.get("specs"):
        d.add_heading("Material specifications to comply with / data schedules to fill", level=2)
        d.add_paragraph(", ".join(pkg["specs"]))
    d.add_heading("Please quote", level=2)
    for line in ("Price per item and lump sum, excluding VAT", "Delivery / completion time from award",
                 "Clause-by-clause compliance statement with every deviation listed",
                 "Filled data schedules, signed and stamped", "Type test reports and certificates",
                 "Payment terms and validity of the offer"):
        d.add_paragraph(line, style="List Bullet")
    if company.get("name"):
        d.add_heading("Send your quotation to", level=2)
        for v in (company.get("name"), company.get("contact_name"), company.get("email"), company.get("phone")):
            if v:
                d.add_paragraph(str(v))
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _cut_pdf(path: str, ranges: List[List[int]]) -> Optional[bytes]:
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        with fitz.open(path) as src:
            out = fitz.open()
            for a, b in ranges:
                a, b = max(1, a), min(b, src.page_count)
                if a <= b:
                    out.insert_pdf(src, from_page=a - 1, to_page=b - 1)
            if not out.page_count:
                return None
            data = out.tobytes(garbage=3, deflate=True)
            out.close()
            return data
    except Exception:
        return None


def build_zip(packages: List[Dict[str, Any]], files: Dict[str, str], tender: Dict[str, Any],
              dates: List[Dict[str, Any]], company: Dict[str, Any], closes_at: Optional[str] = None) -> bytes:
    """files: source document name -> stored path. PDF pages are cut out; other files are copied whole."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i, pkg in enumerate(packages, 1):
            root = f"{i:02d}- {_safe(pkg['name'])}/"
            z.writestr(root + FOLDERS["brief"] + "/Project brief and RFQ.docx",
                       _brief_docx(tender, pkg, dates, company, closes_at))
            brief_pages = defaultdict(list)
            for b in pkg.get("brief") or []:
                brief_pages[b["document"]].append(b["page"])
            for doc, ps in brief_pages.items():
                path = files.get(doc)
                if path and path.lower().endswith(".pdf"):
                    data = _cut_pdf(path, [list(r) for r in _ranges(ps)])
                    if data:
                        z.writestr(root + FOLDERS["brief"] + f"/Pages from {_safe(doc.rsplit('.', 1)[0])}.pdf", data)
            for kind in KINDS:
                for part in pkg["parts"].get(kind) or []:
                    path = files.get(part["document"])
                    if not path:
                        continue
                    folder = root + FOLDERS[kind] + "/"
                    if path.lower().endswith(".pdf"):
                        data = _cut_pdf(path, part["ranges"])
                        if data:
                            z.writestr(folder + f"Pages from {_safe(part['document'].rsplit('.', 1)[0])}.pdf", data)
                    else:
                        try:
                            z.write(path, folder + _safe(part["document"]))
                        except OSError:
                            continue
    return buf.getvalue()
