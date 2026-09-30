"""Stage 9 — portfolio pages: decision board, approvals, work packages, document library, analytics.

All built from data the system already holds, per account. Heavy per-tender inputs (page texts,
sections, certificates) are memoised elsewhere on the extraction cache, so a board load stays cheap
after the first visit.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List

CLOSED = {"SUBMITTED", "CLOSED"}


def _votes(db, tender_id):
    from app.models import DepartmentVote
    from app.team import vote_summary
    return vote_summary([{"department": v.department, "vote": v.vote}
                         for v in db.query(DepartmentVote).filter(DepartmentVote.tender_id == tender_id).all()])


def board(db, user, tenders) -> List[Dict[str, Any]]:
    from app.api.routes import _LAST_SCORE, _cached_score
    from app.certifications import summary as cert_summary, tender_certifications
    from app.eligibility import capability_dict, capability_for, score as elig_score
    from app.models import EligibilityResult, TenderAnalysis
    from app.scoring import tender_score
    from app.similarity import profile
    analysed = {tid for (tid,) in db.query(TenderAnalysis.tender_id).distinct().all()}
    rows = []
    for t in tenders:
        sc = _cached_score(db, t.id)
        if sc is None and t.id in analysed:
            try:
                # The board must not say GO where the decision says NO_BID or REVIEW.
                from app.engines.decision import contradiction_waived, latest_decision
                dec = latest_decision(db, t.id)
                sc = tender_score(db, t, user, None, int((dec.hard_fail_count if dec else 0) or 0),
                                  0 if (dec is None or contradiction_waived(dec)) else int(dec.contradicted_count or 0))
                _LAST_SCORE[t.id] = (dec.id if dec else None, sc)
            except Exception:
                db.rollback()
        el = db.query(EligibilityResult).filter(EligibilityResult.tender_id == t.id).first()
        try:
            certs = cert_summary(tender_certifications(t.id, capability_dict(capability_for(db, t)), {})) if t.id in analysed else None
        except Exception:
            certs = None
        v = _votes(db, t.id)["overall"]
        rows.append({"id": t.id, "title": t.title, "client": profile(db, t)["client"], "stage": t.stage,
                     "deadline": t.submission_deadline.date().isoformat() if t.submission_deadline else None,
                     "outcome": t.outcome, "analysed": t.id in analysed,
                     "score": (sc or {}).get("score"), "band": (sc or {}).get("band"),
                     "eligibility": el.status if el else None, "overridden": bool(el and el.override_by),
                     "eligibility_percent": (elig_score(el.checks) or {}).get("percent") if el else None,
                     "needs_partner": bool(certs and certs.get("needs_partner")),
                     "votes": v, "final_decision": t.final_decision})
    return rows


def approvals(db, tenders) -> Dict[str, Any]:
    waiting, decided = [], []
    for t in tenders:
        v = _votes(db, t.id)
        row = {"id": t.id, "title": t.title, "stage": t.stage, "votes": v,
               "deadline": t.submission_deadline.date().isoformat() if t.submission_deadline else None,
               "final_decision": t.final_decision, "final_reason": t.final_reason, "final_by": t.final_by,
               "final_at": t.final_at.isoformat() if t.final_at else None}
        (decided if t.final_decision else waiting).append(row)
    waiting.sort(key=lambda r: r["deadline"] or "9999")
    decided.sort(key=lambda r: r["final_at"] or "", reverse=True)
    return {"waiting": waiting, "decided": decided}


def work_packages(db, user, tenders) -> List[Dict[str, Any]]:
    from app.api.routes import _account_tender_ids
    from app.models import Rfq
    from app.sections import NON_TECHNICAL_DISCIPLINES, suppliers_by_discipline, tender_sections, discipline_of
    others = _account_tender_ids(db, user)
    out = []
    for t in tenders:
        try:
            secs = tender_sections(t.id)
        except Exception:
            secs = []
        if not secs:
            continue
        sup = suppliers_by_discipline(db, [x for x in others if x != t.id])
        rfqs = db.query(Rfq).filter(Rfq.tender_id == t.id).all()
        by = defaultdict(lambda: {"sections": 0, "pages": 0})
        for s in secs:
            if s["discipline"] in NON_TECHNICAL_DISCIPLINES:
                continue
            d = by[s["discipline"]]
            d["sections"] += 1
            d["pages"] += s["page_to"] - s["page_from"] + 1
        packages = []
        for disc, d in sorted(by.items(), key=lambda kv: -kv[1]["pages"]):
            mine = [r for r in rfqs if discipline_of(f"{r.discipline or ''} {r.package_name or ''}", r.scope or "") == disc]
            packages.append({"discipline": disc, **d, "suppliers": sup.get(disc, [])[:3],
                             "rfqs": [{"id": r.id, "reference": r.reference, "status": r.status} for r in mine]})
        out.append({"id": t.id, "title": t.title, "packages": packages})
    return out


def documents(db, user, tenders, q: str = "", limit: int = 60) -> Dict[str, Any]:
    from app.models import CompanyDocument, TenderDocument
    from app.access import owner_filter
    from app.sections import sources_from_cache
    files = []
    for t in tenders:
        for d in db.query(TenderDocument).filter(TenderDocument.tender_id == t.id).all():
            files.append({"kind": "tender", "tender_id": t.id, "tender_title": t.title,
                          "name": getattr(d, "original_filename", None) or getattr(d, "filename", None) or d.id,
                          "size": getattr(d, "file_size", None)})
    cq = db.query(CompanyDocument)
    f = owner_filter(CompanyDocument.owner_email, user)
    if f is not None:
        cq = cq.filter(f)
    for d in cq.all():
        files.append({"kind": "company", "tender_id": None, "name": d.title or d.id, "type": d.document_type})
    hits = []
    words = [w for w in re.findall(r"[\wء-ي]{3,}", (q or "").lower())]
    if words:
        for t in tenders:
            try:
                pages = sources_from_cache(t.id)
            except Exception:
                pages = []
            for p in pages:
                low = (p.text or "").lower()
                if all(w in low for w in words):
                    i = low.find(words[0])
                    hits.append({"tender_id": t.id, "file": p.source_document, "page": p.page_number,
                                 "snippet": " ".join((p.text or "")[max(0, i - 120): i + 220].split())})
                    if len(hits) >= limit:
                        break
            if len(hits) >= limit:
                break
    return {"files": files, "hits": hits, "query": q}


def analytics(db, user, tenders) -> Dict[str, Any]:
    from app.models import TenderAnalysis
    from app.similarity import profile
    analysed = {tid for (tid,) in db.query(TenderAnalysis.tender_id).distinct().all()}
    outcomes = Counter(t.outcome for t in tenders if t.outcome)
    decided = outcomes.get("WON", 0) + outcomes.get("LOST", 0)
    stages = Counter(t.stage or ("ANALYSED" if t.id in analysed else "NEW") for t in tenders)
    finals = Counter(t.final_decision for t in tenders if t.final_decision)
    by_month = Counter(t.created_at.strftime("%Y-%m") for t in tenders if t.created_at)
    clients, kinds = Counter(), Counter()
    per_client_won = Counter()
    for t in tenders:
        p = profile(db, t)
        if p["client"]:
            clients[p["client"]] += 1
            if t.outcome == "WON":
                per_client_won[p["client"]] += 1
        if p["work_type"]:
            kinds[p["work_type"]] += 1
    return {"total": len(tenders), "analysed": len(analysed & {t.id for t in tenders}),
            "outcomes": dict(outcomes), "win_rate": round(100 * outcomes.get("WON", 0) / decided) if decided else None,
            "stages": dict(stages), "final_decisions": dict(finals),
            "by_month": dict(sorted(by_month.items())[-12:]),
            "top_clients": [{"client": c, "tenders": n, "won": per_client_won[c]} for c, n in clients.most_common(8)],
            "work_types": dict(kinds.most_common())}
