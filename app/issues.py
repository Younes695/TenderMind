"""Stage 5H — review items ("missing") and questions (Q&A) per tender.

Built from what the pipeline already produced — nothing is guessed:
- missing:  files that are missing / failed / unsupported / read as empty,
            documents referenced in the text but not in the package,
            mandatory requirements with no company evidence (after Evaluate).
- question: grouped ambiguities, scanned pages OCR could not read reliably,
            requirements the AI could not classify (UNKNOWN).

sync_issues() is idempotent: each item has a stable dedupe_key, so a rebuild
adds only new items and never reopens one a person resolved.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from collections import defaultdict
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import Requirement, TenderAnalysis, TenderIssue
from app.pipeline.ambiguity import TBD_MARKER
from app.pipeline.gaps import evidence_page

_GAP_TITLES = {
    "missing-file": "File listed but missing",
    "unsupported-type": "File type could not be read",
    "failed-extraction": "File could not be read",
    "partial-extraction": "Some pages could not be read",
    "empty-ocr": "File produced no readable text",
    "referenced-form-absent": "Referenced document not in the package",
    "empty-analysis": "Tender has no documents",
}
_HIGH_GAPS = {"missing-file", "failed-extraction", "partial-extraction", "unsupported-type",
              "referenced-form-absent", "empty-analysis"}


_MODEL_DOUBTS = {"unclear-applicability", "undefined-term"}
_QUESTION_TITLES = {
    "missing-value": "Value not stated (TBD) — ask the tender owner",
    "unclear-date-anchor": "Duration without a start date — ask the tender owner",
}


def _key(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]


def _natural(ref: str):
    """APPENDIX II before APPENDIX X, FORM 2 before FORM 10."""
    from app.pipeline.gaps import _ROMAN
    import re
    kind, _, ident = ref.partition(" ")
    if re.fullmatch(_ROMAN, ident):
        vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        n = sum(-vals[a] if vals[a] < vals.get(b, 0) else vals[a] for a, b in zip(ident, ident[1:] + " "))
        return (kind, 0, n, "")
    m = re.match(r"\d+", ident)
    return (kind, 1, int(m.group()) if m else 0, ident)


def _latest_analysis(db: Session, tender_id: str):
    return (db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id)
            .order_by(TenderAnalysis.created_at.desc()).first())


def build_candidates(db: Session, tender_id: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    a = _latest_analysis(db, tender_id)
    if a is not None:
        df = a.derived_features or {}
        seen_docs = set()
        refs_absent = []
        unread_docs, unread_pages = set(), set()  # already reported as gaps: not asked again below
        for g in df.get("gaps") or []:
            kind = g.get("kind") or "gap"
            if kind == "referenced-form-absent":
                refs_absent.append(g)  # grouped below: one item, not one per reference
                continue
            ev = g.get("evidence") or []
            doc = evidence_page(ev[0])[0] if ev else None
            if kind == "failed-extraction" and doc:
                unread_docs.add(doc)
            elif kind == "partial-extraction":
                for e in ev:
                    unread_pages.add(evidence_page(e))
            if kind in ("missing-file", "failed-extraction", "unsupported-type", "empty-ocr") and doc:
                seen_docs.add(doc)
            if kind in ("failed-extraction", "partial-extraction") and doc:
                # Keyed by file and pages, not the description: it quotes the reader's
                # error (temp paths), which changes on every read of the same file.
                key = _key("gap", kind, doc, *sorted({p for _d, p in map(evidence_page, ev) if p}, key=int))
            else:
                key = _key("gap", kind, g.get("description"))
            out.append({"category": "missing", "kind": kind,
                        "title": _GAP_TITLES.get(kind, "Package gap"),
                        "detail": g.get("description"), "source_document": doc,
                        "page": ", ".join(ev[:3]) if kind == "referenced-form-absent" else None,
                        "priority": "HIGH" if kind in _HIGH_GAPS else "MEDIUM",
                        "dedupe_key": key})
        if refs_absent:
            from app.pipeline.gaps import normalize_form_ref  # also cleans analyses stored before the fix
            by_doc: Dict[str, set] = defaultdict(set)
            for g in refs_absent:
                n = normalize_form_ref(str(g.get("description") or "").split(" referenced")[0])
                if n:
                    ev = g.get("evidence") or []
                    by_doc[evidence_page(ev[0])[0] if ev else "?"].add(n)
            names = {n for refs in by_doc.values() for n in refs}
            unread = next((int(m.group(1)) for g in refs_absent
                           for m in [re.match(r"(\d+) page", str(g.get("note") or ""))] if m), 0)
            if names:
                # Language-neutral detail (file: references); the explanation is
                # translated in the UI for this kind.
                lines = []
                for doc, refs in sorted(by_doc.items()):
                    r = sorted(refs, key=_natural)
                    lines.append(f"{doc}: {', '.join(r[:30])}" + (f" (+{len(r) - 30})" if len(r) > 30 else ""))
                # Not proof of absence: pages without readable text may hold some of them.
                title = "Referenced documents not found in the readable text"
                out.append({"category": "missing", "kind": "referenced-form-absent",
                            "title": f"{title} ({unread} page(s) unread)" if unread else title,
                            "detail": "\n".join(lines),
                            "source_document": None, "page": None, "priority": "MEDIUM",
                            "dedupe_key": _key("refs-absent", sorted(names))})
        for d in a.documents or []:
            name = d.get("filename")
            status = d.get("extraction_status") or d.get("document_status")
            if not name or name in seen_docs:
                continue
            if status in ("FAILED", "UNSUPPORTED"):
                kind = "failed-extraction" if status == "FAILED" else "unsupported-type"
                out.append({"category": "missing", "kind": kind, "title": _GAP_TITLES[kind],
                            "detail": f"{name}: {status.lower()} — its content is not part of the analysis.",
                            "source_document": name, "page": None, "priority": "HIGH",
                            "dedupe_key": _key("gap", kind, name)})
        # Stage 6: only real clarification needs become questions, one per requirement,
        # quoting the tender's own words. Model doubts (binding force unclear, model
        # abstained) are internal — they were 31 of 48 Turaif "questions" and the email
        # draft sent them to the tender owner.
        req_by_id = {r.get("requirement_id"): r for r in a.requirements or []}
        for g in df.get("ambiguities") or []:
            kind = g.get("ambiguity_type") or "ambiguity"
            if kind in _MODEL_DOUBTS:
                continue
            for s in g.get("raw_signals") or []:
                r = req_by_id.get(s.get("requirement_id")) or {}
                quote = " ".join(str(r.get("source_text") or r.get("summary") or "").split())[:300]
                if not quote or (kind == "missing-value" and not TBD_MARKER.search(quote)):
                    continue  # analyses stored before Stage 6 flagged boilerplate ("as applicable")
                out.append({"category": "question", "kind": kind,
                            "title": _QUESTION_TITLES.get(kind, "Unclear wording — ask for clarification"),
                            "detail": quote, "source_document": r.get("source_document") or g.get("source_document"),
                            "page": str(r.get("page_number")) if r.get("page_number") else None,
                            "priority": "MEDIUM",
                            "dedupe_key": _key("amb2", kind, s.get("requirement_id"), quote)})
        by_doc = defaultdict(list)
        for p in df.get("page_quality") or []:
            if p.get("document") in unread_docs or (p.get("document"), str(p.get("page"))) in unread_pages:
                continue
            by_doc[p.get("document")].append(p)
        for doc, pages in sorted(by_doc.items(), key=lambda kv: str(kv[0])):
            nums = sorted({int(p["page"]) for p in pages if str(p.get("page") or "").isdigit()})
            shown = ", ".join(str(n) for n in nums[:20]) + (" …" if len(nums) > 20 else "")
            out.append({"category": "question", "kind": "unreadable-pages",
                        "title": f"{len(pages)} scanned page(s) could not be read reliably",
                        "detail": ("Low OCR quality — check these pages by eye or ask for a clearer copy. "
                                   f"Pages: {shown}"),
                        "source_document": doc, "page": shown or None, "priority": "MEDIUM",
                        "dedupe_key": _key("pages", doc, len(pages))})
        unknown_by_doc = defaultdict(list)
        for r in a.requirements or []:
            if (r.get("category") or "").upper() == "UNKNOWN":
                unknown_by_doc[r.get("source_document")].append(r)
        for doc, rs in sorted(unknown_by_doc.items(), key=lambda kv: str(kv[0])):
            if len(rs) == 1:
                r = rs[0]
                out.append({"category": "question", "kind": "unclassified-requirement",
                            "title": "Requirement could not be classified",
                            "detail": r.get("summary"), "source_document": doc,
                            "page": str(r.get("page_number")) if r.get("page_number") else None,
                            "priority": "LOW",
                            "dedupe_key": _key("unknown", r.get("requirement_id"), r.get("summary"))})
                continue
            lines = [f"p.{r.get('page_number')}: {r.get('summary')}" for r in rs[:30]]
            out.append({"category": "question", "kind": "unclassified-requirement",
                        "title": f"{len(rs)} requirements could not be classified",
                        "detail": "Check these and set the right category:\n" + "\n".join(lines)
                                  + (f"\n… and {len(rs) - 30} more" if len(rs) > 30 else ""),
                        "source_document": doc, "page": None, "priority": "LOW",
                        "dedupe_key": _key("unknown-doc", doc, len(rs))})
    try:  # Stage 7: the package contradicts itself -> ask, never pick one silently
        from app.conflicts import tender_conflicts
        for c in tender_conflicts(tender_id):
            lines = [f"- {v['value']}: {v['file']}, p. {v['page']} — “{v['quote'][:200]}”" for v in c["values"]]
            first = c["values"][0]
            out.append({"category": "question", "kind": "conflict",
                        "title": f"Documents disagree: {c['label']}",
                        "detail": "Which value applies?\n" + "\n".join(lines),
                        "source_document": first["file"], "page": str(first["page"]), "priority": "MEDIUM",
                        "dedupe_key": _key("conflict", c["fact"], [v["value"] for v in c["values"]],
                                           [v["quote"][:80] for v in c["values"]])})
    except Exception:
        pass
    try:  # Stage 8: the company has worked with this client before
        from app.models import Tender as _T
        from app.similarity import client_history
        t = db.query(_T).filter(_T.id == tender_id).first()
        hist, client = client_history(db, t) if t else ([], None)
        if hist:
            lines = [f"- {h['id']} — {h['title'] or ''}"
                     + (f" · {h['decision']}" if h.get("decision") else "") + (f" · {h['outcome']}" if h.get("outcome") else "")
                     for h in hist[:10]]
            out.append({"category": "info", "kind": "client-history",
                        "title": f"You took part in a tender with this client before: {client}",
                        "detail": "\n".join(lines), "source_document": None, "page": None, "priority": "LOW",
                        "dedupe_key": _key("client-history", client, sorted(h["id"] for h in hist))})
    except Exception:
        db.rollback()
    from app.models import EligibilityResult  # Stage 6 gate
    el = db.query(EligibilityResult).filter(EligibilityResult.tender_id == tender_id).first()
    if el is not None and el.status == "INELIGIBLE" and not el.override_by:
        from app.eligibility import failed_reasons
        reasons = failed_reasons(el.checks or [])
        out.append({"category": "missing", "kind": "ineligible", "title": "Tender not suitable for the company",
                    "detail": "\n".join(reasons) + "\nThe full analysis was not run. Open the tender to review "
                              "the checks or continue anyway.",
                    "source_document": None, "page": None, "priority": "HIGH",
                    "dedupe_key": _key("ineligible", tender_id, reasons)})
    out.extend(_missing_evidence(db, tender_id))
    return out


def _missing_evidence(db: Session, tender_id: str) -> List[Dict[str, Any]]:
    """Mandatory requirements with no company evidence — only once the tender was evaluated."""
    try:
        from app.engines.tender_bridge import req_prefix, HARD_GATE_CATEGORIES
        from app.engines.status import evaluate_all
        from app.models import EvidenceMatch
        reqs = db.query(Requirement).filter(Requirement.id.like(f"{req_prefix(tender_id)}%"),
                                            Requirement.mandatory.is_(True)).all()
        if not reqs:
            return []
        ids = [r.id for r in reqs]
        if not db.query(EvidenceMatch).filter(EvidenceMatch.requirement_id.in_(ids)).first():
            return []  # not evaluated yet: every requirement would look "missing"
        status = evaluate_all(db, tender_id)
    except Exception:
        return []
    from app.engines.decision import contradiction_waived, latest_decision
    accepted = contradiction_waived(latest_decision(db, tender_id))  # a person decided to bid anyway
    out = []
    for r in reqs:
        st = (status.get(r.id) or {}).get("status")
        if st == "FAIL":
            if accepted:
                continue
            # Not a gap: the company's own document says the opposite. The
            # decision cannot be BID until a person resolved it.
            out.append({"category": "missing", "kind": "evidence-contradicted",
                        "title": "A company document contradicts a mandatory requirement",
                        "detail": r.requirement, "source_document": r.source_document,
                        "page": r.page_or_section, "priority": "HIGH",
                        "dedupe_key": _key("contradicted", r.id)})
            continue
        if st != "MISSING_EVIDENCE":
            continue
        out.append({"category": "missing", "kind": "evidence-missing",
                    "title": "No company evidence for a mandatory requirement",
                    "detail": r.requirement, "source_document": r.source_document,
                    "page": r.page_or_section,
                    "priority": "HIGH" if (r.category or "") in HARD_GATE_CATEGORIES else "MEDIUM",
                    "dedupe_key": _key("evidence", r.id)})
    return out


_SUPERSEDED = {  # Stage 5I: per-item kinds now grouped — drop their open, untouched rows
    "referenced-form-absent": "Referenced document not in the package",
    "unclassified-requirement": "Requirement could not be classified",
    # Stage 6: grouped model-doubt "questions" replaced by per-requirement quotes
    "unclear-applicability": "", "undefined-term": "", "missing-value": "", "unclear-date-anchor": "",
    # A contradiction the evidence no longer shows (or a BID override accepted) retires by itself.
    "evidence-contradicted": "",
    "client-history": "",  # Stage 8: refreshed when more tenders with the client arrive
    "ineligible": "",  # Stage 6: disappears once the manager overrides or the tender becomes eligible
    # A file read again (a retry, OCR installed) with other pages unread, or read in full.
    "failed-extraction": "", "partial-extraction": "",
}


def sync_issues(db: Session, tender_id: str) -> Dict[str, int]:
    candidates = build_candidates(db, tender_id)
    wanted = {c["dedupe_key"] for c in candidates}
    for kind in _SUPERSEDED:
        db.query(TenderIssue).filter(TenderIssue.tender_id == tender_id, TenderIssue.kind == kind,
                                     TenderIssue.status == "OPEN", TenderIssue.answer.is_(None),
                                     TenderIssue.dedupe_key.notin_(wanted)).delete(synchronize_session=False)
    existing = {k for (k,) in db.query(TenderIssue.dedupe_key).filter(TenderIssue.tender_id == tender_id)}
    added = 0
    for c in candidates:
        if c["dedupe_key"] in existing:
            continue
        existing.add(c["dedupe_key"])
        db.add(TenderIssue(id=f"ISS-{uuid.uuid4().hex[:10].upper()}", tender_id=tender_id,
                           category=c["category"], kind=c["kind"], title=c["title"][:300],
                           detail=(c.get("detail") or "")[:4000] or None,
                           source_document=c.get("source_document"),
                           page=(c.get("page") or None) and str(c["page"])[:200],
                           priority=c.get("priority") or "MEDIUM", status="OPEN",
                           dedupe_key=c["dedupe_key"]))
        added += 1
    db.commit()
    return {"added": added, "total": len(existing)}


def sync_issues_safe(tender_id: str) -> None:
    """For the end of a processing job: never raises."""
    from app.database import SessionLocal
    s = SessionLocal()
    try:
        sync_issues(s, tender_id)
    except Exception:
        s.rollback()
    finally:
        s.close()


def issue_dict(i: TenderIssue) -> Dict[str, Any]:
    return {"id": i.id, "tender_id": i.tender_id, "category": i.category, "kind": i.kind,
            "title": i.title, "detail": i.detail, "source_document": i.source_document,
            "page": i.page, "priority": i.priority, "status": i.status, "answer": i.answer,
            "resolved_by": i.resolved_by,
            "created_at": i.created_at.isoformat() if i.created_at else None,
            "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None}
