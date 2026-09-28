"""Stage 5J — expected contract value from comparable awarded contracts.

Source: World Bank "Contract Award" procurement notices (official, public). Each
award notice states the signed contract price; we keep power-sector awards in
USD with their voltage (kV) and type (substation / transmission line /
transformer / distribution). For a tender we pick awards of the same type and a
similar voltage and report the median and the 25-75% range, with the list of
contracts used. Fewer than 3 comparables -> no estimate (never a guess).
Caveat shown to users: these are World Bank-financed projects; scope and
country conditions differ, so the range is a sanity check, not a price.
"""
from __future__ import annotations

import datetime as dt
import re
import statistics
import uuid
from typing import Any, Dict, List, Optional

import requests

from app.news import WB_API, WB_NOTICE_URL, TIMEOUT, _clean, _parse_date

QUERIES = ("substation", "transmission line", "power transformer", "switchgear", "distribution network")
_PRICE = re.compile(r"(?:Signed\s+Contract\s+Price|Contract\s+Price|Contract\s+Amount)[^0-9A-Za-z]{0,40}"
                    r"(?:USD|US\$|\$)\s?([\d,]+(?:\.\d+)?)", re.IGNORECASE)
_KV = re.compile(r"(\d{2,3})(?:/\d{1,3}){0,3}\s?kV", re.IGNORECASE)
MIN_COMPARABLES = 3


def classify_kind(text: str) -> Optional[str]:
    t = (text or "").lower()
    if "substation" in t or " gis" in t or "switchyard" in t or "محطة" in t:
        return "substation"
    if "transmission line" in t or "overhead line" in t or "ohtl" in t or "interconnect" in t:
        return "transmission line"
    if "transformer" in t:
        return "transformer"
    if "distribution" in t or "switchgear" in t or "feeder" in t:
        return "distribution"
    return None


def max_kv(text: str) -> Optional[int]:
    vals = [int(v) for v in _KV.findall(text or "") if 1 <= int(v) <= 800]
    return max(vals) if vals else None


def fetch_awards(rows: int = 100, session=None) -> List[Dict[str, Any]]:
    http = session or requests
    out, seen = [], set()
    for q in QUERIES:
        try:
            r = http.get(WB_API, timeout=TIMEOUT, params={
                "format": "json", "rows": rows, "srt": "noticedate", "order": "desc", "qterm": q,
                "notice_type_exact": "Contract Award",
                "fl": "id,bid_description,project_name,project_ctry_name,noticedate,notice_text"})
            r.raise_for_status()
            got = (r.json() or {}).get("procnotices") or []
        except Exception:
            continue
        for n in (got.values() if isinstance(got, dict) else got):
            nid = str(n.get("id") or "")
            if not nid or nid in seen:
                continue
            seen.add(nid)
            text = _clean(n.get("notice_text"), 20000)
            m = _PRICE.search(text)
            title = _clean(n.get("bid_description") or n.get("project_name"), 500)
            kind = classify_kind(title)
            if not m or not kind:
                continue
            amount = float(m.group(1).replace(",", ""))
            if amount < 10_000:
                continue  # not a works/supply contract price
            out.append({"external_id": nid, "title": title, "country": n.get("project_ctry_name"),
                        "kind": kind, "kv": max_kv(title), "amount_usd": amount,
                        "awarded_at": _parse_date(n.get("noticedate")), "url": WB_NOTICE_URL.format(id=nid)})
    return out


def store_awards(db, items: List[Dict[str, Any]]) -> int:
    from app.models import MarketAward
    added = 0
    for it in items:
        if db.query(MarketAward).filter(MarketAward.external_id == it["external_id"]).first():
            continue
        db.add(MarketAward(id=f"MA-{uuid.uuid4().hex[:10].upper()}", fetched_at=dt.datetime.utcnow(), **it))
        added += 1
    db.commit()
    return added


def refresh_awards() -> Dict[str, int]:
    from app.database import SessionLocal
    items = fetch_awards()
    db = SessionLocal()
    try:
        return {"fetched": len(items), "added": store_awards(db, items)}
    finally:
        db.close()


_EPC = re.compile(r"design|construction|construct|turnkey|lstk|epc|installation|install|erection|civil works|"
                  r"rehabilitation|upgrade|extension|complet", re.IGNORECASE)


def scope_of(text: str) -> str:
    """'epc' (design/build/install) or 'supply' (equipment only) — prices differ ~10x."""
    return "epc" if _EPC.search(text or "") else "supply"


def main_kv(title: str, body: str = "") -> Optional[int]:
    """The tender's own voltage: from its title when stated, otherwise the most
    frequent kV in the requirements (the maximum picked up stray 500 kV mentions)."""
    if max_kv(title):
        return max_kv(title)
    vals = [int(v) for v in _KV.findall(body or "") if 1 <= int(v) <= 800]
    return max(set(vals), key=vals.count) if vals else None


def estimate(db, text: str, title: str = "") -> Dict[str, Any]:
    """Estimate from awards of the same kind and a similar voltage."""
    from app.models import MarketAward
    kind = classify_kind(title) or classify_kind(text)
    kv = main_kv(title, text)
    if not kind:
        return {"available": False, "reason": "Tender type not recognised (substation, line, transformer, distribution)."}
    q = db.query(MarketAward).filter(MarketAward.kind == kind)
    rows = q.all()
    scope = scope_of(f"{title} {text[:5000]}")
    same_scope = [r for r in rows if scope_of(r.title) == scope]
    mixed_scope = len(same_scope) < MIN_COMPARABLES
    rows = rows if mixed_scope else same_scope
    if kv:
        close = [r for r in rows if r.kv and 0.6 * kv <= r.kv <= 1.6 * kv]
        rows = close if len(close) >= MIN_COMPARABLES else rows
    amounts = sorted(r.amount_usd for r in rows)
    if len(amounts) < MIN_COMPARABLES:
        return {"available": False, "kind": kind, "kv": kv, "comparables": len(amounts),
                "reason": "Not enough comparable awarded contracts yet."}
    qs = statistics.quantiles(amounts, n=4)
    rows.sort(key=lambda r: abs((r.kv or kv or 0) - (kv or 0)))
    return {"available": True, "kind": kind, "kv": kv, "scope": scope, "mixed_scope": mixed_scope,
            "currency": "USD", "comparables": len(amounts),
            "median": round(statistics.median(amounts)), "low": round(qs[0]), "high": round(qs[2]),
            "examples": [{"title": r.title, "country": r.country, "kv": r.kv, "amount_usd": round(r.amount_usd),
                          "awarded_at": r.awarded_at.date().isoformat() if r.awarded_at else None, "url": r.url}
                         for r in rows[:8]],
            "caveat": "Based on World Bank-financed contracts; scope and country conditions differ — use as a sanity check."}
