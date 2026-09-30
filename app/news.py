"""Stage 5H — tender news from official / trusted sources.

Sources
- World Bank procurement notices API (official, public JSON): Egypt, the GCC and
  the wider MENA region. Only notice data is kept — no personal contact names,
  emails or phone numbers.
- Optional RSS/Atom feeds listed in TENDERMIND_NEWS_FEEDS (comma-separated
  https URLs). Only hosts in TENDERMIND_NEWS_ALLOWED_HOSTS may be fetched.

Not used: Etimad and EBRD eCEPP refuse automated access (robots.txt denied /
HTTP 403), so they are not scraped.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import threading
import time
import uuid
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests

WB_API = "https://search.worldbank.org/api/v2/procnotices"
WB_NOTICE_URL = "https://projects.worldbank.org/en/projects-operations/procurement-detail/{id}"
# Target market: Egypt and the GCC only (ISO codes as the API expects).
COUNTRIES = ["EG", "SA", "AE", "OM", "KW", "BH", "QA"]
COUNTRY_NAMES = {"Egypt", "Egypt, Arab Republic of", "Saudi Arabia", "United Arab Emirates", "Oman", "Kuwait", "Bahrain", "Qatar"}
# Sources: World Bank notices (Egypt; the Bank rarely finances GCC projects) and the public tender
# table of Bahrain's Electricity & Water Authority, Oman Tender Board new tenders, and Qatar's
# Monaqasat available tenders (robots.txt of all three permits it; fetched once per 6-hour refresh).
RELEVANT = re.compile(  # electricity sector only (generation, transmission, distribution)
    r"substation|transformer|transmission line|transmission|switchgear|gis|kv|overhead line|"
    r"underground cable|power cable|electric|electrical|electricity|power plant|power station|power supply|"
    r"grid|interconnect|distribution network|metering|scada|solar|photovoltaic|pv|wind farm|"
    r"battery energy|bess|محطة محولات|محول|كهرب|خطوط نقل|جهد", re.IGNORECASE)
OPEN_NOTICE_TYPES = ("Invitation for Bids", "Request for Expression of Interest",
                     "General Procurement Notice", "Invitation for Prequalification")
TIMEOUT = 20
MAX_BYTES = 2 * 1024 * 1024
MIN_REFRESH_GAP_S = 15 * 60

_state = {"last_refresh": 0.0, "last_result": None}
_lock = threading.Lock()


def _parse_date(value: Optional[str], day_first: bool = False) -> Optional[dt.datetime]:
    if not value:
        return None
    if day_first:
        try:
            return dt.datetime.strptime(value.strip(), "%d-%m-%Y")
        except ValueError:
            pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%d-%b-%Y", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            d = dt.datetime.strptime(value.strip(), fmt)
            return d.replace(tzinfo=None)
        except ValueError:
            continue
    return None


def _clean(text: Optional[str], limit: int = 2000) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", t).strip()[:limit]


def fetch_world_bank(countries: Iterable[str] = COUNTRIES, rows: int = 40,
                     session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    http = session or requests
    out = []
    fields = ("id,notice_type,noticedate,submission_deadline_date,project_ctry_name,project_name,"
              "bid_description,procurement_method_name,contact_organization")
    for code in countries:
        notices = []
        # Only notices a contractor can still act on — contract awards were two
        # thirds of the feed and crowded out the open tenders.
        for ntype in OPEN_NOTICE_TYPES:
            try:
                r = http.get(WB_API, timeout=TIMEOUT, params={
                    "format": "json", "rows": rows, "srt": "noticedate", "order": "desc",
                    "project_ctry_code": code, "notice_type_exact": ntype, "fl": fields})
                r.raise_for_status()
                got = (r.json() or {}).get("procnotices") or []
            except Exception:
                continue  # one country / type failing must not stop the others
            notices.extend(got.values() if isinstance(got, dict) else got)
        seen = set()
        for n in notices:
            nid = str(n.get("id") or "").strip()
            title = _clean(n.get("bid_description") or n.get("project_name"), 500)
            if not nid or not title or nid in seen:
                continue
            seen.add(nid)
            desc = _clean(" · ".join(x for x in (n.get("project_name"), n.get("procurement_method_name")) if x))
            out.append({"source": "World Bank", "external_id": nid, "title": title, "description": desc,
                        "country": n.get("project_ctry_name"), "notice_type": n.get("notice_type"),
                        "organization": _clean(n.get("contact_organization"), 300) or None,
                        "url": WB_NOTICE_URL.format(id=nid),
                        "published_at": _parse_date(n.get("noticedate")),
                        "deadline_at": _parse_date(n.get("submission_deadline_date"))})
    return out


EWA_URL = "https://www.ewa.bh/en/tenders"


def fetch_ewa(session=None, html_text: Optional[str] = None) -> List[Dict[str, Any]]:
    """Bahrain Electricity & Water Authority: the public "Published Domestic Tenders" table.
    robots.txt allows all agents; fetched at most once per refresh (every 6 h)."""
    import html as _html
    if html_text is None:
        http = session or requests
        try:
            r = http.get(EWA_URL, timeout=TIMEOUT, headers={"User-Agent": "TenderMind/1.0 (+tender news)"})
            r.raise_for_status()
            html_text = r.text[:MAX_BYTES]
        except Exception:
            return []
    i = html_text.find("Published Domestic Tenders")
    j = html_text.find("Tender Opening Results", i)
    seg = html_text[i:j if j > i else i + 60000] if i >= 0 else ""
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S):
        cells = [" ".join(_html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) < 6 or cells[1].lower() == "title":
            continue
        ref, title, desc, directorate, published, closing = cells[:6]
        ref = ref if ref and ref != "-" else None
        out.append({"source": "EWA Bahrain", "external_id": (ref or title)[:200], "title": title[:500],
                    "description": _clean(f"{desc} · {directorate}"), "country": "Bahrain", "notice_type": "Tender",
                    "organization": "Electricity & Water Authority (Bahrain)", "url": EWA_URL,
                    "published_at": _parse_date(published.replace(" ", "").replace("/", "-")[:10], day_first=True),
                    "deadline_at": _parse_date(closing.replace(" ", "").replace("/", "-")[:10], day_first=True)})
    return out


OMAN_URL = "https://etendering.tenderboard.gov.om/product/publicDash?viewFlag=NewTenders"
QATAR_URL = "https://monaqasat.mof.gov.qa/TendersOnlineServices/AvailableMinistriesTenders/{page}"
_UA = {"User-Agent": "TenderMind/1.0 (+tender news)"}


_LEGACY_TLS_HOSTS = {"monaqasat.mof.gov.qa"}  # server only offers ciphers below OpenSSL's default level


def _get(url: str, session=None) -> Optional[str]:
    if session is None and urlparse(url).hostname in _LEGACY_TLS_HOSTS:
        import ssl
        import urllib.request
        ctx = ssl.create_default_context()      # certificate and host name are still verified
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), context=ctx, timeout=40) as r:
                return r.read(MAX_BYTES).decode("utf-8", "ignore")
        except Exception:
            return None
    http = session or requests
    try:
        r = http.get(url, timeout=40, headers=_UA)
        r.raise_for_status()
        return r.text[:MAX_BYTES]
    except Exception:
        return None


def _cells(row_html: str) -> List[str]:
    import html as _html
    return [" ".join(_html.unescape(re.sub(r"<[^>]+>", " ", c)).split())
            for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S)]


def fetch_oman(session=None, html_text: Optional[str] = None) -> List[Dict[str, Any]]:
    """Oman Tender Board public "New Tenders" list (robots.txt does not restrict it)."""
    html_text = html_text if html_text is not None else _get(OMAN_URL, session)
    if not html_text:
        return []
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html_text, re.S):
        c = _cells(row)
        if len(c) < 7 or not re.match(r"^\d+\.$", c[0]):
            continue
        closing = re.search(r"Bid Closing Date:\s*(\d{2}-\d{2}-\d{4})", c[6])
        out.append({"source": "Oman Tender Board", "external_id": c[1][:200], "title": c[2].rstrip(". ")[:500],
                    "description": _clean(f"{c[3]} · {c[4]} · {c[5]}"), "country": "Oman", "notice_type": "Tender",
                    "organization": c[3][:300] or None, "url": OMAN_URL, "published_at": None,
                    "deadline_at": _parse_date(closing.group(1), day_first=True) if closing else None})
    return out


def fetch_qatar(session=None, pages: int = 3, html_pages: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Qatar Ministry of Finance "Monaqasat" available tenders (robots.txt allows all)."""
    import html as _html
    texts = html_pages if html_pages is not None else [t for t in (_get(QATAR_URL.format(page=i), session)
                                                                    for i in range(1, pages + 1)) if t]
    out, seen = [], set()
    for page in texts:
        t = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
        lines = [ln.strip() for ln in _html.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n") if ln.strip()]
        for i, ln in enumerate(lines):
            if not re.fullmatch(r"\d{2,6}/20\d\d", ln) or ln in seen or i + 1 >= len(lines):
                continue
            seen.add(ln)
            block = lines[i + 1:i + 30]

            def after(label):
                for k, x in enumerate(block):
                    if x.startswith(label) and k + 1 < len(block):
                        return block[k + 1]
                return None
            out.append({"source": "Qatar Monaqasat", "external_id": ln, "title": block[0][:500],
                        "description": _clean(" · ".join(x for x in (after("الجهة"), after("النوع"),
                                                                        after("نوع القطاع المطلوب")) if x)),
                        "country": "Qatar", "notice_type": after("النوع") or "Tender",
                        "organization": (after("الجهة") or "")[:300] or None,
                        "url": QATAR_URL.format(page=1),
                        "published_at": _parse_date((after("تاريخ الطرح") or "").replace("/", "-"), day_first=True),
                        "deadline_at": _parse_date((after("تاريخ الإغلاق") or "").replace("/", "-"), day_first=True)})
    return out


def _allowed_hosts() -> set:
    return {h.strip().lower() for h in os.environ.get("TENDERMIND_NEWS_ALLOWED_HOSTS", "").split(",") if h.strip()}


def fetch_rss(urls: Iterable[str], session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    import xml.etree.ElementTree as ET
    http = session or requests
    allowed = _allowed_hosts()
    out = []
    for url in urls:
        u = urlparse(url)
        if u.scheme != "https" or (u.hostname or "").lower() not in allowed:
            continue  # only explicitly trusted https hosts
        try:
            r = http.get(url, timeout=TIMEOUT, stream=True)
            r.raise_for_status()
            body = r.raw.read(MAX_BYTES + 1, decode_content=True)
            if len(body) > MAX_BYTES or b"<!ENTITY" in body[:4096]:
                continue  # oversized or entity-declaring feed: refuse
            root = ET.fromstring(body)
        except Exception:
            continue
        host = u.hostname
        for item in root.iter():
            tag = item.tag.split("}")[-1]
            if tag not in ("item", "entry"):
                continue
            get = lambda name: next((c for c in item if c.tag.split("}")[-1] == name), None)
            t, link, d, pub = get("title"), get("link"), get("description") or get("summary"), get("pubDate") or get("updated") or get("published")
            href = (link.get("href") if link is not None and link.get("href") else (link.text if link is not None else None))
            title = _clean(t.text if t is not None else "", 500)
            if not title:
                continue
            ext = (href or title)[:500]
            out.append({"source": host, "external_id": ext, "title": title,
                        "description": _clean(d.text if d is not None else ""), "country": None,
                        "notice_type": None, "organization": host, "url": href,
                        "published_at": _parse_date(pub.text if pub is not None else None), "deadline_at": None})
    return out


def store(db, items: List[Dict[str, Any]]) -> Dict[str, int]:
    from app.models import NewsItem
    added = updated = 0
    for it in items:
        row = db.query(NewsItem).filter(NewsItem.source == it["source"],
                                        NewsItem.external_id == it["external_id"]).first()
        relevant = bool(RELEVANT.search(f"{it['title']} {it.get('description') or ''}"))
        if row is None:
            db.add(NewsItem(id=f"NEWS-{uuid.uuid4().hex[:12].upper()}", relevant=relevant,
                            fetched_at=dt.datetime.utcnow(), **it))
            added += 1
        else:
            for k in ("title", "description", "notice_type", "deadline_at", "url", "organization"):
                setattr(row, k, it.get(k))
            row.relevant = relevant
            updated += 1
    db.commit()
    return {"added": added, "updated": updated}


def refresh(force: bool = False) -> Dict[str, Any]:
    """Fetch every source and store new notices. At most once per 15 minutes."""
    with _lock:
        now = time.time()
        if not force and now - _state["last_refresh"] < MIN_REFRESH_GAP_S and _state["last_result"]:
            return {**_state["last_result"], "skipped": True}
        from app.database import SessionLocal
        items = fetch_world_bank() + fetch_ewa() + fetch_oman() + fetch_qatar()
        feeds = [f.strip() for f in os.environ.get("TENDERMIND_NEWS_FEEDS", "").split(",") if f.strip()]
        items += fetch_rss(feeds)
        db = SessionLocal()
        try:
            res = store(db, items)
        except Exception:
            db.rollback()
            res = {"added": 0, "updated": 0, "error": "store failed"}
        finally:
            db.close()
        result = {**res, "fetched": len(items), "at": dt.datetime.utcnow().isoformat() + "Z"}
        _state.update(last_refresh=now, last_result=result)
        return result


def last_refresh() -> Optional[Dict[str, Any]]:
    return _state["last_result"]


def start_refresher(interval_s: int = 6 * 3600, first_delay_s: int = 30) -> None:
    def _loop():
        time.sleep(first_delay_s)
        while True:
            try:
                refresh(force=True)
            except Exception:
                pass
            time.sleep(interval_s)
    threading.Thread(target=_loop, name="news-refresher", daemon=True).start()
