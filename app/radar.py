"""Tender Radar — how well a discovered tender notice matches the account's capabilities.

Each factor is explained and only counted when both sides are known:
work type, voltage, country and time left. The match is the share of known factors met
(a close deadline counts half). No capabilities, or nothing known about the notice,
gives no percentage: INSUFFICIENT_DATA.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.tender_facts import classify_kind, max_kv

STRONG = 75


def _country_ok(country: str, allowed: List[str]) -> bool:
    c = (country or "").lower()
    return any(c.startswith(a.lower()) or a.lower().startswith(c.split(",")[0]) for a in allowed if a)


def match(item: Dict[str, Any], cap: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
    now = now or datetime.utcnow()
    text = f"{item.get('title') or ''} {item.get('description') or ''}"
    factors: List[Dict[str, Any]] = []

    def add(name, status, key, **vars_):
        factors.append({"factor": name, "status": status, "key": key, "vars": vars_})

    cap = cap or {}
    kind = classify_kind(text)
    if kind and cap.get("work_types"):
        ok = kind in cap["work_types"]
        add("work_type", "MET" if ok else "NOT_MET",
            "Work type {kind} is in your capabilities" if ok else "Work type {kind} is not in your capabilities", kind=kind)
    kv = max_kv(text)
    if kv and cap.get("max_kv"):
        ok = kv <= cap["max_kv"]
        add("voltage", "MET" if ok else "NOT_MET",
            "{kv} kV is within your {max} kV" if ok else "{kv} kV is above your {max} kV", kv=kv, max=cap["max_kv"])
    if item.get("country") and cap.get("countries"):
        ok = _country_ok(item["country"], cap["countries"])
        add("country", "MET" if ok else "NOT_MET",
            "You work in {country}" if ok else "{country} is not in your countries", country=item["country"])
    dl = item.get("deadline_at")
    if isinstance(dl, str):
        try:
            dl = datetime.fromisoformat(dl[:19])
        except ValueError:
            dl = None
    if dl:
        days = (dl - now).days
        if days < 0:
            add("deadline", "NOT_MET", "Closed on {date}", date=dl.date().isoformat())
        elif days < 14:
            add("deadline", "PARTIAL", "Only {days} day(s) left", days=days)
        else:
            add("deadline", "MET", "{days} days left to prepare", days=days)
    weights = {"MET": 1.0, "PARTIAL": 0.5, "NOT_MET": 0.0}
    known = [f for f in factors if not (f["factor"] == "deadline" and len(factors) == 1)]
    if not cap or not known:
        return {"match": None, "status": "INSUFFICIENT_DATA", "factors": factors}
    pct = round(100 * sum(weights[f["status"]] for f in known) / len(known))
    blocked = any(f["status"] == "NOT_MET" and f["factor"] in ("voltage", "work_type") for f in known)
    return {"match": pct, "status": "STRONG" if pct >= STRONG and not blocked else ("WEAK" if pct < 50 or blocked else "FAIR"),
            "factors": factors}


def summary(items: List[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, int]:
    now = now or datetime.utcnow()
    week = 0
    for i in items:
        dl = i.get("deadline_at")
        if dl:
            try:
                d = (datetime.fromisoformat(dl[:19]) - now).days
                week += 1 if 0 <= d <= 7 else 0
            except ValueError:
                pass
    return {"total": len(items), "strong": sum(1 for i in items if i.get("fit", {}).get("status") == "STRONG"),
            "closing_this_week": week}
