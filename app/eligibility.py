"""Stage 6 — eligibility gate: does this tender fit the company at all?

Runs right after text extraction and before any AI call, so an unsuitable
tender costs seconds, not hours. Deterministic: every check compares one fact
found in the tender text with the company's capability profile and returns
PASS / FAIL / UNCLEAR with the page it came from. Only a clear FAIL blocks;
a fact the text does not state is UNCLEAR, never FAIL. An empty profile skips
the gate (with a note) — it never blocks. A manager can override a block.
"""
from __future__ import annotations

import datetime as dt
import os
import re
from typing import Any, Dict, Iterable, List, Optional

from app.tender_facts import classify_kind, detect_country, main_kv

_ISO = re.compile(r"\bISO\s*[-:]?\s*(9001|14001|45001|18001|27001|50001)\b", re.IGNORECASE)
_DEMAND = re.compile(r"\b(bidder|tenderer|contractor|applicant|supplier)s?\b.{0,120}\b(shall|must|required|"
                     r"certified|certificate|accredited)\b|\b(shall|must)\b.{0,80}\b(certified|certificate)\b",
                     re.IGNORECASE)
_REG = re.compile(r"\b(pre-?qualifi\w+|approved (vendor|contractor|supplier)s?|vendor list|"
                  r"contractor classification|classification (grade|category|certificate)|"
                  r"registered (with|in) (the )?[A-Z][\w ]{2,40})", re.IGNORECASE)
_YEARS = re.compile(r"\b(minimum|at least|not less than|min\.?)\s*(of\s*)?\(?(\d{1,2})\)?\s*(\(\w+\)\s*)?years?\b"
                    r".{0,60}\b(experience|in the field|in similar|in business)", re.IGNORECASE)
_TURNOVER = re.compile(r"\b(turnover|annual revenue|revenues?)\b.{0,100}?\b(not less than|minimum|at least|exceed\w*|"
                       r"min\.?)\b.{0,20}?\b(SAR|SR|USD|US\$|EGP|AED|QAR|KWD|OMR|EUR)?\s?([\d][\d,.]*)\s*"
                       r"(million|mn|m|billion|bn)?\b", re.IGNORECASE)
_CUR = {"SR": "SAR", "US$": "USD"}
# Who a sentence is about. A demand on the bidder/company can block; one on staff,
# manufacturers or sub-suppliers is not about the company and must not.
_COMPANY = re.compile(r"\b(bidder|tenderer|applicant|company|firm|contractor(?!\s+of)|in business)\b", re.IGNORECASE)
_PERSONNEL = re.compile(r"\b(manager|engineer|personnel|staff|supervisor|foreman|specialist|expert|operator|"
                        r"technician|inspector|superintendent|coordinator|officer|key person)", re.IGNORECASE)
_THIRD_PARTY = re.compile(r"\b(supplier|manufacturer|vendor|sub-?contractor|fabricator|factory|laborator)", re.IGNORECASE)


def _sentence(text: str, start: int, end: int) -> str:
    a = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    b_dot, b_nl = text.find(".", end), text.find("\n", end)
    b = min(x for x in (b_dot, b_nl, len(text)) if x >= 0)
    return text[a:b]
_SCAN_PAGES = 400  # qualification terms sit in the ITB/instructions, not in 1,500 pages of drawings


def capability_for(db, tender):
    """Capabilities are stored per account like the company profile: the tender
    owner's, else (tenders from before accounts) the admin's, else "local"."""
    from app.models import CompanyCapability
    # An owned tender is judged by its owner's capabilities only: falling back to
    # the admin's would check it against another company and echo that company's
    # profile back in the check details.
    keys = ((tender.owner_email,) if tender.owner_email
            else (os.environ.get("TENDERMIND_AUTH_EMAIL", "").strip().lower(), "local"))
    for key in keys:
        if key:
            cap = db.query(CompanyCapability).filter(CompanyCapability.id == key).first()
            if cap is not None:
                return cap
    return None


def capability_dict(cap) -> Optional[Dict[str, Any]]:
    if cap is None:
        return None
    return {"work_types": list(cap.work_types or []), "max_kv": cap.max_kv, "countries": list(cap.countries or []),
            "registrations": list(cap.registrations or []), "certifications": list(cap.certifications or []),
            "years_experience": cap.years_experience, "annual_turnover": cap.annual_turnover,
            "turnover_currency": cap.turnover_currency}


def _empty(cap: Optional[Dict[str, Any]]) -> bool:
    return not cap or not any(v for v in cap.values())


def _evidence(sources, pattern) -> Optional[Dict[str, Any]]:
    rx = pattern if hasattr(pattern, "search") else re.compile(re.escape(str(pattern)), re.IGNORECASE)
    for s in sources:
        m = rx.search(s.text or "")
        if m:
            a, b = max(0, m.start() - 100), min(len(s.text), m.end() + 140)
            return {"file": s.source_document, "page": s.page_number, "quote": " ".join(s.text[a:b].split())}
    return None


