import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from app.auth import require_auth
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

router = APIRouter(dependencies=[Depends(require_auth)])

@router.get("/tenders")
def list_tenders(db: Session = Depends(get_db)):
    return db.query(Tender).all()

@router.post("/tenders")
def create_tender(payload: dict, db: Session = Depends(get_db)):
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
def get_company(company_id: str, db: Session = Depends(get_db)):
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
def list_company_documents(db: Session = Depends(get_db)):
    from app.engines.tender_bridge import COMPANY_ID
    docs = db.query(CompanyDocument).filter(CompanyDocument.company_id == COMPANY_ID).all()
    return {"documents": [{"id": d.id, "title": d.title, "document_type": d.document_type} for d in docs],
            "count": len(docs)}


@router.post("/company-documents")
def upload_company_documents(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
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
                               title=name, source_path=str(dest), page="", section=""))
        created.append({"id": doc_id, "title": name, "document_type": ext.lstrip(".").upper()})
    db.commit()
    return {"documents": created, "count": len(created)}


@router.delete("/company-documents/{doc_id}")
def delete_company_document(doc_id: str, db: Session = Depends(get_db)):
    d = db.query(CompanyDocument).filter(CompanyDocument.id == doc_id).first()
    if not d:
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
    for r in reqs:
        sr = status_results.get(r.id, {})
        evs = []
        for m in db.query(EvidenceMatch).filter(EvidenceMatch.requirement_id == r.id).all():
            ev = db.query(Evidence).filter(Evidence.id == m.evidence_id).first()
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
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    try:
        job = get_processing_job(db, job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
        return {"status": latest_job.status, "current_stage": latest_job.current_stage, "progress": latest_job.progress, "message": "Processing not complete"}
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
    # Return canonical analysis — frontend-safe, no raw LLM, no candidate IDs
    return {
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
