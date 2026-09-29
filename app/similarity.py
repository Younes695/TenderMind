"""Stage 8 — similar past tenders and client history, from the account's own tenders only.

Similarity (0-100) = 40 requirement-text cosine (TF-IDF over requirement summaries)
                   + 25 same client + 20 same type of work + 10 voltage within ±40% + 5 same country.
Every match lists its reasons, its latest recommendation and its outcome. Nothing leaves the account.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional

_STOP = set("the a an and or of to in for on with by at from as is are be shall must will this that these those "
            "such all any each its his their it which per not no than other into under over within".split())
WEIGHTS = {"text": 40, "client": 25, "work_type": 20, "voltage": 10, "country": 5}


def _terms(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9]{2,}", (text or "").lower()) if w not in _STOP]


_PROFILES: Dict[tuple, Dict[str, Any]] = {}


def profile(db, tender) -> Dict[str, Any]:
    """What the comparison needs about one tender; memoised on everything it depends on."""
    from app.models import Decision, TenderAnalysis
    a_row = (db.query(TenderAnalysis.id).filter(TenderAnalysis.tender_id == tender.id)
             .order_by(TenderAnalysis.created_at.desc()).first())
    d_row = (db.query(Decision.id, Decision.decision).filter(Decision.tender_id == tender.id)
             .order_by(Decision.timestamp.desc()).first())
    key = (tender.id, a_row[0] if a_row else None, tender.client, tender.title, tender.outcome,
           d_row[1] if d_row else None)
    if key not in _PROFILES:
        if len(_PROFILES) > 500:
            _PROFILES.clear()
        _PROFILES[key] = _profile(db, tender)
    return _PROFILES[key]


def _profile(db, tender) -> Dict[str, Any]:
    from app.models import Decision, TenderAnalysis
    from app.tender_facts import classify_kind, detect_country, main_kv, normalise_client
    a = (db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender.id)
         .order_by(TenderAnalysis.created_at.desc()).first())
    reqs = (a.requirements if a else None) or []
    body = " ".join(str(r.get("summary") or "") for r in reqs[:1500])
    client = tender.client or (a.tender or {}).get("client") if a and isinstance(a.tender, dict) else tender.client
    if not client:
        try:  # detected once from the page texts, cached on the analysis-less path
            from app.sections import sources_from_cache
            from app.tender_facts import detect_client
            client = detect_client(sources_from_cache(tender.id))[0]
        except Exception:
            client = None
    if client:
        from app.tender_facts import KNOWN_CLIENTS
        canon = normalise_client(client)
        client = canon if canon in KNOWN_CLIENTS else client  # "SEC" and "Saudi Electricity Company" read the same
    dec = (db.query(Decision).filter(Decision.tender_id == tender.id).order_by(Decision.timestamp.desc()).first())
    return {"id": tender.id, "title": tender.title, "client": client, "client_key": normalise_client(client) if client else None,
            "work_type": classify_kind(tender.title or "") or classify_kind(body),
            "kv": main_kv(tender.title or "", body), "country": detect_country([tender.title or "", body]),
            "terms": Counter(_terms(body)), "analysed": bool(reqs),
            "decision": dec.decision if dec else None, "outcome": tender.outcome,
            "created_at": tender.created_at.isoformat() if tender.created_at else None}


def _cosine(a: Counter, b: Counter, idf: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[t] * b[t] * idf.get(t, 1.0) ** 2 for t in a.keys() & b.keys())
    na = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in a.items()))
    nb = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in b.items()))
    return dot / (na * nb) if na and nb else 0.0


def rank(target: Dict[str, Any], others: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    docs = [target] + others
    df = Counter(t for d in docs for t in d["terms"].keys())
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
    out = []
    for o in others:
        reasons, score = [], 0.0
        cos = _cosine(target["terms"], o["terms"], idf)
        if cos > 0.05:
            score += WEIGHTS["text"] * cos
            reasons.append({"key": "Requirements {p}% alike", "vars": {"p": round(100 * cos)}})
        if target["client_key"] and target["client_key"] == o["client_key"]:
            score += WEIGHTS["client"]
            reasons.append({"key": "Same client: {client}", "vars": {"client": o["client"]}})
        if target["work_type"] and target["work_type"] == o["work_type"]:
            score += WEIGHTS["work_type"]
            reasons.append({"key": "Same type of work: {kind}", "vars": {"kind": o["work_type"]}})
        if target["kv"] and o["kv"] and 0.6 * target["kv"] <= o["kv"] <= 1.4 * target["kv"]:
            score += WEIGHTS["voltage"]
            reasons.append({"key": "Similar voltage: {kv} kV", "vars": {"kv": o["kv"]}})
        if target["country"] and target["country"] == o["country"]:
            score += WEIGHTS["country"]
            reasons.append({"key": "Same country: {country}", "vars": {"country": o["country"]}})
        if score >= 20:
            out.append({"id": o["id"], "title": o["title"], "client": o["client"], "score": round(score),
                        "reasons": reasons, "decision": o["decision"], "outcome": o["outcome"],
                        "created_at": o["created_at"]})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]


def for_tender(db, tender, user) -> Dict[str, Any]:
    from app.access import owner_filter
    from app.models import Tender
    from app.access import DEMO_TENDER_ID
    q = db.query(Tender).filter(Tender.id != tender.id, Tender.id != DEMO_TENDER_ID)
    f = owner_filter(Tender.owner_email, user)
    if f is not None:
        q = q.filter(f)
    target = profile(db, tender)
    others = [profile(db, t) for t in q.all()]
    same_client = [{"id": o["id"], "title": o["title"], "decision": o["decision"], "outcome": o["outcome"],
                    "created_at": o["created_at"]}
                   for o in others if target["client_key"] and o["client_key"] == target["client_key"]]
    return {"client": target["client"], "similar": rank(target, [o for o in others if o["analysed"] or o["client_key"]]),
            "client_history": same_client}


def client_history(db, tender):
    """Earlier tenders of the same owner account with the same client (for the notification)."""
    from app.access import DEMO_TENDER_ID
    from app.models import Tender
    target = profile(db, tender)
    if not target["client_key"]:
        return [], None
    q = db.query(Tender).filter(Tender.id != tender.id, Tender.id != DEMO_TENDER_ID)
    q = q.filter(Tender.owner_email == tender.owner_email) if tender.owner_email else q.filter(Tender.owner_email.is_(None))
    out = []
    for t in q.all():
        o = profile(db, t)
        if o["client_key"] == target["client_key"]:
            out.append({"id": o["id"], "title": o["title"], "decision": o["decision"], "outcome": o["outcome"]})
    return out, target["client"]