def _money(num: str, unit: Optional[str]) -> Optional[float]:
    try:
        v = float(num.replace(",", ""))
    except ValueError:
        return None
    u = (unit or "").lower()
    return v * (1e9 if u in ("billion", "bn") else 1e6 if u in ("million", "mn", "m") else 1)


def check(cap: Optional[Dict[str, Any]], title: str, sources: List[Any]) -> Dict[str, Any]:
    if _empty(cap):
        return {"status": "SKIPPED", "checks": [], "note": "Company capabilities are empty — fill them in Settings "
                                                           "to check each new tender before the full analysis."}
    sources = list(sources)[:_SCAN_PAGES]
    body = "\n".join(s.text or "" for s in sources)
    checks: List[Dict[str, Any]] = []

    def add(key, label, result, detail, evidence=None, **vars_):
        """detail is an English template; vars fill it (the UI translates the template)."""
        checks.append({"key": key, "label": label, "result": result, "detail": detail.format(**vars_),
                       "detail_key": detail, "detail_vars": vars_, "evidence": evidence})

    if cap.get("work_types"):
        kind = classify_kind(title)
        body_kind = None if kind else classify_kind(body[:20000])
        if not kind and body_kind:
            add("work_type", "Type of work", "UNCLEAR",
                "The title does not name the type of work; the text mentions {kind} — check it.",
                _evidence(sources, body_kind.split()[0]), kind=body_kind)
        elif not kind:
            add("work_type", "Type of work", "UNCLEAR", "The tender does not name its type of work clearly.")
        else:
            ok = kind in cap["work_types"]
            add("work_type", "Type of work", "PASS" if ok else "FAIL",
                "Tender: {kind}. Company: {company}.",
                None, kind=kind, company=", ".join(cap["work_types"]))
    if cap.get("max_kv"):
        kv = main_kv(title, body)
        if not kv:
            add("voltage", "Voltage", "UNCLEAR", "No voltage (kV) found in the tender.")
        else:
            ok = kv <= float(cap["max_kv"])
            add("voltage", "Voltage", "PASS" if ok else "FAIL",
                "Tender: {kv} kV. Company works up to {max} kV.",
                _evidence(sources, re.compile(rf"\b{kv}(?:/\d{{1,3}}(?:\.\d{{1,2}})?){{0,3}}\s?kV", re.IGNORECASE)),
                kv=kv, max=f"{cap['max_kv']:g}")
    if cap.get("countries"):
        country = detect_country([title, body[:200000]])
        if not country:
            add("country", "Country", "UNCLEAR", "The project country is not stated clearly.")
        else:
            ok = country in cap["countries"]
            add("country", "Country", "PASS" if ok else "FAIL",
                "Tender: {country}. Company works in: {company}.", country=country, company=", ".join(cap["countries"]))
    demanded = set()
    demand_ev = None
    for s in sources:
        for m in _ISO.finditer(s.text or ""):
            a, b = max(0, m.start() - 160), m.end() + 160
            sent = _sentence(s.text, m.start(), m.end())
            if _DEMAND.search(sent) and _COMPANY.search(sent) and not _THIRD_PARTY.search(sent):
                demanded.add(f"ISO {m.group(1)}")
                demand_ev = demand_ev or {"file": s.source_document, "page": s.page_number,
                                          "quote": " ".join(s.text[a:b].split())}
    if demanded:
        held = {f"ISO {m.group(1)}" for c in cap.get("certifications") or [] for m in _ISO.finditer(c)}
        missing = sorted(demanded - held)
        if not cap.get("certifications"):
            add("certifications", "Certifications", "UNCLEAR",
                "Tender asks for {need}; add your certifications in Settings.", demand_ev, need=", ".join(sorted(demanded)))
        else:
            add("certifications", "Certifications", "FAIL" if missing else "PASS",
                ("Tender asks for {need}; company lacks {missing}." if missing else "Tender asks for {need}; company holds them."),
                demand_ev, need=", ".join(sorted(demanded)), missing=", ".join(missing))
    reg_ev = _evidence(sources, _REG)
    if reg_ev:
        words = {w.lower() for r in cap.get("registrations") or [] for w in re.findall(r"[A-Za-z]{3,}", r)}
        hit = words and any(w in reg_ev["quote"].lower() for w in words - {"the", "and", "with", "approved"})
        add("registration", "Registration / prequalification", "PASS" if hit else "UNCLEAR",
            "Tender requires a registration or prequalification — check it matches yours.", reg_ev)
    m, about_company = None, False
    for s in sources:
        for cand in _YEARS.finditer(s.text or ""):
            sent = _sentence(s.text, cand.start(), cand.end())
            if _PERSONNEL.search(sent):
                continue  # key-staff experience, not the company's
            m, about_company = cand, bool(_COMPANY.search(sent))
            years_ev = {"file": s.source_document, "page": s.page_number, "quote": " ".join(sent.split())[:300]}
            break
        if m:
            break
    if m:
        need = int(m.group(3))
        have = cap.get("years_experience")
        if not about_company:
            add("experience", "Years of experience", "UNCLEAR",
                "Tender asks for {need} years — check whether this is about the company.", years_ev, need=need)
        elif have is None:
            add("experience", "Years of experience", "UNCLEAR", "Tender asks for {need} years.", years_ev, need=need)
        else:
            add("experience", "Years of experience", "PASS" if have >= need else "FAIL",
                "Tender asks for {need} years; company has {have}.", years_ev, need=need, have=f"{have:g}")
    t = None
    for s in sources:
        t = _TURNOVER.search(s.text or "")
        if t:
            turn_ev = {"file": s.source_document, "page": s.page_number, "quote": " ".join(t.group(0).split())}
            break
    if t:
        need = _money(t.group(4), t.group(5))
        cur = _CUR.get((t.group(3) or "").upper(), (t.group(3) or "").upper()) or None
        have, have_cur = cap.get("annual_turnover"), (cap.get("turnover_currency") or "").upper() or None
        if need is None or have is None or not cur or cur != have_cur:
            add("turnover", "Annual turnover", "UNCLEAR",
                "Tender sets a minimum turnover — compare it with yours (currency or amount not comparable).", turn_ev)
        else:
            add("turnover", "Annual turnover", "PASS" if have >= need else "FAIL",
                "Tender asks for {need} {cur}; company {have} {cur}.", turn_ev, need=f"{need:,.0f}", cur=cur,
                have=f"{have:,.0f}")
    status = "INELIGIBLE" if any(c["result"] == "FAIL" for c in checks) else "ELIGIBLE"
    return {"status": status, "checks": checks}


