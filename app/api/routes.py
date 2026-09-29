import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from app.auth import require_auth
from app.access import (enforce_tender_access, owner_filter, owner_for_new_rows, owns,
                        tender_owner_or_404, is_admin, DEMO_COMPANY_ID)
from sqlalchemy.orm import Session
from app.database import get_db, get_storage_root
from app.models import Tender, Requirement, Evidence, EvidenceMatch, Risk, MissingEvidence, Decision, DecisionAudit, Company, CompanyDocument, TenderDocument, TenderAnalysis, ProcessingJob
from app.engines.status import evaluate_all
from app.engines.decision import get_or_create_decision
from app.engines.explanation import build_explanation
from datetime import datetime
import uuid
from typing import List, Optional
import re
from pathlib import Path

router = APIRouter(dependencies=[Depends(require_auth), Depends(enforce_tender_access)])

@router.get("/tenders")
def list_tenders(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.access import DEMO_TENDER_ID
    q = db.query(Tender)
    flt = owner_filter(Tender.owner_email, user)
    if flt is not None:
        q = q.filter(flt | (Tender.id == DEMO_TENDER_ID))
    return q.all()

@router.post("/tenders")
def create_tender(payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    # Validate required fields per existing model conventions
    raw_id = payload.get("id") or payload.get("tender_id")
    title = payload.get("title")
    # Strip and validate
    tender_id = str(raw_id).strip() if raw_id is not None else ""
    title_str = str(title).strip() if title is not None else ""
    if not tender_id or not title_str:
        raise HTTPException(status_code=400, detail="id and title are required")
    # Prevent path traversal and invalid characters; allow alphanumeric, hyphen, underscore only for storage safety
    # Tender ID is used as directory name under storage_root, so must be filesystem-safe
    if ".." in tender_id or tender_id.startswith("/") or tender_id.startswith("\\") or "//" in tender_id or "\\" in tender_id:
        raise HTTPException(status_code=400, detail="Invalid tender_id: path traversal not allowed")
    if tender_id in (".", "..", ""):
        raise HTTPException(status_code=400, detail="Invalid tender_id")
    # Strict pattern: alphanumeric, hyphen, underscore (slash allowed only as single separator for nested IDs, but still filesystem safe)
    # We allow slash for logical IDs but ensure each segment is safe
    if "/" in tender_id:
        segments = tender_id.split("/")
        for seg in segments:
            if not seg or seg in (".", ".."):
                raise HTTPException(status_code=400, detail="Invalid tender_id segment")
            if not re.match(r"^[A-Za-z0-9-_]+$", seg):
                raise HTTPException(status_code=400, detail="Invalid tender_id format: segments must be alphanumeric, hyphen or underscore")
    else:
        if not re.match(r"^[A-Za-z0-9-_]+$", tender_id):
            raise HTTPException(status_code=400, detail="Invalid tender_id format: must be alphanumeric, hyphen or underscore")
    # Length guard
    if len(tender_id) > 100:
        raise HTTPException(status_code=400, detail="tender_id too long (max 100)")
    if len(title_str) > 500:
        raise HTTPException(status_code=400, detail="title too long (max 500)")
    existing = db.query(Tender).filter(Tender.id == tender_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Tender {tender_id} already exists")
    tender = Tender(
        id=tender_id,
        title=title_str,
        client=payload.get("client"),
        location=payload.get("location"),
        owner_email=owner_for_new_rows(user),
    )
    db.add(tender)
    db.commit()
    db.refresh(tender)
    return tender

@router.get("/tenders/{tender_id}")
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    t = db.query(Tender).filter(Tender.id == tender_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tender not found")
    return t

@router.get("/tenders/{tender_id}/documents")
def list_documents(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    docs = db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id).all()
    # Return with source_path if available, for client/debugging
    out = []
    for d in docs:
        out.append({
            "id": d.id,
            "tender_id": d.tender_id,
            "title": d.title,
            "doc_type": d.doc_type,
            "page": d.page,
            "section": d.section,
            "language": d.language,
            "file_size": getattr(d, "file_size", None),
            "original_filename": getattr(d, "original_filename", None),
        })
    return {"tender_id": tender_id, "documents": out, "count": len(out)}

DEFAULT_MAX_UPLOAD_MB = 5 * 1024  # 5 GB per file
_UPLOAD_CHUNK = 8 * 1024 * 1024


def _max_upload_bytes(plan: Optional[str] = None) -> int:
    """Per-file upload cap in bytes.

    Single place to change the limit. TENDERMIND_MAX_UPLOAD_MB sets the global
    cap (default 5 GB). Subscription plans can later override it with
    TENDERMIND_MAX_UPLOAD_MB_<PLAN> (e.g. TENDERMIND_MAX_UPLOAD_MB_STARTER=500)
    once the caller knows the account's plan.
    """
    raw = None
    if plan:
        raw = os.environ.get(f"TENDERMIND_MAX_UPLOAD_MB_{plan.upper()}")
    raw = raw or os.environ.get("TENDERMIND_MAX_UPLOAD_MB", str(DEFAULT_MAX_UPLOAD_MB))
    try:
        mb = int(raw)
    except ValueError:
        mb = DEFAULT_MAX_UPLOAD_MB
    return max(1, mb) * 1024 * 1024


def _fmt_limit(n_bytes: int) -> str:
    mb = n_bytes // (1024 * 1024)
    return f"{mb / 1024:g} GB" if mb >= 1024 else f"{mb} MB"


def _stream_to_disk(upload_file: UploadFile, dest_path: Path, display_name: str) -> int:
    """Copy an upload to dest_path in 8 MB chunks; never holds the file in memory.

    Enforces the size cap while copying and rejects empty files; on any
    rejection or error the partial file is removed. Returns bytes written.
    """
    limit = _max_upload_bytes()
    written = 0
    try:
        with open(dest_path, "wb") as out:
            while True:
                chunk = upload_file.file.read(_UPLOAD_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise HTTPException(status_code=413,
                                        detail=f"File too large (max {_fmt_limit(limit)} per file): {display_name}")
                out.write(chunk)
        if written == 0:
            raise HTTPException(status_code=400, detail=f"Empty file not accepted: {display_name}")
        return written
    except BaseException:
        try:
            dest_path.unlink()
        except OSError:
            pass
        raise


@router.post("/tenders/{tender_id}/documents")
def upload_documents(tender_id: str, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    # Verify tender exists
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    # Validate files presence
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided")
    # Use single source of truth for storage root
    storage_root = get_storage_root()
    # Ensure storage_root exists
    storage_root.mkdir(parents=True, exist_ok=True)
    # Tender directory — use pathlib for platform independence
    # tender_id may contain "/" for logical nesting; handle via Path parts safely after validation above
    tender_dir = storage_root / tender_id
    # Prevent path traversal: resolved tender_dir must be inside resolved storage_root
    try:
        tender_dir_resolved = tender_dir.resolve()
        storage_root_resolved = storage_root.resolve()
        # Python 3.9+: is_relative_to
        try:
            tender_dir_resolved.relative_to(storage_root_resolved)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tender_id path traversal")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid tender_id path: {e}")
    tender_dir.mkdir(parents=True, exist_ok=True)

    # Validate storage_root / tender_dir are actually directories and inside root after creation
    try:
        # Re-check after mkdir
        tender_dir_resolved = tender_dir.resolve()
        storage_root_resolved = storage_root.resolve()
        tender_dir_resolved.relative_to(storage_root_resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tender_id path traversal after creation")
    except Exception:
        pass

    created_docs = []
    for upload_file in files:
        # Validate filename presence
        original_filename = upload_file.filename or ""
        original_filename = original_filename.strip()
        if not original_filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        # Prevent path traversal and unsafe names: only use basename
        # Path().name strips directory components on both POSIX and Windows
        safe_filename = Path(original_filename).name
        # Additional sanitization: remove any remaining path separators, control chars
        safe_filename = safe_filename.strip()
        if not safe_filename or safe_filename in (".", "..", ""):
            raise HTTPException(status_code=400, detail=f"Invalid filename: {safe_filename}")
        # Reject filenames with path separators after basename extraction (should not happen)
        if "/" in safe_filename or "\\" in safe_filename or "\0" in safe_filename:
            raise HTTPException(status_code=400, detail=f"Invalid filename: {safe_filename}")
        # Reject overly long filenames
        if len(safe_filename) > 255:
            raise HTTPException(status_code=400, detail=f"Filename too long: {safe_filename}")
        # For Windows, also check reserved names
        reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
        if safe_filename.upper().split(".")[0] in reserved:
            raise HTTPException(status_code=400, detail=f"Invalid filename (reserved): {safe_filename}")

        # Size cap and empty-file checks happen while streaming to disk below
        # (the file is never loaded into memory — uploads can be several GB).

        # Determine destination with collision avoidance (platform-independent)
        dest_path = tender_dir / safe_filename
        # Ensure dest_path is still inside storage_root
        try:
            dest_resolved = dest_path.resolve()
            # For not-yet-existing file, resolve will resolve parent; check parent is inside root
            dest_resolved.parent.relative_to(storage_root.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid filename path traversal: {safe_filename}")
        except Exception:
            pass
        # Collision handling: do not overwrite; add _1, _2 suffix
        counter = 1
        base_name = dest_path.stem
        ext = dest_path.suffix
        # Keep original safe_filename for title/original_filename, but dest_path may be renamed
        final_filename = safe_filename
        while dest_path.exists():
            final_filename = f"{base_name}_{counter}{ext}"
            dest_path = tender_dir / final_filename
            counter += 1
            # Re-check traversal for renamed
            try:
                dest_path.resolve().parent.relative_to(storage_root.resolve())
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid filename path traversal after collision handling")
            if counter > 1000:
                raise HTTPException(status_code=400, detail="Too many duplicate filenames")

        # Validate again before writing
        try:
            dest_path.resolve().parent.relative_to(storage_root.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid destination path traversal")

        # Stream to disk in chunks, enforcing the size cap as we go
        try:
            size = _stream_to_disk(upload_file, dest_path, safe_filename)
            # Verify file was written and inside root
            if not dest_path.exists() or dest_path.stat().st_size != size:
                raise HTTPException(status_code=500, detail=f"Failed to persist file {final_filename}")
            # Final traversal check on persisted file
            try:
                dest_path.resolve().relative_to(storage_root.resolve())
            except ValueError:
                # Remove file if outside root
                try:
                    dest_path.unlink()
                except:
                    pass
                raise HTTPException(status_code=400, detail="File path outside storage root after write")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to store file {final_filename}: {e}")

        # doc_type from extension, or from content for .bak / unknown extensions
        # (honest: UNSUPPORTED only when the server cannot read it).
        from app.pipeline.file_extractors import upload_doc_type
        doc_type = upload_doc_type(dest_path)

        # Sanitize the echoed original name (Stage 4H): basename + strip control
        # chars and HTML-active characters so user input is never reflected
        # raw into API responses/DB. Filesystem writes already use safe_filename.
        import re as _re
        display_filename = Path(original_filename).name
        display_filename = _re.sub(r"[\x00-\x1f\x7f<>\"'&]", "", display_filename).strip()
        if not display_filename:
            display_filename = safe_filename
        display_filename = display_filename[:255]
        doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
        # Persist actual path reference needed by processing — canonical field source_path
        tender_doc = TenderDocument(
            id=doc_id,
            tender_id=tender_id,
            title=final_filename,  # preserve original filename (or renamed if collision) as title
            doc_type=doc_type,
            page="1",
            section="",
            language="EN",
            source_path=str(dest_path.resolve()),
            file_size=float(size),
            original_filename=display_filename,
        )
        db.add(tender_doc)
        # Flush to catch DB errors before commit
        try:
            db.flush()
        except Exception as e:
            db.rollback()
            # Cleanup file on DB failure
            try:
                dest_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to create document record: {e}")
        created_docs.append({
            "id": doc_id,
            "tender_id": tender_id,
            "title": final_filename,
            "original_filename": display_filename,
            "filename": final_filename,
            "size": size,
            "file_size": size,
            "doc_type": doc_type,
        })
    db.commit()
    return {"tender_id": tender_id, "documents": created_docs, "count": len(created_docs)}

def _active_job(db: Session, tender_id: str):
    return (db.query(ProcessingJob)
            .filter(ProcessingJob.tender_id == tender_id,
                    ProcessingJob.status.in_(["QUEUED", "PROCESSING"]))
            .first())


def _remove_stored_file(doc: TenderDocument) -> None:
    """Delete the stored file, only ever inside the storage root."""
    try:
        p = Path(doc.source_path or "")
        root = get_storage_root().resolve()
        if p.is_file() and root in p.resolve().parents:
            p.unlink()
    except OSError:
        pass


def _delete_documents(db: Session, tender_id: str, doc_id: Optional[str] = None) -> dict:
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    if _active_job(db, tender_id):
        raise HTTPException(status_code=409,
                            detail="Tender is being processed — wait for it to finish before removing files")
    q = db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id)
    if doc_id is not None:
        q = q.filter(TenderDocument.id == doc_id)
    docs = q.all()
    if doc_id is not None and not docs:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    removed = []
    for d in docs:
        _remove_stored_file(d)
        removed.append({"id": d.id, "title": d.title})
        db.delete(d)
    db.commit()
    remaining = db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id).count()
    has_analysis = db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id).first() is not None
    return {"tender_id": tender_id, "removed": removed, "removed_count": len(removed),
            "remaining_count": remaining,
            # Existing results were computed from the old file set.
            "reprocess_needed": bool(removed) and has_analysis}


@router.delete("/tenders/{tender_id}/documents/{doc_id}")
def delete_document(tender_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Remove one uploaded file so it is not used in processing."""
    return _delete_documents(db, tender_id, doc_id)


@router.delete("/tenders/{tender_id}/documents")
def delete_all_documents(tender_id: str, db: Session = Depends(get_db)):
    """Remove every uploaded file of a tender."""
    return _delete_documents(db, tender_id)


@router.get("/tenders/{tender_id}/requirements")
def get_requirements(tender_id: str, db: Session = Depends(get_db)):
    reqs = db.query(Requirement).filter(Requirement.tender_id == tender_id).all()
    status_results = evaluate_all(db, tender_id)
    out = []
    for r in reqs:
        sr = status_results.get(r.id, {})
        out.append({
            "requirement_id": r.id,
            "category": r.category,
            "requirement": r.requirement,
            "mandatory": r.mandatory,
            "requirement_type": r.requirement_type,
            "evidence_required": r.evidence_required,
            "source_document": r.source_document,
            "page_or_section": r.page_or_section,
            "status": sr.get("status"),
            "evidence_ids": sr.get("evidence_ids", []),
            "reason": sr.get("reason"),
            "provenance": sr.get("provenance", [])
        })
    return out

@router.get("/tenders/{tender_id}/evidence")
def get_evidence(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")

    evidences = (
        db.query(Evidence)
        .outerjoin(Requirement, Evidence.requirement_id == Requirement.id)
        .filter(
            or_(
                Requirement.tender_id == tender_id,
                Evidence.tender_source_id == tender_id,
            )
        )
        .all()
    )
    return evidences

@router.get("/tenders/{tender_id}/risks")
def get_risks(tender_id: str, db: Session = Depends(get_db)):
    risks = db.query(Risk).filter(Risk.tender_id == tender_id).all()
    return risks

@router.get("/tenders/{tender_id}/missing-evidence")
def get_missing(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")

    status_results = evaluate_all(db, tender_id)

    from app.engines.missing_evidence import generate_missing_evidence
    generate_missing_evidence(db, tender_id, status_results)

    return (
        db.query(MissingEvidence)
        .join(Requirement, MissingEvidence.requirement_id == Requirement.id)
        .filter(Requirement.tender_id == tender_id)
        .all()
    )

@router.get("/tenders/{tender_id}/decision")
def get_decision(tender_id: str, db: Session = Depends(get_db)):
    # return latest decision, or create one
    dec = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not dec:
        dec, _ = get_or_create_decision(db, tender_id)
    status_results = evaluate_all(db, tender_id)
    return {
        "decision": dec.decision,
        "confidence": dec.confidence,
        "decision_id": dec.id,
        "tender_id": dec.tender_id,
        "timestamp": dec.timestamp,
        "rules_triggered": dec.rules_triggered,
        "hard_fail_count": dec.hard_fail_count,
        "mandatory_missing_evidence_count": dec.mandatory_missing_count,
        "top_blockers": dec.top_blockers,
        "top_risks": dec.top_risks,
        "supporting_requirements": dec.supporting_requirements,
        "supporting_evidence": dec.supporting_evidence,
        "missing_evidence": dec.missing_evidence,
        "risks": dec.risks,
        "is_override": dec.is_override,
        "status_results": status_results
    }

@router.post("/tenders/{tender_id}/decision/recompute")
def recompute(tender_id: str, db: Session = Depends(get_db)):
    dec, _ = get_or_create_decision(db, tender_id)
    return {"decision": dec.decision, "confidence": dec.confidence, "decision_id": dec.id, "rules_triggered": dec.rules_triggered}

@router.post("/tenders/{tender_id}/decision/override")
def override(tender_id: str, payload: dict, db: Session = Depends(get_db)):
    # payload: reviewer, new_decision, reason, comments
    reviewer = payload.get("reviewer", "unknown")
    new_decision = payload.get("new_decision")
    reason = payload.get("reason", "")
    comments = payload.get("comments", "")
    if new_decision not in ("BID","REVIEW","NO_BID"):
        raise HTTPException(status_code=400, detail="new_decision must be BID/REVIEW/NO_BID")
    last = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not last:
        raise HTTPException(status_code=404, detail="No decision to override")
    # create new decision as override
    override_dec = Decision(
        id=f"DEC-{uuid.uuid4().hex[:6].upper()}",
        tender_id=tender_id,
        decision=new_decision,
        confidence="OVERRIDE",
        timestamp=datetime.utcnow(),
        rules_triggered=["HUMAN_OVERRIDE"],
        supporting_requirements=last.supporting_requirements,
        supporting_evidence=last.supporting_evidence,
        missing_evidence=last.missing_evidence,
        risks=last.risks,
        hard_fail_count=last.hard_fail_count,
        mandatory_missing_count=last.mandatory_missing_count,
        top_blockers=last.top_blockers,
        top_risks=last.top_risks,
        is_override=True
    )
    db.add(override_dec)
    audit = DecisionAudit(
        id=f"AUD-{uuid.uuid4().hex[:6].upper()}",
        decision_id=override_dec.id,
        reviewer=reviewer,
        timestamp=datetime.utcnow(),
        previous_decision=last.decision,
        new_decision=new_decision,
        reason=reason,
        comments=comments
    )
    db.add(audit)
    db.commit()
    return {"override_decision": new_decision, "audit_id": audit.id, "previous": last.decision}

@router.get("/tenders/{tender_id}/audit")
def get_audit(tender_id: str, db: Session = Depends(get_db)):
    decisions = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.asc()).all()
    audits = db.query(DecisionAudit).all()
    # filter audits where decision tender matches
    # need join: audits where decision_id in decisions ids
    dec_ids = [d.id for d in decisions]
    filtered_audits = [a for a in audits if a.decision_id in dec_ids]
    return {"decisions": decisions, "audits": filtered_audits}

@router.get("/tenders/{tender_id}/export")
def export_json(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    reqs = db.query(Requirement).filter(Requirement.tender_id == tender_id).all()
    status_results = evaluate_all(db, tender_id)
    dec = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not dec:
        dec, status_results = get_or_create_decision(db, tender_id)
    risks = db.query(Risk).filter(Risk.tender_id == tender_id).all()
    missing = (
        db.query(MissingEvidence)
        .join(Requirement, MissingEvidence.requirement_id == Requirement.id)
        .filter(Requirement.tender_id == tender_id)
        .all()
    )

    evidences = (
        db.query(Evidence)
        .outerjoin(Requirement, Evidence.requirement_id == Requirement.id)
        .filter(
            or_(
                Requirement.tender_id == tender_id,
                Evidence.tender_source_id == tender_id,
            )
        )
        .all()
    )
    return {
        "tender": {"id": tender.id, "title": tender.title, "client": tender.client, "location": tender.location},
        "decision": {"decision": dec.decision, "confidence": dec.confidence, "decision_id": dec.id, "timestamp": str(dec.timestamp), "rules_triggered": dec.rules_triggered, "hard_fail_count": dec.hard_fail_count, "mandatory_missing_evidence_count": dec.mandatory_missing_count, "top_blockers": dec.top_blockers, "top_risks": dec.top_risks},
        "requirements": [
            {
                "requirement_id": r.id,
                "category": r.category,
                "requirement": r.requirement,
                "mandatory": r.mandatory,
                "requirement_type": r.requirement_type,
                "status": status_results.get(r.id, {}).get("status"),
                "evidence_ids": status_results.get(r.id, {}).get("evidence_ids"),
                "reason": status_results.get(r.id, {}).get("reason"),
                "provenance": status_results.get(r.id, {}).get("provenance"),
                "source_document": r.source_document,
                "page_or_section": r.page_or_section
            } for r in reqs
        ],
        "evidences": [{"id": e.id, "requirement_id": e.requirement_id, "fact": e.fact, "status": e.status, "source_document": e.source_document, "page_or_section": e.page_or_section, "extraction_confidence": e.extraction_confidence} for e in evidences],
        "risks": [{"id": r.id, "type": r.type, "severity": r.severity, "description": r.description, "mitigation": r.mitigation, "decision_impact": r.decision_impact, "source_requirement": r.source_requirement} for r in risks],
        "missing_evidence": [{"id": m.id, "requirement_id": m.requirement_id, "document_needed": m.document_needed, "priority": m.priority, "owner": m.owner, "why_needed": m.why_needed, "status": m.status} for m in missing],
        "provenance_chain": "Requirement → Evidence → Source Document → Page/Section → Rule → Decision"
    }

@router.get("/tenders/{tender_id}/explanation")
def get_explanation(tender_id: str, db: Session = Depends(get_db)):
    dec = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not dec:
        dec, status_results = get_or_create_decision(db, tender_id)
    else:
        status_results = evaluate_all(db, tender_id)
    exp = build_explanation(db, tender_id, dec, status_results)
    return exp

@router.get("/company/{company_id}")
def get_company(company_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    # Evaluation evidence of every account shares the working company id, so
    # only the curated demo company is readable outside dev / the env admin.
    if company_id != DEMO_COMPANY_ID and not (user.get("auth_disabled") or is_admin(user)):
        raise HTTPException(status_code=404, detail="Company not found")
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Company not found")
    docs = db.query(Evidence).filter(Evidence.company_id == company_id).all()
    return {"company": c, "evidences": docs}

# ---- Stage 5C: company documents + evaluation (decision for uploaded tenders)
_COMPANY_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".md", ".csv",
                 ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp",
                 ".zip", ".rar", ".7z", ".dxf", ".bak"}


@router.get("/company-documents")
def list_company_documents(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.engines.tender_bridge import COMPANY_ID
    q = db.query(CompanyDocument).filter(CompanyDocument.company_id == COMPANY_ID)
    flt = owner_filter(CompanyDocument.owner_email, user)
    docs = (q.filter(flt) if flt is not None else q).all()
    return {"documents": [{"id": d.id, "title": d.title, "document_type": d.document_type} for d in docs],
            "count": len(docs)}


@router.post("/company-documents")
def upload_company_documents(files: List[UploadFile] = File(...), db: Session = Depends(get_db),
                             user: dict = Depends(require_auth)):
    from app.engines.tender_bridge import COMPANY_ID, ensure_company
    ensure_company(db)
    root = (get_storage_root() / "_company").resolve()
    root.mkdir(parents=True, exist_ok=True)
    created = []
    for f in files:
        name = re.sub(r"[\x00-\x1f\x7f<>\"'&/\\]", "", Path(f.filename or "").name).strip()
        if not name or name in (".", ".."):
            raise HTTPException(status_code=400, detail="Invalid filename")
        ext = Path(name).suffix.lower()
        if ext not in _COMPANY_EXTS:
            raise HTTPException(status_code=400, detail=f"Unsupported company document type: {ext or 'none'}")
        doc_id = f"CDOC-{uuid.uuid4().hex[:8].upper()}"
        # Stored under a generated name: the user filename never touches the path.
        dest = root / f"{doc_id}{ext}"
        _stream_to_disk(f, dest, name)
        db.add(CompanyDocument(id=doc_id, company_id=COMPANY_ID, document_type=ext.lstrip(".").upper(),
                               title=name, source_path=str(dest), page="", section="",
                               owner_email=owner_for_new_rows(user)))
        created.append({"id": doc_id, "title": name, "document_type": ext.lstrip(".").upper()})
    db.commit()
    return {"documents": created, "count": len(created)}


@router.delete("/company-documents/{doc_id}")
def delete_company_document(doc_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    d = db.query(CompanyDocument).filter(CompanyDocument.id == doc_id).first()
    if not d or not owns(d.owner_email, user):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        p = Path(d.source_path or "")
        if p.is_file() and (get_storage_root() / "_company").resolve() in p.resolve().parents:
            p.unlink()
    except Exception:
        pass
    db.delete(d)
    db.commit()
    return {"deleted": doc_id}


@router.post("/tenders/{tender_id}/evaluate")
def start_tender_evaluation(tender_id: str, db: Session = Depends(get_db)):
    if not db.query(Tender).filter(Tender.id == tender_id).first():
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    if tender_id == "SA-2018-HV2":
        raise HTTPException(status_code=400, detail="The seeded demo tender uses curated evidence")
    from app.engines.tender_bridge import start_evaluation
    return start_evaluation(tender_id)


@router.get("/tenders/{tender_id}/evaluation")
def get_tender_evaluation(tender_id: str):
    from app.engines.tender_bridge import evaluation_status
    return evaluation_status(tender_id)


@router.get("/tenders/{tender_id}/decision-detail")
def get_decision_detail(tender_id: str, db: Session = Depends(get_db)):
    """Decision + every requirement with its status and evidence provenance (one call for the UI)."""
    if not db.query(Tender).filter(Tender.id == tender_id).first():
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    reqs = db.query(Requirement).filter(Requirement.tender_id == tender_id).all()
    if not reqs:
        # Tenders processed before Stage 5C have an analysis but no engine rows.
        from app.engines.tender_bridge import sync_requirements
        if sync_requirements(db, tender_id)["synced"]:
            get_or_create_decision(db, tender_id)
            reqs = db.query(Requirement).filter(Requirement.tender_id == tender_id).all()
    if not reqs:
        return {"tender_id": tender_id, "available": False,
                "reason": "No requirements in the decision engine yet - process the tender first."}
    dec = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not dec:
        dec, _ = get_or_create_decision(db, tender_id)
    status_results = evaluate_all(db, tender_id)
    items = []
    # Two queries for all evidence instead of two per requirement (Turaif: 2,387 requirements).
    req_ids = [r.id for r in reqs]
    matches: dict = {}
    for i in range(0, len(req_ids), 800):  # SQLite parameter limit
        for m in db.query(EvidenceMatch).filter(EvidenceMatch.requirement_id.in_(req_ids[i:i + 800])).all():
            matches.setdefault(m.requirement_id, []).append(m.evidence_id)
    ev_ids = list({e for lst in matches.values() for e in lst})
    evidence_by_id = {}
    for i in range(0, len(ev_ids), 800):
        for ev in db.query(Evidence).filter(Evidence.id.in_(ev_ids[i:i + 800])).all():
            evidence_by_id[ev.id] = ev
    for r in reqs:
        sr = status_results.get(r.id, {})
        evs = []
        for eid in matches.get(r.id, []):
            ev = evidence_by_id.get(eid)
            if ev:
                evs.append({"evidence_id": ev.id, "status": ev.status, "fact": ev.fact,
                            "source_document": ev.source_document, "page_or_section": ev.page_or_section,
                            "quote": ev.source_quote, "confidence": ev.extraction_confidence,
                            "reason": ev.notes})
        logic = r.evaluation_logic if isinstance(r.evaluation_logic, dict) else {}
        items.append({"requirement_id": r.id.split("::", 1)[-1], "category": r.category,
                      "requirement": r.requirement, "mandatory": bool(r.mandatory),
                      "requirement_type": r.requirement_type, "status": sr.get("status"),
                      "reason": sr.get("reason"), "source_document": r.source_document,
                      "page_or_section": r.page_or_section, "source_quote": logic.get("source_quote"),
                      "evidence": evs})
    counts = {}
    for it in items:
        if it["mandatory"]:
            counts[it["status"]] = counts.get(it["status"], 0) + 1
    order = {"FAIL": 0, "REVIEW": 1, "MISSING_EVIDENCE": 2, "PASS": 3}
    items.sort(key=lambda x: (not x["mandatory"], order.get(x["status"], 9), x["category"] or ""))
    return {"tender_id": tender_id, "available": True,
            "decision": {"decision": dec.decision, "confidence": dec.confidence, "decision_id": dec.id,
                         "timestamp": dec.timestamp, "rules_triggered": dec.rules_triggered,
                         "hard_fail_count": dec.hard_fail_count,
                         "mandatory_missing_count": dec.mandatory_missing_count,
                         "top_blockers": dec.top_blockers, "is_override": dec.is_override},
            "mandatory_status_counts": counts, "requirements": items}


# --- Processing Pipeline (Phase 3A) ---
from app.processing import create_processing_job, get_processing_job, process_tender, PIPELINE_VERSION, LLM_MODEL

@router.post("/tenders/{tender_id}/process")
def start_processing(tender_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        job = create_processing_job(db, tender_id)
    except ValueError as e:
        msg = str(e)
        if "already exists" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=404, detail=msg)
    # Run in background (in-process, no Redis/Celery per Phase 3A)
    background_tasks.add_task(process_tender, tender_id, job.id)
    return {"job_id": job.id, "tender_id": job.tender_id, "status": job.status, "current_stage": job.current_stage}

def _coverage_payload(job) -> dict:
    """Additive 4H coverage block. Best-effort; never breaks the endpoint."""
    try:
        from app.pipeline.jobs import resolve_coverage
        return resolve_coverage(job.documents_total, job.documents_processed,
                                job.documents_failed, job.documents_unsupported)
    except Exception:
        return {}


@router.get("/processing-jobs/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    try:
        job = get_processing_job(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    try:
        tender_owner_or_404(db, job.tender_id, user)
    except HTTPException:
        raise HTTPException(status_code=404, detail=f"Processing job {job_id} not found")
    from app.models import StageEvent
    history = db.query(StageEvent).filter(StageEvent.job_id == job_id).order_by(StageEvent.created_at).all()
    return {
        "job_id": job.id,
        "tender_id": job.tender_id,
        "status": job.status,
        "current_stage": job.current_stage,
        "progress": job.progress,
        "documents_total": job.documents_total,
        "documents_processed": job.documents_processed,
        "documents_failed": job.documents_failed,
        "documents_unsupported": job.documents_unsupported,
        "error_count": job.error_count,
        "last_error": job.last_error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "pipeline_version": job.pipeline_version,
        "model": job.model,
        "prompt_version": job.prompt_version,
        "stage_history": [{"stage": h.stage, "status": h.status, "counts": h.counts,
                           "error": h.error,
                           "created_at": h.created_at.isoformat() if h.created_at else None}
                          for h in history],
        # Stage 4H additive coverage (never alters status derivation)
        **_coverage_payload(job),
    }
    return ret

@router.get("/tenders/{tender_id}/analysis")
def get_analysis(tender_id: str, db: Session = Depends(get_db)):
    from app.models import TenderAnalysis
    # Check if processing is complete
    latest_job = db.query(ProcessingJob).filter(ProcessingJob.tender_id == tender_id).order_by(ProcessingJob.created_at.desc()).first()
    if not latest_job:
        raise HTTPException(status_code=404, detail="No processing job found for tender")
    if latest_job.status in ("QUEUED", "PROCESSING"):
        return {"status": latest_job.status, "current_stage": latest_job.current_stage, "progress": latest_job.progress,
                "message": "Processing not complete",
                # Live counts for the workspace while the job runs (Stage 5G).
                "processing": {"job_id": latest_job.id, "status": latest_job.status,
                               "current_stage": latest_job.current_stage, "progress": latest_job.progress,
                               "documents_total": latest_job.documents_total,
                               "documents_processed": latest_job.documents_processed,
                               "documents_failed": latest_job.documents_failed,
                               "documents_unsupported": latest_job.documents_unsupported}}
    if latest_job.status == "FAILED":
        return {"status": "FAILED", "last_error": latest_job.last_error, "error_count": latest_job.error_count}
    # For COMPLETED/PARTIAL, return persisted canonical analysis
    analysis = db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id).order_by(TenderAnalysis.created_at.desc()).first()
    if not analysis:
        # Fallback to processing metadata if no persisted analysis (e.g., old jobs)
        tender = db.query(Tender).filter(Tender.id == tender_id).first()
        if not tender:
            raise HTTPException(status_code=404, detail="Tender not found")
        return {
            "tender_id": tender_id,
            "status": latest_job.status,
            "current_stage": latest_job.current_stage,
            "progress": latest_job.progress,
            "documents_total": latest_job.documents_total,
            "documents_processed": latest_job.documents_processed,
            "documents_failed": latest_job.documents_failed,
            "message": "Analysis ready (generic extraction available via evaluation/generic_extraction.py)",
            "pipeline_version": latest_job.pipeline_version,
        }
    # Stage 5H: open review items / questions, so the workspace needs no extra call.
    review = None
    try:
        from app.issues import sync_issues
        from app.models import TenderIssue
        sync_issues(db, tender_id)
        open_items = db.query(TenderIssue.category).filter(TenderIssue.tender_id == tender_id,
                                                           TenderIssue.status == "OPEN").all()
        review = {"missing_open": sum(1 for (c,) in open_items if c == "missing"),
                  "question_open": sum(1 for (c,) in open_items if c == "question")}
    except Exception:
        db.rollback()
    # Return canonical analysis — frontend-safe, no raw LLM, no candidate IDs
    return {
        "review": review,
        "tender": analysis.tender,
        "documents": analysis.documents,
        "requirements": analysis.requirements,
        "evidence": analysis.evidence,
        "deadlines": analysis.deadlines,
        "commercial": analysis.commercial,
        "risks": analysis.risks,
        "derived_features": analysis.derived_features,
        "processing": analysis.processing,
        "analysis_version": analysis.analysis_version,
        "pipeline_version": analysis.pipeline_version,
        "model": analysis.model,
        "prompt_version": analysis.prompt_version,
        "status": analysis.status,
        "created_at": analysis.created_at,
    }


# ---- Stage 5H: review items (missing) + Q&A (questions) + notifications
@router.get("/tenders/{tender_id}/issues")
def list_tender_issues(tender_id: str, category: Optional[str] = None, status: Optional[str] = None,
                       db: Session = Depends(get_db)):
    from app.issues import sync_issues, issue_dict
    from app.models import TenderIssue
    if not db.query(Tender).filter(Tender.id == tender_id).first():
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    sync_issues(db, tender_id)  # picks up new analysis / evaluation results
    q = db.query(TenderIssue).filter(TenderIssue.tender_id == tender_id)
    if category:
        q = q.filter(TenderIssue.category == category)
    if status:
        q = q.filter(TenderIssue.status == status.upper())
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items = sorted(q.all(), key=lambda i: (i.status != "OPEN", order.get(i.priority or "", 3), i.created_at or datetime.min))
    return {"tender_id": tender_id, "issues": [issue_dict(i) for i in items],
            "open": sum(1 for i in items if i.status == "OPEN"), "count": len(items)}


@router.patch("/issues/{issue_id}")
def update_issue(issue_id: str, payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.issues import issue_dict
    from app.access import can_write_tender
    from app.models import TenderIssue
    i = db.query(TenderIssue).filter(TenderIssue.id == issue_id).first()
    t = db.query(Tender).filter(Tender.id == i.tender_id).first() if i else None
    if not i or not t or not can_write_tender(t, user):
        raise HTTPException(status_code=404, detail="Issue not found")
    if "answer" in payload:
        ans = str(payload.get("answer") or "").strip()
        if len(ans) > 4000:
            raise HTTPException(status_code=400, detail="Answer too long (max 4000 characters)")
        i.answer = ans or None
    if "status" in payload:
        st = str(payload.get("status") or "").upper()
        if st not in ("OPEN", "RESOLVED"):
            raise HTTPException(status_code=400, detail="status must be OPEN or RESOLVED")
        i.status = st
        i.resolved_at = datetime.utcnow() if st == "RESOLVED" else None
        i.resolved_by = user.get("email") if st == "RESOLVED" else None
    db.commit()
    return issue_dict(i)


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """Open review items ("missing") across this account's tenders."""
    from app.issues import sync_issues, issue_dict
    from app.models import TenderIssue
    q = db.query(Tender)
    flt = owner_filter(Tender.owner_email, user)
    tenders = (q.filter(flt) if flt is not None else q).all()
    items = []
    for t in tenders:
        if t.id == "SA-2018-HV2":
            continue  # curated demo, not a live tender
        try:
            sync_issues(db, t.id)
        except Exception:
            db.rollback()
        items.extend(db.query(TenderIssue).filter(TenderIssue.tender_id == t.id,
                                                  TenderIssue.category.in_(("missing", "info")),
                                                  TenderIssue.status == "OPEN").all())
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    items.sort(key=lambda i: (order.get(i.priority or "", 3), i.tender_id, i.created_at or datetime.min))
    return {"count": len(items), "notifications": [issue_dict(i) for i in items[:200]]}


# ---- Stage 5H: tender news from official sources
@router.get("/news")
def list_news(country: Optional[str] = None, q: Optional[str] = None, relevant: bool = True,
              limit: int = 100, sort: str = "date", db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import NewsItem
    from app import news as _news
    query = db.query(NewsItem)
    from app.news import COUNTRY_NAMES  # target market: Egypt + GCC (older rows from other countries hidden)
    query = query.filter(NewsItem.country.in_(COUNTRY_NAMES) | NewsItem.country.is_(None))
    if relevant:
        query = query.filter(NewsItem.relevant.is_(True))
    if country:
        query = query.filter(NewsItem.country == country)
    if q:
        like = f"%{q.strip()[:100]}%"
        query = query.filter((NewsItem.title.ilike(like)) | (NewsItem.description.ilike(like)))
    rows = query.order_by(NewsItem.published_at.desc().nullslast()).limit(max(1, min(limit, 500))).all()
    countries = sorted({c for (c,) in db.query(NewsItem.country).distinct() if c})
    from app.eligibility import capability_dict
    from app.models import CompanyCapability
    from app.radar import match, summary
    cap = capability_dict(db.query(CompanyCapability).filter(CompanyCapability.id == _profile_key(user)).first())
    items = [{"id": n.id, "source": n.source, "title": n.title, "description": n.description,
              "country": n.country, "notice_type": n.notice_type, "organization": n.organization,
              "url": n.url, "relevant": bool(n.relevant),
              "published_at": n.published_at.isoformat() if n.published_at else None,
              "deadline_at": n.deadline_at.isoformat() if n.deadline_at else None} for n in rows]
    for it in items:
        it["fit"] = match(it, cap)
    if sort == "match":
        items.sort(key=lambda i: -(i["fit"]["match"] if i["fit"]["match"] is not None else -1))
    return {"items": items, "summary": summary(items), "capabilities_set": bool(cap),
            "count": len(rows), "countries": countries, "last_refresh": _news.last_refresh(),
            "sources": ["World Bank procurement notices (official API)"] +
                       [h for h in sorted(_news._allowed_hosts())]}


@router.post("/news/refresh")
def refresh_news():
    from app import news as _news
    return _news.refresh()


# ---- Stage 5I: subcontractor RFQs and quotation comparison
def _rfq_dict(r, quotes=None):
    from app.subcontractors import score_quotations
    qs = score_quotations([{"id": q.id, "contractor": q.contractor, "price": q.price,
                            "duration_weeks": q.duration_weeks, "technical_fit": q.technical_fit,
                            "payment_terms_days": q.payment_terms_days, "notes": q.notes,
                            "selected": bool(q.selected)} for q in (quotes or [])])
    return {"id": r.id, "tender_id": r.tender_id, "reference": r.reference, "package_name": r.package_name,
            "discipline": r.discipline, "scope": r.scope, "currency": r.currency or "SAR", "status": r.status,
            "invited_count": int(r.invited_count) if r.invited_count is not None else None,
            "closes_at": r.closes_at.isoformat() if r.closes_at else None,
            "quoted_count": len(qs), "quotations": sorted(qs, key=lambda q: -q["score"])}


def _num(payload, key, lo=0.0, hi=None, required=True):
    v = payload.get(key)
    if v in (None, ""):
        if required:
            raise HTTPException(status_code=400, detail=f"{key} is required")
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{key} must be a number")
    if v < lo or (hi is not None and v > hi):
        raise HTTPException(status_code=400, detail=f"{key} out of range")
    return v


def _owned_rfq(db, rfq_id, user, write=False):
    from app.access import can_read_tender, can_write_tender
    from app.models import Rfq
    r = db.query(Rfq).filter(Rfq.id == rfq_id).first()
    t = db.query(Tender).filter(Tender.id == r.tender_id).first() if r else None
    if not r or not t or not can_read_tender(t, user) or (write and not can_write_tender(t, user)):
        raise HTTPException(status_code=404, detail="RFQ not found")
    return r


@router.get("/rfqs")
def list_rfqs(tender_id: Optional[str] = None, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import Rfq, Quotation
    tq = db.query(Tender)
    flt = owner_filter(Tender.owner_email, user)
    visible = {t.id for t in (tq.filter(flt) if flt is not None else tq).all()}
    q = db.query(Rfq).filter(Rfq.tender_id.in_(visible))
    if tender_id:
        q = q.filter(Rfq.tender_id == tender_id)
    rfqs = q.order_by(Rfq.created_at.desc()).all()
    return {"rfqs": [_rfq_dict(r, db.query(Quotation).filter(Quotation.rfq_id == r.id).all()) for r in rfqs]}


@router.post("/tenders/{tender_id}/rfqs")
def create_rfq(tender_id: str, payload: dict, db: Session = Depends(get_db)):
    from app.models import Rfq
    if not db.query(Tender).filter(Tender.id == tender_id).first():
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    name = str(payload.get("package_name") or "").strip()[:200]
    ref = str(payload.get("reference") or "").strip()[:60]
    if not name or not ref:
        raise HTTPException(status_code=400, detail="package_name and reference are required")
    closes = None
    if payload.get("closes_at"):
        try:
            closes = datetime.fromisoformat(str(payload["closes_at"])[:19])
        except ValueError:
            raise HTTPException(status_code=400, detail="closes_at must be a date (YYYY-MM-DD)")
    r = Rfq(id=f"RFQ-{uuid.uuid4().hex[:10].upper()}", tender_id=tender_id, reference=ref, package_name=name,
            discipline=(str(payload.get("discipline") or "").strip()[:80] or None),
            scope=(str(payload.get("scope") or "").strip()[:1000] or None),
            invited_count=_num(payload, "invited_count", 0, 1000, required=False), closes_at=closes,
            currency=(str(payload.get("currency") or "SAR").upper()[:3]))
    db.add(r)
    db.commit()
    return _rfq_dict(r, [])


@router.delete("/rfqs/{rfq_id}")
def delete_rfq(rfq_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import Quotation
    r = _owned_rfq(db, rfq_id, user, write=True)
    db.query(Quotation).filter(Quotation.rfq_id == r.id).delete()
    db.delete(r)
    db.commit()
    return {"deleted": rfq_id}


@router.post("/rfqs/{rfq_id}/quotations")
def add_quotation(rfq_id: str, payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import Quotation
    r = _owned_rfq(db, rfq_id, user, write=True)
    contractor = str(payload.get("contractor") or "").strip()[:200]
    if not contractor:
        raise HTTPException(status_code=400, detail="contractor is required")
    q = Quotation(id=f"QT-{uuid.uuid4().hex[:10].upper()}", rfq_id=r.id, contractor=contractor,
                  price=_num(payload, "price", 0.01), duration_weeks=_num(payload, "duration_weeks", 0.1, 520),
                  technical_fit=_num(payload, "technical_fit", 0, 100),
                  payment_terms_days=_num(payload, "payment_terms_days", 0, 3650),
                  notes=(str(payload.get("notes") or "").strip()[:2000] or None))
    db.add(q)
    db.commit()
    return _rfq_dict(r, db.query(Quotation).filter(Quotation.rfq_id == r.id).all())


@router.delete("/quotations/{quote_id}")
def delete_quotation(quote_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import Quotation
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    r = _owned_rfq(db, q.rfq_id, user, write=True)
    db.delete(q)
    db.commit()
    return _rfq_dict(r, db.query(Quotation).filter(Quotation.rfq_id == r.id).all())


@router.post("/quotations/{quote_id}/select")
def select_quotation(quote_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import Quotation
    q = db.query(Quotation).filter(Quotation.id == quote_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Quotation not found")
    r = _owned_rfq(db, q.rfq_id, user, write=True)
    for other in db.query(Quotation).filter(Quotation.rfq_id == r.id).all():
        other.selected = other.id == q.id
    r.status = "AWARDED"
    db.commit()
    return _rfq_dict(r, db.query(Quotation).filter(Quotation.rfq_id == r.id).all())


@router.get("/rfqs/{rfq_id}/draft")
def rfq_draft(rfq_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.subcontractors import draft_rfq_text
    r = _owned_rfq(db, rfq_id, user)
    t = db.query(Tender).filter(Tender.id == r.tender_id).first()
    a = (db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == r.tender_id)
         .order_by(TenderAnalysis.created_at.desc()).first())
    return draft_rfq_text(_rfq_dict(r), {"id": t.id, "title": t.title}, (a.requirements if a else []) or [])


# ---- Stage 5I: problem reports / suggestions and plan-upgrade requests
@router.post("/feedback")
def send_feedback(payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import Feedback
    msg = str(payload.get("message") or "").strip()
    kind = str(payload.get("kind") or "problem")
    if kind not in ("problem", "suggestion", "upgrade"):
        raise HTTPException(status_code=400, detail="kind must be problem, suggestion or upgrade")
    if not msg and kind != "upgrade":
        raise HTTPException(status_code=400, detail="Please describe the problem")
    f = Feedback(id=f"FB-{uuid.uuid4().hex[:10].upper()}", user_email=user.get("email"), kind=kind,
                 message=(msg or f"Upgrade request: {payload.get('plan')}")[:4000],
                 page=(str(payload.get("page") or "")[:300] or None),
                 plan=(str(payload.get("plan") or "")[:40] or None))
    db.add(f)
    db.commit()
    return {"id": f.id, "status": f.status, "created_at": f.created_at.isoformat()}


@router.get("/feedback")
def my_feedback(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import Feedback
    rows = (db.query(Feedback).filter(Feedback.user_email == user.get("email"))
            .order_by(Feedback.created_at.desc()).limit(50).all())
    return {"items": [{"id": f.id, "kind": f.kind, "message": f.message, "plan": f.plan, "status": f.status,
                       "created_at": f.created_at.isoformat()} for f in rows]}


# ---- Stage 5J: company profile, bid recommendation, first-draft email
_PROFILE_FIELDS = ("name", "intro", "contact_name", "contact_title", "email", "phone", "website", "address")


def _profile_key(user):
    return user.get("email") if not user.get("auth_disabled") else "local"


def _profile_dict(p):
    return {k: getattr(p, k) for k in _PROFILE_FIELDS} if p else {k: None for k in _PROFILE_FIELDS}


@router.get("/company-profile")
def get_company_profile(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import CompanyProfile
    return _profile_dict(db.query(CompanyProfile).filter(CompanyProfile.id == _profile_key(user)).first())


@router.put("/company-profile")
def put_company_profile(payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import CompanyProfile
    key = _profile_key(user)
    p = db.query(CompanyProfile).filter(CompanyProfile.id == key).first() or CompanyProfile(id=key)
    limits = {"intro": 2000, "address": 400}
    for k in _PROFILE_FIELDS:
        if k in payload:
            v = str(payload.get(k) or "").strip()[:limits.get(k, 200)]
            setattr(p, k, v or None)
    p.updated_at = datetime.utcnow()
    db.merge(p)
    db.commit()
    return _profile_dict(p)


# ---- Account type: a company (team, votes, approvals) or an individual professional
ACCOUNT_TYPES = ("company", "individual")


@router.get("/account")
def get_account(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import CompanyProfile
    p = db.query(CompanyProfile).filter(CompanyProfile.id == _profile_key(user)).first()
    return {"account_type": (p.account_type if p and p.account_type in ACCOUNT_TYPES else "company")}


@router.put("/account")
def put_account(payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import CompanyProfile
    kind = str(payload.get("account_type") or "").strip().lower()
    if kind not in ACCOUNT_TYPES:
        raise HTTPException(status_code=422, detail="account_type must be company or individual")
    key = _profile_key(user)
    p = db.query(CompanyProfile).filter(CompanyProfile.id == key).first() or CompanyProfile(id=key)
    p.account_type = kind
    p.updated_at = datetime.utcnow()
    db.merge(p)
    db.commit()
    return {"account_type": kind}


# Internal review lists the tender owner cannot act on — never put in the email.
_EMAIL_SKIP = {"unclassified-requirement", "evidence-missing", "ineligible"}


def _open_issues(db, tender_id, category, skip_kinds=()):
    from app.models import TenderIssue
    return [{"title": i.title, "detail": i.detail, "source_document": i.source_document, "page": i.page}
            for i in db.query(TenderIssue).filter(TenderIssue.tender_id == tender_id, TenderIssue.category == category,
                                                  TenderIssue.status == "OPEN").all()
            if i.kind not in skip_kinds]


@router.get("/tenders/{tender_id}/recommendation")
def tender_recommendation(tender_id: str, lang: str = "en", db: Session = Depends(get_db),
                          user: dict = Depends(require_auth)):
    from app.recommendation import build_recommendation
    from app.issues import sync_issues
    if not db.query(Tender).filter(Tender.id == tender_id).first():
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    try:
        detail = get_decision_detail(tender_id, db)
    except HTTPException:
        detail = None
    a = db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id).order_by(TenderAnalysis.created_at.desc()).first()
    analysis = {"deadlines": a.deadlines, "risks": a.risks} if a else None
    try:
        sync_issues(db, tender_id)
    except Exception:
        db.rollback()
    review = {"missing_open": len(_open_issues(db, tender_id, "missing")),
              "question_open": len(_open_issues(db, tender_id, "question"))}
    rec = build_recommendation(detail, analysis, review, lang)
    try:
        rec["score"] = _score_for(db, tender_id, user, rec, detail)
    except Exception:  # the recommendation must still load if a score input is broken
        db.rollback()
        rec["score"] = None
    return rec


@router.get("/tenders/{tender_id}/email-draft")
def tender_email_draft(tender_id: str, lang: str = "en", db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.recommendation import build_email
    from app.models import CompanyProfile
    t = db.query(Tender).filter(Tender.id == tender_id).first()
    if not t:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    prof = db.query(CompanyProfile).filter(CompanyProfile.id == _profile_key(user)).first()
    draft = build_email({"id": t.id, "title": t.title, "client": t.client}, _profile_dict(prof) if prof else None,
                        _open_issues(db, tender_id, "question", _EMAIL_SKIP),
                        _open_issues(db, tender_id, "missing", _EMAIL_SKIP), lang)
    return {**draft, "company_profile_complete": bool(prof and prof.name)}


# ---- Stage 6: company capabilities + eligibility gate
_CAP_LISTS = ("work_types", "countries", "registrations", "certifications")
_CAP_NUMS = ("max_kv", "years_experience", "annual_turnover")


@router.get("/company-capability")
def get_company_capability(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.eligibility import capability_dict
    from app.models import CompanyCapability
    cap = db.query(CompanyCapability).filter(CompanyCapability.id == _profile_key(user)).first()
    return capability_dict(cap) or {k: [] for k in _CAP_LISTS} | {k: None for k in _CAP_NUMS + ("turnover_currency",)}


@router.put("/company-capability")
def put_company_capability(payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.eligibility import capability_dict
    from app.models import CompanyCapability
    from app.tender_facts import WORK_TYPES
    key = _profile_key(user)
    cap = db.query(CompanyCapability).filter(CompanyCapability.id == key).first() or CompanyCapability(id=key)
    for k in _CAP_LISTS:
        if k in payload:
            raw = payload.get(k) or []
            if not isinstance(raw, list):
                raise HTTPException(status_code=422, detail=f"{k} must be a list")
            items = [str(x).strip()[:120] for x in raw if str(x).strip()][:30]
            if k == "work_types":
                bad = [x for x in items if x not in WORK_TYPES]
                if bad:
                    raise HTTPException(status_code=422, detail=f"Unknown work type(s): {', '.join(bad)}")
            setattr(cap, k, items)
    for k in _CAP_NUMS:
        if k in payload:
            v = payload.get(k)
            try:
                v = None if v in (None, "") else float(v)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{k} must be a number")
            if v is not None and v < 0:
                raise HTTPException(status_code=422, detail=f"{k} must not be negative")
            setattr(cap, k, v)
    if "turnover_currency" in payload:
        cap.turnover_currency = (str(payload.get("turnover_currency") or "").strip().upper()[:3]) or None
    cap.updated_at = datetime.utcnow()
    db.merge(cap)
    db.commit()
    return capability_dict(cap)


@router.get("/tenders/{tender_id}/eligibility")
def tender_eligibility(tender_id: str, db: Session = Depends(get_db)):
    from app.eligibility import result_dict
    from app.models import EligibilityResult
    return result_dict(db.query(EligibilityResult).filter(EligibilityResult.tender_id == tender_id).first()) \
        or {"status": None, "checks": []}


@router.post("/tenders/{tender_id}/eligibility/override")
def tender_eligibility_override(tender_id: str, payload: dict, background_tasks: BackgroundTasks,
                                db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """The manager continues with an ineligible tender: record who/why, then run the full analysis
    (extracted text is cached, so only the AI part is new work)."""
    from app.models import EligibilityResult
    row = db.query(EligibilityResult).filter(EligibilityResult.tender_id == tender_id).first()
    if row is None or row.status != "INELIGIBLE":
        raise HTTPException(status_code=409, detail="Tender is not blocked by the eligibility check")
    reason = str(payload.get("reason") or "").strip()[:1000]
    if not reason:
        raise HTTPException(status_code=422, detail="reason is required")
    # audit trail: the signed-in account, plus the name typed by the manager (shared login)
    row.override_by = _profile_key(user)
    row.override_name = str(payload.get("by") or "").strip()[:120] or None
    row.override_reason, row.overridden_at = reason, datetime.utcnow()
    db.commit()
    from app.audit import log as _audit
    _audit(db, tender_id, "eligibility_override", {"reason": reason}, user, row.override_name)
    try:
        job = create_processing_job(db, tender_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    background_tasks.add_task(process_tender, tender_id, job.id)
    return {"job_id": job.id, "status": job.status}


# ---- Stage 6: RFP sections and past suppliers
def _account_tender_ids(db, user) -> list:
    q = db.query(Tender.id)
    f = owner_filter(Tender.owner_email, user)
    if f is not None:
        q = q.filter(f)
    return [tid for (tid,) in q.all()]


@router.get("/tenders/{tender_id}/sections")
def tender_sections_endpoint(tender_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.sections import suppliers_by_discipline, tender_sections
    if db.query(Tender).filter(Tender.id == tender_id).first() is None:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    secs = tender_sections(tender_id)
    sup = suppliers_by_discipline(db, [t for t in _account_tender_ids(db, user) if t != tender_id])
    disciplines = {}
    for s in secs:
        d = disciplines.setdefault(s["discipline"], {"discipline": s["discipline"], "sections": 0, "pages": 0,
                                                     "suppliers": sup.get(s["discipline"], [])})
        d["sections"] += 1
        d["pages"] += s["page_to"] - s["page_from"] + 1
    return {"sections": [dict(s, suppliers=sup.get(s["discipline"], [])) for s in secs],
            "disciplines": sorted(disciplines.values(), key=lambda d: -d["pages"])}


# ---- Stage 6: team (one shared login), tasks, department votes, outcome
def _owned(q, column, user):
    f = owner_filter(column, user)
    return q.filter(f) if f is not None else q


def _member_dict(m):
    return {"id": m.id, "name": m.name, "department": m.department, "role": m.role}


def _clean(payload, key, limit=120, required=False):
    v = str(payload.get(key) or "").strip()[:limit]
    if required and not v:
        raise HTTPException(status_code=422, detail=f"{key} is required")
    return v or None


@router.get("/team")
def list_team(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import TeamMember
    rows = _owned(db.query(TeamMember), TeamMember.owner_email, user).order_by(TeamMember.name).all()
    return [_member_dict(m) for m in rows]


@router.post("/team")
def add_team_member(payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import TeamMember
    m = TeamMember(id=f"TM-{uuid.uuid4().hex[:8].upper()}", owner_email=owner_for_new_rows(user),
                   name=_clean(payload, "name", required=True), department=_clean(payload, "department"),
                   role=_clean(payload, "role"))
    db.add(m)
    db.commit()
    return _member_dict(m)


def _get_member(db, member_id, user):
    from app.models import TeamMember
    m = _owned(db.query(TeamMember).filter(TeamMember.id == member_id), TeamMember.owner_email, user).first()
    if m is None:
        raise HTTPException(status_code=404, detail="Team member not found")
    return m


@router.put("/team/{member_id}")
def update_team_member(member_id: str, payload: dict, db: Session = Depends(get_db),
                       user: dict = Depends(require_auth)):
    m = _get_member(db, member_id, user)
    for k in ("name", "department", "role"):
        if k in payload:
            setattr(m, k, _clean(payload, k, required=(k == "name")))
    db.commit()
    return _member_dict(m)


@router.delete("/team/{member_id}")
def delete_team_member(member_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    db.delete(_get_member(db, member_id, user))
    db.commit()
    return {"deleted": member_id}


def _task_dict(t):
    return {"id": t.id, "tender_id": t.tender_id, "title": t.title, "assignee": t.assignee,
            "department": t.department, "due_date": t.due_date.date().isoformat() if t.due_date else None,
            "status": t.status, "notes": t.notes}


def _parse_due(v):
    if not v:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail="due_date must be YYYY-MM-DD")


def _tender_or_404(db, tender_id):
    t = db.query(Tender).filter(Tender.id == tender_id).first()
    if t is None:
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    return t


@router.get("/tenders/{tender_id}/tasks")
def list_tasks(tender_id: str, db: Session = Depends(get_db)):
    from app.models import TenderTask
    _tender_or_404(db, tender_id)
    rows = db.query(TenderTask).filter(TenderTask.tender_id == tender_id).order_by(TenderTask.created_at).all()
    return [_task_dict(t) for t in rows]


@router.post("/tenders/{tender_id}/tasks")
def add_task(tender_id: str, payload: dict, db: Session = Depends(get_db)):
    from app.models import TenderTask
    _tender_or_404(db, tender_id)
    t = TenderTask(id=f"TT-{uuid.uuid4().hex[:8].upper()}", tender_id=tender_id,
                   title=_clean(payload, "title", 300, required=True), assignee=_clean(payload, "assignee"),
                   department=_clean(payload, "department"), due_date=_parse_due(payload.get("due_date")),
                   notes=_clean(payload, "notes", 2000), status="OPEN")
    db.add(t)
    db.commit()
    return _task_dict(t)


@router.put("/tenders/{tender_id}/tasks/{task_id}")
def update_task(tender_id: str, task_id: str, payload: dict, db: Session = Depends(get_db),
                user: dict = Depends(require_auth)):
    from app.models import TenderTask
    t = db.query(TenderTask).filter(TenderTask.id == task_id, TenderTask.tender_id == tender_id).first()
    if t is None:
        raise HTTPException(status_code=404, detail="Task not found")
    for k in ("title", "assignee", "department", "notes"):
        if k in payload:
            setattr(t, k, _clean(payload, k, 2000 if k == "notes" else 300, required=(k == "title")))
    if "due_date" in payload:
        t.due_date = _parse_due(payload.get("due_date"))
    if "status" in payload:
        st = str(payload.get("status") or "").upper()
        if st not in ("OPEN", "DONE"):
            raise HTTPException(status_code=422, detail="status must be OPEN or DONE")
        changed = st != t.status
        t.status, t.done_at = st, (datetime.utcnow() if st == "DONE" else None)
        if changed:
            from app.audit import log as _audit
            _audit(db, tender_id, "task_done" if st == "DONE" else "task_reopened", {"task": t.title}, user, t.assignee)
    db.commit()
    return _task_dict(t)


@router.delete("/tenders/{tender_id}/tasks/{task_id}")
def delete_task(tender_id: str, task_id: str, db: Session = Depends(get_db)):
    from app.models import TenderTask
    n = db.query(TenderTask).filter(TenderTask.id == task_id, TenderTask.tender_id == tender_id).delete()
    db.commit()
    if not n:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": task_id}


@router.get("/tasks/groups")
def task_groups(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """Similar open tasks across the account's tenders — do them once."""
    from app.models import TenderTask
    from app.team import similar_groups
    ids = _account_tender_ids(db, user)
    rows = (db.query(TenderTask).filter(TenderTask.tender_id.in_(ids), TenderTask.status == "OPEN").all()
            if ids else [])
    return similar_groups([_task_dict(t) for t in rows])


def _vote_dict(v):
    return {"member_name": v.member_name, "department": v.department, "vote": v.vote, "comment": v.comment,
            "updated_at": v.updated_at.isoformat() if v.updated_at else None}


def _votes_payload(db, tender_id):
    from app.models import DepartmentVote
    from app.team import vote_summary
    votes = [_vote_dict(v) for v in db.query(DepartmentVote).filter(DepartmentVote.tender_id == tender_id)
             .order_by(DepartmentVote.department, DepartmentVote.member_name).all()]
    return {"votes": votes, "summary": vote_summary(votes)}


@router.get("/tenders/{tender_id}/votes")
def list_votes(tender_id: str, db: Session = Depends(get_db)):
    _tender_or_404(db, tender_id)
    return _votes_payload(db, tender_id)


@router.put("/tenders/{tender_id}/votes")
def put_vote(tender_id: str, payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """The tender manager records one member's vote (insert or update)."""
    from app.models import DepartmentVote
    from app.team import VOTES
    _tender_or_404(db, tender_id)
    name = _clean(payload, "member_name", required=True)
    vote = str(payload.get("vote") or "").upper()
    if vote not in VOTES:
        raise HTTPException(status_code=422, detail="vote must be APPROVE, REJECT or ABSTAIN")
    v = db.query(DepartmentVote).filter(DepartmentVote.tender_id == tender_id,
                                        DepartmentVote.member_name == name).first()
    if v is None:
        v = DepartmentVote(id=f"DV-{uuid.uuid4().hex[:8].upper()}", tender_id=tender_id, member_name=name)
        db.add(v)
    v.department = _clean(payload, "department", required=True)
    v.vote, v.comment, v.updated_at = vote, _clean(payload, "comment", 1000), datetime.utcnow()
    db.commit()
    from app.audit import log as _audit
    _audit(db, tender_id, "vote_saved", {"member": name, "department": v.department, "vote": vote}, user, name)
    return _votes_payload(db, tender_id)


@router.delete("/tenders/{tender_id}/votes/{member_name}")
def delete_vote(tender_id: str, member_name: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import DepartmentVote
    db.query(DepartmentVote).filter(DepartmentVote.tender_id == tender_id,
                                    DepartmentVote.member_name == member_name).delete()
    db.commit()
    from app.audit import log as _audit
    _audit(db, tender_id, "vote_removed", {"member": member_name}, user)
    return _votes_payload(db, tender_id)


@router.put("/tenders/{tender_id}/outcome")
def set_outcome(tender_id: str, payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.team import OUTCOMES
    t = _tender_or_404(db, tender_id)
    o = payload.get("outcome")
    o = str(o).upper() if o else None
    if o is not None and o not in OUTCOMES:
        raise HTTPException(status_code=422, detail=f"outcome must be one of {', '.join(OUTCOMES)}")
    previous, t.outcome = t.outcome, o
    db.commit()
    from app.audit import log as _audit
    _audit(db, tender_id, "outcome_set", {"previous": previous, "new": o}, user)
    return {"tender_id": t.id, "outcome": t.outcome}


# ---- Stage 6: Go/No-Go score
def _score_for(db, tender_id, user, rec=None, detail=None):
    from app.scoring import tender_score
    t = _tender_or_404(db, tender_id)
    if rec is None:
        from app.recommendation import build_recommendation
        try:
            detail = get_decision_detail(tender_id, db)
        except HTTPException:
            detail = None
        rec = build_recommendation(detail, None, None)
    hard = int(((detail or {}).get("decision") or {}).get("hard_fail_count") or 0)
    res = tender_score(db, t, user, rec.get("match_percent"), hard)
    _LAST_SCORE[tender_id] = res  # the dashboard shows this same number
    return res


_LAST_SCORE: dict = {}


@router.get("/tenders/{tender_id}/score")
def tender_score_endpoint(tender_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    return _score_for(db, tender_id, user)


@router.get("/score-weights")
def get_score_weights(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import ScoreSettings
    from app.scoring import clean_weights
    st = db.query(ScoreSettings).filter(ScoreSettings.id == _profile_key(user)).first()
    return clean_weights(st.weights if st else None)


@router.put("/score-weights")
def put_score_weights(payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import ScoreSettings
    from app.scoring import DEFAULT_WEIGHTS, clean_weights
    for k, v in payload.items():
        if k not in DEFAULT_WEIGHTS:
            raise HTTPException(status_code=422, detail=f"Unknown factor: {k}")
        try:
            if not 0 <= float(v) <= 100:
                raise ValueError
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{k} must be a number from 0 to 100")
    if sum(float(payload.get(k, d)) for k, d in DEFAULT_WEIGHTS.items()) <= 0:
        raise HTTPException(status_code=422, detail="At least one weight must be above 0")
    w = clean_weights(payload)
    st = db.query(ScoreSettings).filter(ScoreSettings.id == _profile_key(user)).first() \
        or ScoreSettings(id=_profile_key(user))
    st.weights, st.updated_at = w, datetime.utcnow()
    db.merge(st)
    db.commit()
    return w


# ---- Stage 7: submission checklist, compliance matrix, decision pack
def _latest_analysis_row(db, tender_id):
    return (db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id)
            .order_by(TenderAnalysis.created_at.desc()).first())


def _checklist_items(db, tender_id):
    from app.checklist import build
    from app.models import SubmissionItem
    a = _latest_analysis_row(db, tender_id)
    items = build((a.requirements if a else None) or [])
    state = {r.item_key: r for r in db.query(SubmissionItem).filter(SubmissionItem.tender_id == tender_id).all()}
    for it in items:
        st = state.get(it["key"])
        it.update(status=st.status if st else "TODO", assignee=st.assignee if st else None, note=st.note if st else None)
    return items


@router.get("/tenders/{tender_id}/checklist")
def get_checklist(tender_id: str, db: Session = Depends(get_db)):
    from app.checklist import progress
    _tender_or_404(db, tender_id)
    items = _checklist_items(db, tender_id)
    return {"items": items, "progress": progress(items)}


@router.put("/tenders/{tender_id}/checklist/{item_key}")
def put_checklist_item(tender_id: str, item_key: str, payload: dict, db: Session = Depends(get_db),
                       user: dict = Depends(require_auth)):
    from app.audit import log as _audit
    from app.checklist import STATUSES
    from app.models import SubmissionItem
    _tender_or_404(db, tender_id)
    items = {i["key"]: i for i in _checklist_items(db, tender_id)}
    if item_key not in items:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    row = (db.query(SubmissionItem).filter(SubmissionItem.tender_id == tender_id, SubmissionItem.item_key == item_key)
           .first())
    if row is None:
        row = SubmissionItem(id=f"SI-{uuid.uuid4().hex[:10].upper()}", tender_id=tender_id, item_key=item_key)
        db.add(row)
    previous = row.status or "TODO"
    if "status" in payload:
        st = str(payload.get("status") or "").upper()
        if st not in STATUSES:
            raise HTTPException(status_code=422, detail="status must be TODO, READY or NOT_APPLICABLE")
        row.status = st
    for k in ("assignee", "note"):
        if k in payload:
            setattr(row, k, _clean(payload, k, 1000 if k == "note" else 120))
    row.updated_at = datetime.utcnow()
    db.commit()
    if row.status != previous:
        _audit(db, tender_id, "checklist_item", {"item": items[item_key]["title"], "previous": previous,
                                                 "new": row.status}, user, row.assignee)
    it = items[item_key]
    it.update(status=row.status, assignee=row.assignee, note=row.note)
    return it


_MATRIX_HEAD = {
    "en": ["Req ID", "Requirement (tender's words)", "Category", "Mandatory", "Source file", "Page",
           "Company evidence", "Status", "Gap", "Comment"],
    "ar": ["رقم المتطلب", "المتطلب (بنص المناقصة)", "الفئة", "إلزامي", "ملف المصدر", "الصفحة",
           "دليل الشركة", "الحالة", "الفجوة", "تعليق"],
}
_STATUS_TEXT = {
    "en": {"PASS": "Met", "FAIL": "Contradicted", "REVIEW": "Needs review", "MISSING_EVIDENCE": "No evidence",
           None: "Not evaluated"},
    "ar": {"PASS": "مستوفى", "FAIL": "متعارض", "REVIEW": "يحتاج مراجعة", "MISSING_EVIDENCE": "بلا دليل",
           None: "لم يُقيّم"},
}
_GAP_TEXT = {
    "en": {"FAIL": "Company documents contradict the requirement", "REVIEW": "Evidence found — a person must confirm it",
           "MISSING_EVIDENCE": "No company evidence found"},
    "ar": {"FAIL": "مستندات الشركة تتعارض مع المتطلب", "REVIEW": "يوجد دليل — يحتاج تأكيدًا بشريًا",
           "MISSING_EVIDENCE": "لا يوجد دليل من مستندات الشركة"},
}


def _compliance_counts(reqs):
    mand = [r for r in reqs if r.get("mandatory")]
    counts = {k: sum(1 for r in mand if r.get("status") == k) for k in ("PASS", "FAIL", "REVIEW", "MISSING_EVIDENCE")}
    counts["mandatory_total"] = len(mand)
    counts["total"] = len(reqs)
    evaluated = any(r.get("evidence") for r in mand) or counts["PASS"] or counts["FAIL"]
    counts["compliance_percent"] = round(100 * counts["PASS"] / len(mand)) if mand and evaluated else None
    return counts


@router.get("/tenders/{tender_id}/compliance-matrix.xlsx")
def compliance_matrix(tender_id: str, lang: str = "en", db: Session = Depends(get_db)):
    """The bidder's compliance matrix: every requirement with its source, company evidence and gap."""
    import io as _io
    from fastapi.responses import StreamingResponse
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    lang = "ar" if lang == "ar" else "en"
    t = _tender_or_404(db, tender_id)
    try:
        detail = get_decision_detail(tender_id, db)
    except HTTPException:
        detail = {"requirements": []}
    reqs = detail.get("requirements") or []
    counts = _compliance_counts(reqs)
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary" if lang == "en" else "الملخص"
    ar = lang == "ar"
    rows = [
        (("Tender" if not ar else "المناقصة"), f"{t.id} — {t.title or ''}"),
        (("Generated" if not ar else "تاريخ الإنشاء"), datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
        (("Requirements (all)" if not ar else "كل المتطلبات"), counts["total"]),
        (("Mandatory requirements" if not ar else "المتطلبات الإلزامية"), counts["mandatory_total"]),
    ] + [(_STATUS_TEXT[lang][k], counts[k]) for k in ("PASS", "FAIL", "REVIEW", "MISSING_EVIDENCE")] + [
        (("Compliance %" if not ar else "نسبة الامتثال"),
         f"{counts['compliance_percent']}%" if counts["compliance_percent"] is not None
         else ("Not evaluated yet" if not ar else "لم يُقيّم بعد")),
        (("Method" if not ar else "طريقة الحساب"),
         "Met mandatory requirements ÷ all mandatory requirements. 'Needs review' and 'No evidence' never count as met."
         if not ar else "المتطلبات الإلزامية المستوفاة ÷ كل المتطلبات الإلزامية. «يحتاج مراجعة» و«بلا دليل» لا تُحتسب مستوفاة أبدًا."),
    ]
    for r in rows:
        ws.append(list(r))
    for c in ws["A"]:
        c.font = Font(bold=True)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 90
    m = wb.create_sheet("Matrix" if not ar else "المصفوفة")
    m.append(_MATRIX_HEAD[lang])
    head_fill = PatternFill("solid", fgColor="162A4C")
    for c in m[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), head_fill
    fills = {"PASS": "E7F5EE", "FAIL": "FDF0F0", "REVIEW": "FDF4DE", "MISSING_EVIDENCE": "F2F4F7"}
    safe_cell = lambda v: ("'" + v) if isinstance(v, str) and v[:1] in "=+-@" else v  # no formulas from tender text
    for r in reqs:
        ev = r.get("evidence") or []
        ev_txt = "\n".join(f"{e.get('source_document') or ''} {e.get('page_or_section') or ''}: "
                           f"{str(e.get('quote') or e.get('fact') or '')[:200]}".strip() for e in ev[:3])
        st = r.get("status")
        m.append([safe_cell(x) for x in [r.get("requirement_id"), r.get("source_quote") or r.get("requirement"), r.get("category"),
                  ("Yes" if not ar else "نعم") if r.get("mandatory") else ("No" if not ar else "لا"),
                  r.get("source_document"), r.get("page_or_section"), ev_txt,
                  _STATUS_TEXT[lang].get(st, st), _GAP_TEXT[lang].get(st, ""), ""]])
        if st in fills:
            m.cell(row=m.max_row, column=8).fill = PatternFill("solid", fgColor=fills[st])
    for col, w in zip("ABCDEFGHIJ", (10, 70, 14, 10, 30, 8, 50, 16, 34, 30)):
        m.column_dimensions[col].width = w
    for row in m.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    m.freeze_panes = "A2"
    if ar:
        ws.sheet_view.rightToLeft = True
        m.sheet_view.rightToLeft = True
    buf = _io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", t.id)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="compliance-matrix-{safe}.xlsx"'})


@router.get("/tenders/{tender_id}/decision-pack")
def decision_pack(tender_id: str, lang: str = "en", db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """Everything management needs to decide, in one place — certifications first. Facts carry their source;
    the decision itself belongs to the company's authorised team."""
    from app.audit import events
    from app.certifications import find as find_certs, summary as cert_summary
    from app.checklist import progress
    from app.conflicts import tender_conflicts
    from app.eligibility import capability_for, capability_dict, result_dict
    from app.models import DepartmentVote, EligibilityResult, TenderTask
    from app.recommendation import build_recommendation
    from app.sections import sources_from_cache, suppliers_by_discipline
    from app.team import vote_summary
    t = _tender_or_404(db, tender_id)
    try:
        detail = get_decision_detail(tender_id, db)
    except HTTPException:
        detail = None
    a = _latest_analysis_row(db, tender_id)
    rec = build_recommendation(detail, {"deadlines": a.deadlines, "risks": a.risks} if a else None, None, lang)
    try:
        score = _score_for(db, tender_id, user, rec, detail)
    except Exception:
        db.rollback()
        score = None
    others = [x for x in _account_tender_ids(db, user) if x != tender_id]
    try:
        from app.certifications import tender_certifications
        certs = tender_certifications(tender_id, capability_dict(capability_for(db, t)),
                                      suppliers_by_discipline(db, others))
    except Exception:
        certs = []
    reqs = (detail or {}).get("requirements") or []
    gaps = [r for r in reqs if r.get("mandatory") and r.get("status") in ("FAIL", "MISSING_EVIDENCE", "REVIEW")]
    gaps.sort(key=lambda r: {"FAIL": 0, "REVIEW": 1, "MISSING_EVIDENCE": 2}[r["status"]])
    checklist = _checklist_items(db, tender_id)
    votes = [{"member_name": v.member_name, "department": v.department, "vote": v.vote, "comment": v.comment}
             for v in db.query(DepartmentVote).filter(DepartmentVote.tender_id == tender_id).all()]
    tasks = [_task_dict(x) for x in db.query(TenderTask).filter(TenderTask.tender_id == tender_id).all()]
    try:
        conflicts = tender_conflicts(tender_id)
    except Exception:
        conflicts = []
    return {
        "tender": {"id": t.id, "title": t.title, "client": t.client, "location": t.location, "outcome": t.outcome},
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "certifications": {"items": certs, "summary": cert_summary(certs)},
        "eligibility": result_dict(db.query(EligibilityResult).filter(EligibilityResult.tender_id == tender_id).first()),
        "score": score,
        "recommendation": {"decision": rec.get("decision"), "headline": rec.get("headline"), "notes": rec.get("notes"),
                           "sections": rec.get("sections")},
        "compliance": _compliance_counts(reqs),
        "gaps": [{k: r.get(k) for k in ("requirement_id", "requirement", "status", "source_document", "page_or_section")}
                 for r in gaps[:15]],
        "conflicts": conflicts,
        "questions": _open_issues(db, tender_id, "question", _EMAIL_SKIP),
        "missing_documents": _open_issues(db, tender_id, "missing", _EMAIL_SKIP),
        "checklist": {"items": checklist, "progress": progress(checklist)},
        "votes": {"votes": votes, "summary": vote_summary(votes)},
        "tasks": tasks,
        "audit": events(db, tender_id),
        **_pack_extras(db, t, user),
    }


def _pack_extras(db, t, user):
    """Material cost estimate, similar past tenders and key dates for the decision pack / summary."""
    from app.materials import cost_view, price_index, tender_boq
    from app.sections import sources_from_cache
    from app.similarity import for_tender
    from app.summary import key_dates
    try:
        mv = cost_view(tender_boq(t.id), price_index(_price_items(db, user)), None)
        materials = {"totals": mv["totals"], "priced": mv["priced"], "unavailable": mv["unavailable"],
                     "lines": len(mv["lines"])}
    except Exception:
        materials = {"totals": [], "priced": 0, "unavailable": 0, "lines": 0}
    try:
        similar = for_tender(db, t, user)["similar"][:3]
    except Exception:
        similar = []
    try:
        dates = [{"label": d["label"], "date": d["date"] or d["raw"], "file": d["file"], "page": d["page"]}
                 for d in key_dates(sources_from_cache(t.id))]
    except Exception:
        dates = []
    if t.submission_deadline:
        dates = [d for d in dates if d["label"] != "Submission deadline"]
        dates.insert(0, {"label": "Submission deadline", "date": t.submission_deadline.date().isoformat(),
                         "file": None, "page": None})
    final = {"decision": t.final_decision, "reason": t.final_reason, "by": t.final_by} if t.final_decision else None
    return {"materials": materials, "similar": similar, "dates": dates, "final": final}


@router.get("/tenders/{tender_id}/decision-summary")
def decision_summary(tender_id: str, lang: str = "en", to: str = "", db: Session = Depends(get_db),
                     user: dict = Depends(require_auth)):
    """A short email-ready summary for the decision maker, from the decision pack's facts only."""
    from app.decision_summary import build
    pack = decision_pack(tender_id, lang, db, user)
    m = pack["materials"]
    mat = {"lines": [None] * m["lines"], "totals": m["totals"], "priced": m["priced"]}
    return build(pack, mat, pack["similar"], pack["dates"], pack["final"], lang, to[:120])


# ---- Stage 8: quick summary, similar tenders, stage/deadline, notes, reminders, dashboard
STAGES = ("ELIGIBILITY", "STUDY", "PRICING", "SUBMISSION", "SUBMITTED", "CLOSED")


def _account_tenders(db, user, include_demo=False):
    from app.access import DEMO_TENDER_ID
    q = db.query(Tender)
    f = owner_filter(Tender.owner_email, user)
    if f is not None:
        q = q.filter(f)
    return [t for t in q.all() if include_demo or t.id != DEMO_TENDER_ID]


@router.get("/tenders/{tender_id}/summary")
def tender_summary(tender_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.summary import build
    return build(db, _tender_or_404(db, tender_id), user)


@router.get("/tenders/{tender_id}/similar")
def tender_similar(tender_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.similarity import for_tender
    return for_tender(db, _tender_or_404(db, tender_id), user)


@router.put("/tenders/{tender_id}/plan")
def set_tender_plan(tender_id: str, payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """Stage and submission deadline, set by the team (audited)."""
    from app.audit import log as _audit
    t = _tender_or_404(db, tender_id)
    changes = {}
    if "stage" in payload:
        st = str(payload.get("stage") or "").upper() or None
        if st is not None and st not in STAGES:
            raise HTTPException(status_code=422, detail=f"stage must be one of {', '.join(STAGES)}")
        if st != t.stage:
            changes["stage"] = {"previous": t.stage, "new": st}
            t.stage = st
    if "submission_deadline" in payload:
        d = _parse_due(payload.get("submission_deadline"))
        if d != t.submission_deadline:
            changes["deadline"] = {"previous": t.submission_deadline.date().isoformat() if t.submission_deadline else None,
                                   "new": d.date().isoformat() if d else None}
            t.submission_deadline = d
    db.commit()
    for k, v in changes.items():
        _audit(db, tender_id, "stage_set" if k == "stage" else "deadline_set", v, user)
    return {"stage": t.stage, "submission_deadline": t.submission_deadline.date().isoformat() if t.submission_deadline else None}


def _note_dict(n):
    return {"id": n.id, "author": n.author, "text": n.text, "created_at": n.created_at.isoformat() if n.created_at else None}


@router.get("/tenders/{tender_id}/notes")
def list_notes(tender_id: str, db: Session = Depends(get_db)):
    from app.models import TenderNote
    _tender_or_404(db, tender_id)
    return [_note_dict(n) for n in db.query(TenderNote).filter(TenderNote.tender_id == tender_id)
            .order_by(TenderNote.created_at.desc()).all()]


@router.post("/tenders/{tender_id}/notes")
def add_note(tender_id: str, payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.audit import log as _audit
    from app.models import TenderNote
    _tender_or_404(db, tender_id)
    n = TenderNote(id=f"TN-{uuid.uuid4().hex[:10].upper()}", tender_id=tender_id,
                   author=_clean(payload, "author"), text=_clean(payload, "text", 4000, required=True))
    db.add(n)
    db.commit()
    _audit(db, tender_id, "note_added", {"text": n.text[:120]}, user, n.author)
    return _note_dict(n)


@router.delete("/tenders/{tender_id}/notes/{note_id}")
def delete_note(tender_id: str, note_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.audit import log as _audit
    from app.models import TenderNote
    n = db.query(TenderNote).filter(TenderNote.id == note_id, TenderNote.tender_id == tender_id).first()
    if n is None:
        raise HTTPException(status_code=404, detail="Note not found")
    text = n.text[:120]
    db.delete(n)
    db.commit()
    _audit(db, tender_id, "note_deleted", {"text": text}, user)
    return {"deleted": note_id}


@router.get("/reminders")
def reminders(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.reminders import for_tenders
    return for_tenders(db, _account_tenders(db, user))


@router.get("/dashboard/attention")
def dashboard_attention(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """What needs the Tender Manager now, across the account's tenders."""
    from collections import Counter
    from app.models import EligibilityResult, TenderAnalysis, TenderIssue
    from app.reminders import CLOSED_STAGES, for_tenders
    from app.scoring import tender_score
    tenders = _account_tenders(db, user)
    analysed = {tid for (tid,) in db.query(TenderAnalysis.tender_id).distinct().all()}
    blocked, awaiting, history = [], [], []
    for t in tenders:
        el = db.query(EligibilityResult).filter(EligibilityResult.tender_id == t.id).first()
        if el is not None and el.status == "INELIGIBLE" and not el.override_by:
            blocked.append({"id": t.id, "title": t.title})
            continue
        if t.id in analysed and not t.outcome and t.stage not in CLOSED_STAGES:
            sc = _LAST_SCORE.get(t.id)  # computed when the tender's score was last shown
            awaiting.append({"id": t.id, "title": t.title, "stage": t.stage,
                             "deadline": t.submission_deadline.date().isoformat() if t.submission_deadline else None,
                             "score": sc.get("score") if sc else None, "band": sc.get("band") if sc else None})
        hit = (db.query(TenderIssue).filter(TenderIssue.tender_id == t.id, TenderIssue.kind == "client-history",
                                            TenderIssue.status == "OPEN").first())
        if hit:
            history.append({"id": t.id, "title": t.title, "message": hit.title})
    awaiting.sort(key=lambda x: (x["deadline"] or "9999", -(x["score"] or 0)))
    stages = Counter(t.stage or ("ANALYSED" if t.id in analysed else "NEW") for t in tenders)
    return {"reminders": for_tenders(db, tenders), "awaiting_decision": awaiting, "blocked": blocked,
            "client_history": history, "stages": dict(stages), "total": len(tenders)}


@router.post("/assistant/ask")
def assistant_ask(payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.assistant import answer
    q = str(payload.get("question") or "").strip()[:500]
    if not q:
        raise HTTPException(status_code=422, detail="question is required")
    tid = payload.get("tender_id") or None
    if tid:
        t = _tender_or_404(db, tid)
        from app.access import can_read_tender
        if not can_read_tender(t, user):
            raise HTTPException(status_code=404, detail="Tender not found")
    return answer(db, user, q, tid, "ar" if payload.get("lang") == "ar" else "en")


# ---- Stage 9: portfolio pages
@router.get("/portfolio/board")
def portfolio_board(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.portfolio import board
    return board(db, user, _account_tenders(db, user))


@router.get("/portfolio/approvals")
def portfolio_approvals(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.portfolio import approvals
    return approvals(db, _account_tenders(db, user))


@router.put("/tenders/{tender_id}/final-decision")
def set_final_decision(tender_id: str, payload: dict, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """The authorised team records the bid decision (GO / NO_GO), with a reason; audited."""
    from app.audit import log as _audit
    t = _tender_or_404(db, tender_id)
    d = str(payload.get("decision") or "").upper() or None
    if d is not None and d not in ("GO", "NO_GO"):
        raise HTTPException(status_code=422, detail="decision must be GO or NO_GO")
    reason = _clean(payload, "reason", 2000)
    if d and not reason:
        raise HTTPException(status_code=422, detail="reason is required")
    previous = t.final_decision
    t.final_decision, t.final_reason = d, reason if d else None
    t.final_by, t.final_at = (_clean(payload, "by") if d else None), (datetime.utcnow() if d else None)
    if d == "GO" and t.stage in (None, "ELIGIBILITY", "STUDY"):
        t.stage = "PRICING"
    if d == "NO_GO":
        t.stage, t.outcome = "CLOSED", t.outcome or "NOT_SUBMITTED"
    db.commit()
    _audit(db, tender_id, "final_decision", {"previous": previous, "new": d, "reason": reason}, user, t.final_by)
    return {"final_decision": t.final_decision, "stage": t.stage, "outcome": t.outcome}


@router.get("/portfolio/work-packages")
def portfolio_work_packages(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.portfolio import work_packages
    return work_packages(db, user, _account_tenders(db, user))


@router.get("/portfolio/documents")
def portfolio_documents(q: str = "", db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.portfolio import documents
    return documents(db, user, _account_tenders(db, user), q[:200])


@router.get("/portfolio/analytics")
def portfolio_analytics(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.portfolio import analytics
    return analytics(db, user, _account_tenders(db, user))


# ---- RFQ packages: one supplier RFQ per equipment package, built from the tender's own pages
def _rfq_package_list(db, tender_id, user):
    from app.models import Rfq
    from app.rfq_packages import tender_packages
    from app.sections import suppliers_by_discipline
    pkgs = tender_packages(tender_id)
    sup = suppliers_by_discipline(db, [t for t in _account_tender_ids(db, user) if t != tender_id])
    made = {r.package_name: r.id for r in db.query(Rfq).filter(Rfq.tender_id == tender_id).all()}
    return [dict(p, suppliers=sup.get(p["discipline"], []), rfq_id=made.get(p["name"])) for p in pkgs]


@router.get("/tenders/{tender_id}/rfq-packages")
def rfq_packages_list(tender_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    _tender_or_404(db, tender_id)
    return {"packages": _rfq_package_list(db, tender_id, user)}


def _closes_at(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="closes_at must be a date (YYYY-MM-DD)")


@router.post("/tenders/{tender_id}/rfq-packages")
def rfq_packages_create(tender_id: str, payload: dict, db: Session = Depends(get_db),
                        user: dict = Depends(require_auth)):
    """Register the chosen packages as RFQs (skips packages already registered)."""
    from app.models import Rfq
    from app.rfq_packages import scope_text
    _tender_or_404(db, tender_id)
    keys = set(payload.get("keys") or [])
    closes = _closes_at(payload.get("closes_at"))
    pkgs = [p for p in _rfq_package_list(db, tender_id, user) if not keys or p["key"] in keys]
    n = db.query(Rfq).filter(Rfq.tender_id == tender_id).count()
    created = []
    for p in pkgs:
        if p["rfq_id"]:
            continue
        n += 1
        r = Rfq(id=f"RFQ-{uuid.uuid4().hex[:10].upper()}", tender_id=tender_id, reference=f"RFQ-{n:02d}",
                package_name=p["name"][:200], discipline=p["discipline"], scope=scope_text(p), closes_at=closes,
                currency=str(payload.get("currency") or "SAR").upper()[:3])
        db.add(r)
        created.append(r.id)
    db.commit()
    return {"created": len(created), "packages": _rfq_package_list(db, tender_id, user)}


@router.get("/tenders/{tender_id}/rfq-packages.zip")
def rfq_packages_zip(tender_id: str, keys: Optional[str] = None, closes_at: Optional[str] = None,
                     db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """Folders per package: brief, scope pages, design criteria, drawings, data schedules to fill."""
    from fastapi.responses import Response
    from app.models import CompanyProfile
    from app.rfq_packages import build_zip, tender_packages
    from app.sections import sources_from_cache
    from app.summary import key_dates
    t = _tender_or_404(db, tender_id)
    wanted = {k for k in (keys or "").split(",") if k}
    pkgs = [p for p in tender_packages(tender_id) if not wanted or p["key"] in wanted]
    if not pkgs:
        raise HTTPException(status_code=404, detail="No RFQ packages found for this tender")
    files = {}
    for d in db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id).all():
        if d.source_path and Path(d.source_path).is_file():
            for name in {d.original_filename, d.title}:
                if name:
                    files[name] = d.source_path
    prof = db.query(CompanyProfile).filter(CompanyProfile.id == _profile_key(user)).first()
    data = build_zip(pkgs, files, {"id": t.id, "title": t.title, "client": t.client, "location": t.location},
                     key_dates(sources_from_cache(tender_id)), _profile_dict(prof),
                     str(_closes_at(closes_at).date()) if closes_at else None)
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", tender_id)[:60]
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="RFQs-{safe}.zip"'})


# ---- Materials: BOQ lines, supplier price lists (the only price source), estimated cost, bulk across tenders
_MAX_PRICE_FILE = 10 * 1024 * 1024


def _price_items(db, user):
    from app.models import PriceItem, PriceList
    lists = {p.id: p for p in db.query(PriceList).filter(PriceList.owner == _profile_key(user)).all()}
    if not lists:
        return []
    rows = db.query(PriceItem).filter(PriceItem.list_id.in_(list(lists))).all()
    return [{"key": r.key, "price": r.price, "currency": r.currency, "unit": r.unit, "min_qty": r.min_qty or 0,
             "list_id": r.list_id, "supplier": lists[r.list_id].supplier, "price_date": lists[r.list_id].price_date,
             "filename": lists[r.list_id].filename, "description": r.description} for r in rows]


def _price_list_dict(p):
    return {"id": p.id, "supplier": p.supplier, "currency": p.currency, "price_date": p.price_date.date().isoformat(),
            "filename": p.filename, "items": int(p.items_count or 0), "uploaded_at": p.uploaded_at.isoformat()}


@router.get("/price-lists")
def list_price_lists(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import PriceList
    rows = (db.query(PriceList).filter(PriceList.owner == _profile_key(user))
            .order_by(PriceList.price_date.desc()).all())
    return {"lists": [_price_list_dict(p) for p in rows]}


@router.post("/price-lists")
def upload_price_list(supplier: str = Form(...), currency: str = Form(...), price_date: str = Form(...),
                      file: UploadFile = File(...), db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """A supplier's price sheet (xlsx / csv): description, unit, price[, currency][, min qty]."""
    import tempfile
    from app.materials import parse_price_rows, read_sheet
    from app.models import PriceItem, PriceList
    supplier, currency = supplier.strip()[:200], currency.strip().upper()[:3]
    if not supplier or len(currency) != 3:
        raise HTTPException(status_code=400, detail="supplier and a 3-letter currency are required")
    try:
        when = datetime.fromisoformat(price_date.strip()[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="price_date must be a date (YYYY-MM-DD)")
    name = Path(file.filename or "prices.xlsx").name
    if not name.lower().endswith((".xlsx", ".xlsm", ".csv")):
        raise HTTPException(status_code=400, detail="Upload an Excel (.xlsx) or CSV price list")
    data = file.file.read(_MAX_PRICE_FILE + 1)
    if len(data) > _MAX_PRICE_FILE:
        raise HTTPException(status_code=413, detail="Price list is larger than 10 MB")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / name
        path.write_bytes(data)
        try:
            items = parse_price_rows(read_sheet(str(path)), currency)
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read the price list")
    if not items:
        raise HTTPException(status_code=400, detail="No priced rows found — the sheet needs Description and Price columns")
    pl = PriceList(id=f"PL-{uuid.uuid4().hex[:10].upper()}", owner=_profile_key(user), supplier=supplier,
                   currency=currency, price_date=when, filename=name, items_count=len(items))
    db.add(pl)
    for it in items:
        db.add(PriceItem(id=f"PI-{uuid.uuid4().hex[:12].upper()}", list_id=pl.id, description=it["description"],
                         unit=it["unit"], price=it["price"], currency=it["currency"], min_qty=it["min_qty"],
                         key=it["key"]))
    db.commit()
    return dict(_price_list_dict(pl), recognised=sum(1 for i in items if i["key"]))


@router.delete("/price-lists/{list_id}")
def delete_price_list(list_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.models import PriceItem, PriceList
    p = db.query(PriceList).filter(PriceList.id == list_id, PriceList.owner == _profile_key(user)).first()
    if not p:
        raise HTTPException(status_code=404, detail="Price list not found")
    db.query(PriceItem).filter(PriceItem.list_id == p.id).delete()
    db.delete(p)
    db.commit()
    return {"deleted": list_id}


@router.get("/tenders/{tender_id}/materials")
def tender_materials(tender_id: str, db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    from app.materials import cost_view, price_index, tender_boq
    _tender_or_404(db, tender_id)
    return cost_view(tender_boq(tender_id), price_index(_price_items(db, user)), None)


def _active(t):
    return not t.outcome and (t.stage or "") not in ("CLOSED", "SUBMITTED") and t.final_decision != "NO_GO"


@router.get("/portfolio/materials")
def portfolio_materials(db: Session = Depends(get_db), user: dict = Depends(require_auth)):
    """The same material across the account's active tenders."""
    from app.materials import aggregate, price_index, tender_boq
    tenders = [t for t in _account_tenders(db, user) if _active(t)]
    lines = {t.id: tender_boq(t.id) for t in tenders}
    res = aggregate({k: v for k, v in lines.items() if v}, {t.id: t.title for t in tenders},
                    price_index(_price_items(db, user)))
    return dict(res, active_tenders=len(tenders), tenders_with_boq=sum(1 for v in lines.values() if v))
