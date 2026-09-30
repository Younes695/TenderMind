"""Stage 8 — quick summary of a tender: what it is, the key facts, and what the team must do next.

Built only from data the system already holds (analysis, eligibility, certificates, contradictions,
checklist, review items, votes). Facts from the tender carry file + page. Action lines are templates
with vars so the UI shows them in English or Arabic.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

_DATE = r"(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]{3,9},?\s+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"
_SUBMISSION = re.compile(rf"\b(?:bid|tender|proposal|offer)s?\s+(?:closing|submission|due|opening)\s+date\b[^.\n]{{0,40}}?{_DATE}|"
                         rf"\b(?:closing|submission)\s+date\s*(?:of|for)?\s*(?:bids?|tenders?|proposals?)?\s*[:\-]?\s*{_DATE}",
                         re.IGNORECASE)


_NUM_DATE = r"(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{4}-\d{2}-\d{2})"
KEY_DATES = [
    ("Submission deadline", re.compile(r"(?:bids?|proposals?|offers?)\s+(?:must|shall)\s+be\s+submitted[\s\S]{0,120}?\bdate\s*:?\s*"
                                       + _NUM_DATE, re.IGNORECASE)),
    ("Submission deadline", _SUBMISSION),
    ("Pre-bid / job explanation meeting", re.compile(r"(?:job\s+explanation\s+meeting|pre-?bid\s+(?:meeting|conference)|site\s+visit)"
                                                     r"[\s\S]{0,160}?\bdate\s*:?\s*" + _NUM_DATE, re.IGNORECASE)),
]


def to_iso(raw: str) -> Optional[str]:
    """Day-first numeric dates (dd.mm.yyyy) as used in the region; ISO dates as they are."""
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
                "%B %d %Y", "%d %B, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def key_dates(sources) -> List[Dict[str, Any]]:
    out, seen = [], set()
    for s in list(sources)[:200]:
        for label, rx in KEY_DATES:
            if label in seen:
                continue
            m = rx.search(s.text or "")
            if m:
                raw = next(g for g in m.groups() if g)
                out.append({"label": label, "raw": raw, "date": to_iso(raw), "file": s.source_document,
                            "page": s.page_number, "quote": " ".join(m.group(0).split())[:200]})
                seen.add(label)
    return out


def suggested_deadline(sources) -> Optional[Dict[str, Any]]:
    return next((d for d in key_dates(sources) if d["label"] == "Submission deadline"), None)


def _action(key: str, **vars_) -> Dict[str, Any]:
    return {"key": key, "vars": vars_, "text": key.format(**vars_)}


def build(db, tender, user) -> Dict[str, Any]:
    from app.certifications import summary as cert_summary, tender_certifications
    from app.conflicts import tender_conflicts
    from app.eligibility import capability_dict, capability_for, score as elig_score
    from app.models import DepartmentVote, EligibilityResult, EvidenceMatch, Requirement, TenderAnalysis, TenderIssue
    from app.sections import sources_from_cache
    from app.tender_facts import classify_kind, detect_client, detect_country, main_kv

    a = (db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender.id)
         .order_by(TenderAnalysis.created_at.desc()).first())
    reqs = (a.requirements if a else None) or []
    try:
        sources = sources_from_cache(tender.id)
    except Exception:
        sources = []
    body = " ".join(r.get("summary") or "" for r in reqs[:1500])
    client, client_ev = detect_client(sources, tender.client or "")
    cap = capability_dict(capability_for(db, tender))
    el = db.query(EligibilityResult).filter(EligibilityResult.tender_id == tender.id).first()
    try:
        certs = tender_certifications(tender.id, cap, {})
    except Exception:
        certs = []
    cs = cert_summary(certs)
    try:
        conflicts = tender_conflicts(tender.id)
    except Exception:
        conflicts = []
    cats = Counter((r.get("category") or "UNKNOWN") for r in reqs)
    mandatory = (db.query(Requirement).filter(Requirement.tender_id == tender.id, Requirement.mandatory.is_(True)).count()
                 or sum(1 for r in reqs if r.get("mandatory")))
    evaluated = bool(db.query(EvidenceMatch).join(Requirement, EvidenceMatch.requirement_id == Requirement.id)
                     .filter(Requirement.tender_id == tender.id).first())
    open_q = db.query(TenderIssue).filter(TenderIssue.tender_id == tender.id, TenderIssue.status == "OPEN",
                                          TenderIssue.category == "question",
                                          TenderIssue.kind.notin_(("unclassified-requirement",))).count()
    votes = db.query(DepartmentVote).filter(DepartmentVote.tender_id == tender.id).count()
    try:
        from app.api.routes import _checklist_items
        checklist = _checklist_items(db, tender.id)
    except Exception:
        checklist = []
    todo = sum(1 for i in checklist if i.get("status") == "TODO")
    dates = []
    if tender.submission_deadline:
        dates.append({"label": "Submission deadline", "date": tender.submission_deadline.date().isoformat(), "set_by_team": True})
    for d in (a.deadlines if a else None) or []:
        if d.get("date"):
            dates.append({"label": d.get("type") or "date", "date": d["date"], "source": d.get("source")})
    found = key_dates(sources)
    for d in found:
        if not (d["label"] == "Submission deadline" and tender.submission_deadline):
            dates.append({"label": d["label"], "date": d["date"] or d["raw"], "source": {"file": d["file"], "page": d["page"],
                                                                                         "quote": d["quote"]}})
    suggestion = None if tender.submission_deadline else next((d for d in found if d["label"] == "Submission deadline"), None)
    risks = [r.get("description") or r.get("summary") for r in ((a.risks if a else None) or [])]
    risks = [r for r in risks if r][:3]

    actions: List[Dict[str, Any]] = []
    if not cap or not any(cap.values()):
        actions.append(_action("Fill company capabilities in Settings so every new tender is checked first."))
    if el is not None and el.status == "INELIGIBLE" and not el.override_by:
        actions.append(_action("Review why the tender does not fit — or continue anyway with a reason."))
    partner = [c["name"] for c in certs if c["status"] == "PARTNER_NEEDED"]
    missing = [c["name"] for c in certs if c["status"] == "MISSING"]
    if missing:
        actions.append(_action("Get or confirm these certificates: {items}.", items=", ".join(missing)))
    if partner:
        actions.append(_action("Line up a partner or supplier for: {items}.", items=", ".join(partner)))
    if reqs and not evaluated:
        actions.append(_action("Upload company documents and run Evaluate to measure the company match."))
    if conflicts:
        actions.append(_action("Ask the tender owner which value applies for {n} contradiction(s).", n=len(conflicts)))
    if open_q:
        actions.append(_action("Send {n} clarification question(s) to the tender owner — the email draft is ready.", n=open_q))
    if todo:
        actions.append(_action("Prepare {n} submission item(s) on the checklist.", n=todo))
    if not tender.submission_deadline:
        actions.append(_action("Set the submission deadline so reminders work."))
    if reqs and not votes:
        actions.append(_action("Collect department votes for the Go/No-Go decision."))

    return {
        "tender": {"id": tender.id, "title": tender.title, "stage": tender.stage,
                   "submission_deadline": tender.submission_deadline.date().isoformat() if tender.submission_deadline else None,
                   "outcome": tender.outcome},
        "client": {"name": client, "evidence": client_ev, "entered": bool((tender.client or "").strip())},
        "facts": {"work_type": classify_kind(tender.title or "") or classify_kind(body),
                  "voltage_kv": main_kv(tender.title or "", body), "country": detect_country([tender.title or "", body]),
                  "documents": len((a.documents if a else None) or []),
                  "pages": sum(int(d.get("page_count") or 0) for d in ((a.documents if a else None) or [])),
                  "requirements": len(reqs), "mandatory": mandatory,
                  "by_category": dict(cats.most_common(6))},
        "eligibility": {"status": el.status if el else None, "overridden": bool(el and el.override_by),
                        "score": elig_score(el.checks) if el else None},
        "certificates": cs,
        "contradictions": len(conflicts),
        "dates": dates,
        "suggested_deadline": suggestion,
        "risks": risks,
        "actions": actions,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