def clear_foreign_capability_results(db) -> List[str]:
    """Results saved before capability_for stopped falling back to the env
    admin's profile may quote another company's capabilities (and may have
    blocked the tender as INELIGIBLE against them). Every owned tender's result
    that was not computed from its owner's own profile - including every result
    from before capability_source existed, whose provenance is unknown - loses
    its checks and becomes SKIPPED until the tender is processed again. A
    manager's override record is kept. Idempotent; returns the tender ids changed."""
    from app.models import EligibilityResult, Tender
    changed = []
    rows = (db.query(EligibilityResult, Tender).join(Tender, EligibilityResult.tender_id == Tender.id)
            .filter(Tender.owner_email.isnot(None)).all())
    for res, tender in rows:
        if not res.checks or res.capability_source == tender.owner_email:
            continue
        res.status, res.checks, res.capability_source = "SKIPPED", [], None
        changed.append(tender.id)
    if changed:
        db.commit()
    return changed


def run_gate(db, tender_id: str, job, doc_results: Dict[str, Any]) -> bool:
    """Called by processing after extraction. Returns True when processing must stop."""
    from app.models import EligibilityResult, Tender
    from app.pipeline.two_stage_runner import adapt_doc_results
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        return False
    row = db.query(EligibilityResult).filter(EligibilityResult.tender_id == tender_id).first()
    if row is not None and row.override_by:
        return False  # the manager chose to continue
    cap = capability_for(db, tender)
    sources, _ = adapt_doc_results(doc_results)
    res = check(capability_dict(cap), f"{tender.title or ''} {tender.client or ''}", sources)
    row = row or EligibilityResult(tender_id=tender_id)
    row.status, row.checks, row.created_at = res["status"], res["checks"], dt.datetime.utcnow()
    row.capability_source = cap.id if cap is not None else None
    db.merge(row)
    db.commit()
    if res["status"] != "INELIGIBLE":
        return False
    job.status = "INELIGIBLE"
    job.current_stage = "ELIGIBILITY"
    job.progress = 100
    job.completed_at = dt.datetime.utcnow()
    job.last_error = None
    db.commit()
    return True


def score(checks: Iterable[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Share of the tender's checks the company meets. UNCLEAR (information missing) is not counted
    as met and is reported separately; no checks = no percentage."""
    checks = list(checks or [])
    if not checks:
        return None
    n = {r: sum(1 for c in checks if c.get("result") == r) for r in ("PASS", "FAIL", "UNCLEAR")}
    return {"percent": round(100 * n["PASS"] / len(checks)), "met": n["PASS"], "failed": n["FAIL"],
            "unclear": n["UNCLEAR"], "total": len(checks)}


def result_dict(row) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    return {"status": row.status, "checks": row.checks or [], "score": score(row.checks),
            "override_by": row.override_by,
            "override_name": getattr(row, "override_name", None),
            "override_reason": row.override_reason,
            "overridden_at": row.overridden_at.isoformat() if row.overridden_at else None,
            "checked_at": row.created_at.isoformat() if row.created_at else None}


def failed_reasons(checks: Iterable[Dict[str, Any]]) -> List[str]:
    return [f"{c['label']}: {c['detail']}" for c in checks if c.get("result") == "FAIL"]
