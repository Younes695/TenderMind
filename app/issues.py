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
import uuid
from collections import defaultdict
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models import Requirement, TenderAnalysis, TenderIssue

_GAP_TITLES = {
    "missing-file": "File listed but missing",
    "unsupported-type": "File type could not be read",
    "failed-extraction": "File could not be read",
    "empty-ocr": "File produced no readable text",
    "referenced-form-absent": "Referenced document not in the package",
    "empty-analysis": "Tender has no documents",
}
_HIGH_GAPS = {"missing-file", "failed-extraction", "unsupported-type", "referenced-form-absent", "empty-analysis"}


def _key(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]


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
        for g in df.get("gaps") or []:
            kind = g.get("kind") or "gap"
            if kind == "referenced-form-absent":
                refs_absent.append(g)  # grouped below: one item, not one per reference
                continue
            ev = g.get("evidence") or []
            doc = ev[0].split("#")[0] if ev else None
            if kind in ("missing-file", "failed-extraction", "unsupported-type", "empty-ocr") and doc:
                seen_docs.add(doc)
            out.append({"category": "missing", "kind": kind,
                        "title": _GAP_TITLES.get(kind, "Package gap"),
                        "detail": g.get("description"), "source_document": doc,
                        "page": ", ".join(ev[:3]) if kind == "referenced-form-absent" else None,
                        "priority": "HIGH" if kind in _HIGH_GAPS else "MEDIUM",
                        "dedupe_key": _key("gap", kind, g.get("description"))})
        if refs_absent:
            names = [str(g.get("description") or "").split(" referenced")[0] for g in refs_absent]
            shown = ", ".join(names[:40]) + (" …" if len(names) > 40 else "")
            out.append({"category": "missing", "kind": "referenced-form-absent",
                        "title": "Referenced documents not in the package",
                        "detail": (f"{len(names)} forms / annexes / appendices are mentioned in the tender text "
                                   f"but no uploaded file matches them. Many are standards or parts of other "
                                   f"files — check the list and upload any that are really missing: {shown}"),
                        "source_document": None, "page": None, "priority": "MEDIUM",
                        "dedupe_key": _key("refs-absent", len(names))})
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
        for g in df.get("ambiguities") or []:
            pages = g.get("pages") or []
            out.append({"category": "question", "kind": g.get("ambiguity_type") or "ambiguity",
                        "title": "Unclear wording — ask for clarification",
                        "detail": g.get("description"), "source_document": g.get("source_document"),
                        "page": ", ".join(str(p) for p in pages[:10]) or None, "priority": "MEDIUM",
                        "dedupe_key": _key("amb", g.get("ambiguity_type"), g.get("source_document"),
                                           g.get("description"))})
        by_doc = defaultdict(list)
        for p in df.get("page_quality") or []:
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
    out = []
    for r in reqs:
        if (status.get(r.id) or {}).get("status") != "MISSING_EVIDENCE":
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
