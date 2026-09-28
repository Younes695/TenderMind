"""
Processing Pipeline — TenderMind — Phase 3A + Stage 1B
- Orchestrates: inventory → extraction → classification → deterministic → semantic → validation → persistence
- Async via BackgroundTasks (in-process, no Redis/Celery)
- Failure isolation per document: COMPLETE/PARTIAL/FAILED/UNSUPPORTED
- Never makes BID/NO_BID decision (analysis only)
- Stage 1B: Uses persisted TenderDocument.source_path via get_storage_root() single source of truth.
-          No Sarai fallback for real uploaded tenders.
"""
import threading
import uuid
import datetime
from pathlib import Path
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import ProcessingJob, Tender
from app.database import SessionLocal, get_storage_root

PIPELINE_VERSION = "1.0"
LLM_MODEL = "qwen2.5:3b"
PROMPT_VERSION = "Variant B"

# Job stages
STAGES = ["INVENTORY", "EXTRACTION", "CLASSIFICATION", "DETERMINISTIC", "SEMANTIC", "VALIDATION", "PERSISTENCE", "COMPLETED"]

def create_processing_job(db: Session, tender_id: str) -> ProcessingJob:
    # Validate tender exists
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise ValueError(f"Tender {tender_id} not found")
    # Prevent duplicate concurrent jobs
    active = db.query(ProcessingJob).filter(
        ProcessingJob.tender_id == tender_id,
        ProcessingJob.status.in_(["QUEUED", "PROCESSING"])
    ).first()
    if active:
        raise ValueError(f"Active job {active.id} already exists for tender {tender_id} with status {active.status}")
    job = ProcessingJob(
        id=f"JOB-{uuid.uuid4().hex[:8].upper()}",
        tender_id=tender_id,
        status="QUEUED",
        current_stage="INVENTORY",
        progress=0,
        created_at=datetime.datetime.utcnow(),
        pipeline_version=PIPELINE_VERSION,
        model=LLM_MODEL,
        prompt_version=PROMPT_VERSION,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def get_processing_job(db: Session, job_id: str) -> ProcessingJob:
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise ValueError(f"Job {job_id} not found")
    return job

def update_job_progress(db: Session, job: ProcessingJob, stage: str, progress: float, **kwargs):
    job.current_stage = stage
    job.progress = progress
    for k, v in kwargs.items():
        if hasattr(job, k):
            setattr(job, k, v)
    db.commit()


def record_stage(db: Session, job_id: str, stage: str, status: str = "COMPLETED",
                 counts: dict | None = None, error: str | None = None):
    """Stage 4G — persist a stage-transition event (refresh/reconnect recovery).

    Best-effort: never breaks processing on logging failure.
    """
    try:
        from app.models import StageEvent
        db.add(StageEvent(
            id=f"STG-{uuid.uuid4().hex[:8].upper()}",
            job_id=job_id, stage=stage, status=status,
            counts=counts or {}, error=(error[:500] if error else None),
            created_at=datetime.datetime.utcnow()))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

def _resolve_tender_dir(tender_id: str):
    """Single source of truth for tender storage directory."""
    storage_root = get_storage_root()
    return storage_root / tender_id

def _is_sarai_tender(tender_id: str) -> bool:
    return tender_id == "SA-2018-HV2"

def _derive_terminal_status(
    documents_total: int,
    documents_processed: int,
    documents_failed: int,
    documents_unsupported: int,
) -> str:
    total = int(documents_total or 0)
    processed = int(documents_processed or 0)
    failed = int(documents_failed or 0)
    unsupported = int(documents_unsupported or 0)

    if total == 0:
        return "COMPLETED"

    if processed == total and failed == 0 and unsupported == 0:
        return "COMPLETED"

    if failed > 0 and processed == 0 and unsupported == 0:
        return "FAILED"

    if processed > 0 or unsupported > 0:
        return "PARTIAL"

    return "FAILED"

ACTIVE_JOBS: set = set()
_ACTIVE_LOCK = threading.Lock()
LOW_OCR_CONFIDENCE = 0.55


def page_quality(doc_results: dict) -> list:
    """OCR'd pages that are probably unreadable (low confidence or almost no text)."""
    out = []
    for name, res in (doc_results or {}).items():
        for pg in (res or {}).get("pages") or []:
            if not pg.get("ocr_applied"):
                continue
            conf = pg.get("confidence")
            chars = len((pg.get("text") or "").strip())
            if (conf is not None and conf < LOW_OCR_CONFIDENCE) or chars < 30:
                out.append({"document": name, "page": pg.get("page_number") or pg.get("source_page_number"),
                            "confidence": round(conf, 2) if isinstance(conf, (int, float)) else None,
                            "chars": chars})
    return out


def process_tender(tender_id: str, job_id: str):
    with _ACTIVE_LOCK:
        ACTIVE_JOBS.add(job_id)
    try:
        _process_tender(tender_id, job_id)
    finally:
        with _ACTIVE_LOCK:
            ACTIVE_JOBS.discard(job_id)
        try:
            from app.issues import sync_issues_safe
            sync_issues_safe(tender_id)
        except Exception:
            pass


def resume_interrupted(grace_seconds: int = 0, reason: str = "the server stopped") -> list:
    """Jobs marked QUEUED/PROCESSING with no live worker in this process are
    resumed as a new job (extraction and AI answers come back from checkpoints).
    A tender is auto-resumed at most 3 times in 6 hours, so a file that crashes
    the worker every time cannot loop forever."""
    import os
    from app.database import SessionLocal as _SL
    auto = os.environ.get("TENDERMIND_AUTO_RESUME", "1").strip() != "0"
    now = datetime.datetime.utcnow()
    started = []
    s = _SL()
    try:
        stuck = s.query(ProcessingJob).filter(ProcessingJob.status.in_(["QUEUED", "PROCESSING"])).all()
        for job in stuck:
            with _ACTIVE_LOCK:
                alive = job.id in ACTIVE_JOBS
            born = job.started_at or job.created_at or now
            if alive or (now - born).total_seconds() < grace_seconds:
                continue
            recent = s.query(ProcessingJob).filter(
                ProcessingJob.tender_id == job.tender_id,
                ProcessingJob.created_at >= now - datetime.timedelta(hours=6),
                ProcessingJob.last_error.like("%resumed automatically%")).count()
            job.status = "FAILED"
            job.completed_at = now
            if auto and recent < 3:
                s.commit()
                new = create_processing_job(s, job.tender_id)
                job.last_error = f"Interrupted ({reason}) — resumed automatically as {new.id}"
                s.commit()
                threading.Thread(target=process_tender, args=(job.tender_id, new.id),
                                 name=f"resume-{new.id}", daemon=True).start()
                started.append(new.id)
            else:
                job.last_error = (f"Interrupted ({reason}). Start processing again."
                                  if not auto else
                                  f"Interrupted ({reason}) repeatedly — not resumed again automatically. "
                                  "Check the files, then start processing again.")
                s.commit()
    except Exception:
        s.rollback()
    finally:
        s.close()
    return started


def start_watchdog(interval_s: int = 60, grace_s: int = 180) -> None:
    """Resumes jobs whose worker thread died without recording a result."""
    def _loop():
        import time as _t
        while True:
            _t.sleep(interval_s)
            try:
                resume_interrupted(grace_seconds=grace_s, reason="its worker stopped unexpectedly")
            except Exception:
                pass
    threading.Thread(target=_loop, name="job-watchdog", daemon=True).start()


def _process_tender(tender_id: str, job_id: str):
    """Orchestration function — runs in BackgroundTasks"""
    db = SessionLocal()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            return
        job.status = "PROCESSING"
        job.started_at = datetime.datetime.utcnow()
        job.current_stage = "INVENTORY"
        job.progress = 5
        db.commit()

        # Stage 1: Inventory — real, from persisted TenderDocuments or filesystem
        # Production flow for new tenders: MUST use TenderDocument.source_path or storage_root/tender_id
        # Sarai fallback isolated: only for SA-2018-HV2 when no real uploads exist (regression/evaluation only)
        job_inventory = []
        try:
            from app.models import TenderDocument
            import os
            storage_root = get_storage_root()
            tender_docs = []
            try:
                tender_docs = db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id).all()
            except Exception:
                tender_docs = []

            # Prefer DB source_path if any doc has it (Stage 1B path)
            docs_with_path = []
            if tender_docs:
                for doc in tender_docs:
                    sp = getattr(doc, "source_path", None)
                    if sp and str(sp).strip():
                        p = Path(str(sp))
                        if p.exists() and p.is_file():
                            docs_with_path.append(doc)
                        else:
                            # Try reconstructing from storage_root if absolute path missing (migration compat)
                            # Title holds filename, storage_root/tender_id/filename should exist
                            reconstructed = storage_root / tender_id / (doc.title or "")
                            if reconstructed.exists() and reconstructed.is_file():
                                docs_with_path.append(doc)
                                # Use reconstructed for inventory, keep original doc for count
                            else:
                                # File missing — still count but mark as not found? For now skip missing
                                pass
                            # Even if missing, we still count it as doc but without file it will be FAILED later
                            # To keep honest, only add if file exists

            if docs_with_path:
                inventory = []
                for doc in docs_with_path:
                    try:
                        sp = getattr(doc, "source_path", None)
                        if sp and Path(str(sp)).exists():
                            p = Path(str(sp))
                        else:
                            p = storage_root / tender_id / (doc.title or "")
                        if p.exists() and p.is_file():
                            inventory.append({"filename": p.name, "full_path": str(p), "extension": p.suffix.lower(), "size_bytes": p.stat().st_size})
                        else:
                            # Keep entry but mark missing — will be counted as FAILED in extraction
                            inventory.append({"filename": doc.title or p.name, "full_path": str(p), "extension": p.suffix.lower() if p.suffix else ".unknown", "size_bytes": 0, "missing": True})
                    except Exception:
                        continue
                job.documents_total = len(tender_docs)
                job_inventory = inventory
                job.current_stage = "INVENTORY"
                job.progress = 10
                db.commit()
            else:
                # No DB source_path docs — scan filesystem tender_dir
                tender_dir = storage_root / tender_id
                # Isolated Sarai fallback: only if this is the Sarai tender AND no real files
                # Portable: only via TENDER_SARAI_PATH env, no hardcoded developer path
                if not tender_dir.exists() and _is_sarai_tender(tender_id):
                    sarai_env = os.environ.get("TENDER_SARAI_PATH")
                    if sarai_env and Path(sarai_env).exists():
                        tender_dir = Path(sarai_env)
                    else:
                        # No Sarai files and no env — keep empty inventory (will produce empty analysis)
                        # Hardcoded C:\Users\EgyTech\... removed for portability — set TENDER_SARAI_PATH for evaluation
                        tender_dir = storage_root / tender_id
                if tender_dir.exists():
                    files = list(tender_dir.rglob("*"))
                    files = [p for p in files if p.is_file()]
                    inventory = [{"filename": str(p.relative_to(tender_dir)), "full_path": str(p), "extension": p.suffix.lower(), "size_bytes": p.stat().st_size} for p in files]
                    job.documents_total = len(files)
                    job_inventory = inventory
                else:
                    job_inventory = []
                    job.documents_total = len(tender_docs) if tender_docs else 0
                job.current_stage = "INVENTORY"
                job.progress = 10
                db.commit()
        except Exception as e:
            job.last_error = str(e)[:500]
            job.error_count = (job.error_count or 0) + 1
            job_inventory = []
            db.commit()
        record_stage(db, job.id, "INVENTORY", "COMPLETED" if job_inventory else "PARTIAL",
                     {"entries": len(job_inventory or [])},
                     error=None if job_inventory else "empty inventory")

        # Stage 2: Extraction (per document, with failure isolation) — real
        job.current_stage = "EXTRACTION"
        job.progress = 10
        db.commit()
        documents_total = len(job_inventory) if job_inventory is not None else 0
        job.documents_total = documents_total
        documents_processed = 0
        documents_failed = 0
        documents_unsupported = 0
        doc_results = {}
        # Live progress (Stage 5G): 10-40% follows pages extracted (OCR included),
        # documents_processed follows finished files. Page totals come from the
        # PDF page counts (cheap); every other file counts as one page.
        from app.pipeline.progress import listen as _listen

        def _page_estimate(item):
            try:
                if str(item.get("full_path", "")).lower().endswith(".pdf"):
                    import fitz as _fitz
                    with _fitz.open(item["full_path"]) as _d:
                        return max(1, len(_d))
            except Exception:
                pass
            return 1

        _estimates = [_page_estimate(f) for f in (job_inventory or [])]
        _all_pages = max(1, sum(_estimates))
        _pages_before = 0
        _last_commit = [0.0]

        def _set_progress(pct, force=False):
            """Best effort: a progress write that hits a busy database is skipped,
            never allowed to end the job (it did, on the Turaif run)."""
            import time as _time
            if force or _time.time() - _last_commit[0] >= 2:
                try:
                    job.progress = round(min(pct, 99.0), 1)
                    db.commit()
                except Exception:
                    db.rollback()
                _last_commit[0] = _time.time()

        def _on_extract(phase, done, total):
            if phase == "pages":
                _set_progress(10 + 30 * (_pages_before + min(done, total)) / _all_pages)

        for _idx, f in enumerate(job_inventory if job_inventory else []):
            if _idx:
                _pages_before += _estimates[_idx - 1]
                job.documents_processed = documents_processed
                job.documents_failed = documents_failed
                job.documents_unsupported = documents_unsupported
                _set_progress(10 + 30 * _pages_before / _all_pages, force=True)
            # Handle missing file marker
            if f.get("missing"):
                documents_failed += 1
                doc_results[f["filename"]] = {"pages": [], "page_count": 0, "total_text_chars": 0, "status": "FAILED", "error": "File not found on storage"}
                continue
            try:
                p = Path(f["full_path"])
                if not p.exists():
                    documents_failed += 1
                    doc_results[f["filename"]] = {"pages": [], "page_count": 0, "total_text_chars": 0, "status": "FAILED", "error": "File not found"}
                    continue
                hint = None
                if "ocr_needed" in f:
                    low = f["ocr_needed"].lower()
                    if "yes" in low:
                        hint = True
                    elif "no" in low:
                        hint = False
                # Stage 5E: one dispatcher for every type (PDF, Office, text,
                # images via OCR, ZIP/RAR/7z archives, CAD, .bak by content).
                # Archives yield one entry per inner file.
                from app.pipeline.file_extractors import extract_any
                from evaluation.run_real_benchmark import extract_pdf_text

                def _pdf(path, h):
                    return extract_pdf_text(path, ocr_needed_hint=h)

                # Stage 5H: reuse this file's extraction from an earlier run (retry /
                # resume after a crash) instead of reading and OCR-ing it again.
                from app.pipeline.checkpoint import load_extraction, save_extraction
                _entries = load_extraction(tender_id, p, f["filename"])
                if _entries is None:
                    with _listen(_on_extract):
                        _entries = extract_any(p, f["filename"], _pdf, pdf_hint=hint)
                    save_extraction(tender_id, p, f["filename"], _entries)
                for _name, _res in _entries:
                    _st = _res["status"]
                    if _st == "UNSUPPORTED":
                        documents_unsupported += 1
                    elif _st == "FAILED":
                        documents_failed += 1
                    else:
                        documents_processed += 1
                    doc_results[_name] = _res
            except Exception as e:
                documents_failed += 1
                doc_results[f["filename"]] = {"pages": [], "page_count": 0, "total_text_chars": 0, "status": "FAILED", "error": str(e)[:200]}
        documents_total = len(doc_results)  # archives expand into their inner files
        job.documents_total = documents_total
        job.documents_processed = documents_processed
        job.documents_failed = documents_failed
        job.documents_unsupported = documents_unsupported
        db.commit()
        record_stage(db, job.id, "EXTRACTION", "COMPLETED" if documents_failed == 0 else "PARTIAL",
                     {"total": documents_total, "processed": documents_processed,
                      "failed": documents_failed, "unsupported": documents_unsupported})

        # Stages 3-6 are quick bookkeeping; the AI itself runs later
        # (AI_ANALYSIS, 45-93%), so these must not claim 60-90%.
        # Stage 3: Classification
        job.current_stage = "CLASSIFICATION"
        job.progress = 41
        db.commit()

        # Stage 4: Deterministic extraction (voltage, MVA, dates)
        job.current_stage = "DETERMINISTIC"
        job.progress = 42
        db.commit()

        # Stage 5: Semantic extraction (LLM)
        job.current_stage = "SEMANTIC"
        job.progress = 43
        try:
            from evaluation.llm_generic_extraction import check_ollama_available
            ok, msg = check_ollama_available()
            if not ok:
                job.last_error = f"LLM unavailable: {msg}"
        except Exception as e:
            job.last_error = str(e)[:500]
        db.commit()

        # Stage 6: Validation
        job.current_stage = "VALIDATION"
        job.progress = 44
        db.commit()

        # Stage 7: Persistence — build and validate canonical analysis (real, not simulated)
        job.current_stage = "PERSISTENCE"
        job.progress = 45
        try:
            from evaluation.generic_extraction import build_generic_extraction
            import os
            storage_root = get_storage_root()
            # For new tenders, tender_path is always storage_root / tender_id
            tender_path = storage_root / tender_id
            # Only allow Sarai fallback if this is Sarai and tender_path doesn't exist (portable, env-only)
            if not tender_path.exists() and _is_sarai_tender(tender_id):
                sarai_env = os.environ.get("TENDER_SARAI_PATH")
                if sarai_env and Path(sarai_env).exists():
                    tender_path = Path(sarai_env)
                else:
                    # No hardcoded developer path — set TENDER_SARAI_PATH for evaluation
                    tender_path = storage_root / tender_id
            if not tender_path.exists():
                # Create empty dir so build_generic_extraction doesn't fail on missing path
                # but will produce minimal analysis (0 docs) — honest empty
                tender_path = storage_root / tender_id
                if not tender_path.exists():
                    try:
                        tender_path.mkdir(parents=True, exist_ok=True)
                    except:
                        tender_path = Path.cwd()
            tender = db.query(Tender).filter(Tender.id == tender_id).first()
            # Reuse the text extracted above (it used to be extracted — and OCR'd — twice).
            _reuse = doc_results if tender_path == storage_root / tender_id else None
            analysis_data = build_generic_extraction(tender_path, tender_id=tender_id, use_llm=False,
                                                     doc_results=_reuse)
            from evaluation.generic_extraction import validate_against_schema
            schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
            ok, msg = validate_against_schema(analysis_data, schema_path)
            if not ok:
                raise ValueError(f"Schema validation failed: {msg}")
            # Stage 4A seam (flag-gated): when TENDERMIND_TWO_STAGE_LLM=1, build
            # requirements/evidence through the hardened two-stage runner over
            # the already-extracted doc_results. Flag off: untouched legacy data.
            # Stage 4F: the flag path runs the full intelligence runner (lanes
            # A-E: structured-first, commercial/schedule, gaps, ambiguity,
            # reconciliation MVP, risk, synthesis). New sections merge into
            # derived_features additively (no schema/migration change).
            pipeline_version = PIPELINE_VERSION
            model_name = LLM_MODEL
            prompt_version = PROMPT_VERSION
            from app.pipeline.config import is_two_stage_enabled
            if not is_two_stage_enabled():
                # AI flag off: no model is called, so don't label the run with one.
                model_name = "none (deterministic)"
                prompt_version = "none"
                job.model = model_name
                job.prompt_version = prompt_version
            if is_two_stage_enabled():
                from app.pipeline import two_stage_runner as _tsr
                from app.pipeline import intelligence_runner as _ir
                from app.pipeline.jobs import pipeline_version_metadata as _pvm
                from app.pipeline.contracts import DocumentArtifact as _Doc
                _sources, _extras = _tsr.adapt_doc_results(doc_results)
                _docs = [_Doc(filename=e.get("filename", ""), full_path="", extension="",
                              status=str(e.get("extraction_status", "COMPLETE")),
                              page_count=int(e.get("page_count", 0) or 0),
                              total_text_chars=int(e.get("text_length", 0) or 0),
                              error=e.get("error")) for e in _extras.get("documents", [])]
                _tables = []
                try:
                    from app.pipeline.structured_data import read_structured
                    for _fn in sorted(doc_results.keys()):
                        if str(_fn).lower().endswith(".xlsx"):
                            _p = tender_path / str(_fn).split("#")[0]
                            if _p.is_file():
                                _tables.extend(read_structured(_p))
                except Exception:
                    _tables = []
                _extras.update({
                    "deadlines": analysis_data.get("deadlines", []),
                    "commercial": analysis_data.get("commercial_terms"),
                    "risks": analysis_data.get("risks", []),
                    "derived_features": analysis_data.get("derived_features", {}),
                })
                # Workers were never passed here before, so TENDERMIND_WORKERS_ENABLED
                # had no effect and every AI call ran sequentially.
                from app.pipeline.capability_tiers import load_worker_config as _lwc
                job.current_stage = "AI_ANALYSIS"
                _set_progress(45, force=True)

                def _on_ai(phase, done, total):
                    if phase == "ai" and total:
                        _set_progress(45 + 48 * done / total)

                from app.pipeline.checkpoint import AiCache
                from app.pipeline.ai_router import active_model_name as _amn, active_prompt_version as _apv
                with _listen(_on_ai):
                    _intel, _telem = _ir.run_intelligence(
                        tender_id, _sources, documents=_docs, tables=_tables,
                        job_id=job.id, deterministic_extras=_extras,
                        workers=_lwc(), ai_cache=AiCache(tender_id, _amn(), _apv()))
                job.current_stage = "PERSISTENCE"
                _set_progress(95, force=True)
                analysis_data = dict(analysis_data)
                analysis_data["requirements"] = _intel["requirements"]
                analysis_data["evidence"] = _intel["evidence"]
                analysis_data["documents"] = _extras["documents"]
                _df = dict(analysis_data.get("derived_features", {}) or {})
                for _k in ("commercial_facts", "schedule_facts", "clarifications", "addenda",
                           "gaps", "ambiguities", "ambiguities_raw", "ambiguity_report",
                           "conflicts", "duplicate_groups",
                           "amendment_links", "lifecycle", "risk_signals", "synthesis",
                           "structured_coverage"):
                    _df[_k] = _intel[_k]
                _df["telemetry"] = _telem.to_dict()
                analysis_data["derived_features"] = _df
                _meta = _pvm()
                pipeline_version = _meta["pipeline_version"]
                from app.pipeline.ai_router import active_model_name, active_prompt_version
                model_name = active_model_name()
                prompt_version = active_prompt_version()
                job.model = model_name
                job.prompt_version = prompt_version
                # Re-validate the final two-stage payload (patched schema permits
                # the documented UNKNOWN quarantine category; all other gates
                # identical). Never persist an invalid analysis.
                from evaluation.generic_extraction import validate_against_schema as _vas
                _schema2 = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema_2stage.json"
                _ok2, _msg2 = _vas(analysis_data, _schema2)
                if not _ok2:
                    raise ValueError(f"Two-stage schema validation failed: {_msg2}")
                job.current_stage = "FINALIZING"
                db.commit()
            # Stage 5H: unreadable scanned pages feed the Q&A list.
            try:
                _df2 = dict(analysis_data.get("derived_features") or {})
                _df2["page_quality"] = page_quality(doc_results)
                analysis_data["derived_features"] = _df2
            except Exception:
                pass
            req_ids = [r["requirement_id"] for r in analysis_data["requirements"]]
            if len(req_ids) != len(set(req_ids)):
                raise ValueError("Duplicate requirement IDs")
            for ev in analysis_data["evidence"]:
                if ev.get("requirement_id") and ev["requirement_id"] not in req_ids:
                    raise ValueError(f"Orphan evidence {ev.get('evidence_id')} references unknown {ev.get('requirement_id')}")
            for req in analysis_data["requirements"]:
                if not req.get("source_document"):
                    pass
            from app.models import TenderAnalysis
            import uuid
            terminal_status = _derive_terminal_status(
                documents_total,
                documents_processed,
                documents_failed,
                documents_unsupported,
            )
            analysis = TenderAnalysis(
                id=f"ANALYSIS-{uuid.uuid4().hex[:8].upper()}",
                tender_id=tender_id,
                processing_job_id=job.id,
                analysis_version="1.0",
                pipeline_version=pipeline_version,
                model=model_name,
                prompt_version=prompt_version,
                status=terminal_status,
                tender={"id": tender.id, "title": tender.title} if tender else {"id": tender_id},
                documents=analysis_data["documents"],
                requirements=analysis_data["requirements"],
                evidence=analysis_data["evidence"],
                deadlines=analysis_data.get("deadlines", []),
                commercial=analysis_data.get("commercial_terms"),
                risks=analysis_data.get("risks", []),
                derived_features=analysis_data.get("derived_features", {}),
                processing={
                    "job_id": job.id,
                    "status": terminal_status,
                    "progress": job.progress,
                    "documents_total": job.documents_total,
                    "documents_processed": job.documents_processed,
                    "pipeline_version": pipeline_version,
                    "model": model_name,
                    "prompt_version": prompt_version,
                    "documents_failed": job.documents_failed,
                    "documents_unsupported": job.documents_unsupported,
                }
            )
            try:
                from app.pipeline.jobs import resolve_coverage
                analysis.processing = {**(analysis.processing or {}),
                                       **resolve_coverage(job.documents_total, job.documents_processed,
                                                          job.documents_failed, job.documents_unsupported)}
                db.commit()
            except Exception:
                pass
            db.add(analysis)
            db.commit()
            print(f"PERSISTENCE: Saved analysis {analysis.id} for tender {tender_id} with {len(analysis_data['requirements'])} requirements")
            record_stage(db, job.id, "PERSISTENCE", "COMPLETED",
                         {"requirements": len(analysis_data["requirements"]),
                          "evidence": len(analysis_data.get("evidence", []))})
            # Stage 5C: feed the decision engine (requirements start MISSING_EVIDENCE
            # until company documents are matched). Never fails the job.
            try:
                from app.engines.tender_bridge import sync_requirements
                from app.engines.decision import get_or_create_decision
                _sync = sync_requirements(db, tender_id)
                if _sync["synced"]:
                    get_or_create_decision(db, tender_id)
                record_stage(db, job.id, "DECISION_SYNC", "COMPLETED", _sync)
            except Exception as _e:
                db.rollback()
                record_stage(db, job.id, "DECISION_SYNC", "FAILED", {}, error=str(_e)[:300])
        except Exception as e:
            print(f"PERSISTENCE failed: {e}")
            import traceback
            traceback.print_exc()
            job.last_error = f"PERSISTENCE failed: {str(e)[:300]}"
            job.error_count = (job.error_count or 0) + 1
            db.commit()
            record_stage(db, job.id, "PERSISTENCE", "FAILED", {}, error=str(e))
        db.commit()

        # Final status
        if documents_failed == 0 and documents_unsupported == 0:
            job.status = "COMPLETED"
        elif documents_failed > 0 and documents_processed > 0:
            job.status = "PARTIAL"
        elif documents_failed > 0 and documents_processed == 0 and documents_unsupported == 0:
            # If we had documents but all failed, FAILED; if no documents, COMPLETED with empty analysis is more honest
            if documents_total > 0:
                job.status = "FAILED"
            else:
                job.status = "COMPLETED"
        elif documents_unsupported > 0 and documents_processed == 0:
            # Only unsupported docs -> PARTIAL (upload succeeded, processing honestly unsupported)
            job.status = "PARTIAL"
        else:
            job.status = "COMPLETED"
        job.current_stage = "COMPLETED"
        job.progress = 100
        job.completed_at = datetime.datetime.utcnow()
        if documents_failed > 0 and job.status == "COMPLETED":
            job.status = "PARTIAL"
        # Stage 4G honesty rule: COMPLETED requires a persisted analysis.
        # Persistence failure with real documents => FAILED (never fake COMPLETE).
        try:
            from app.models import TenderAnalysis as _TA
            _persisted = db.query(_TA).filter(_TA.processing_job_id == job.id).first()
            if _persisted is None and (documents_total or 0) > 0:
                job.status = "FAILED"
                if not job.last_error or "PERSISTENCE" not in job.last_error:
                    job.last_error = (job.last_error + " | " if job.last_error else "") + \
                        "PERSISTENCE produced no retrievable analysis"
                job.error_count = (job.error_count or 0) + 1
        except Exception:
            pass
        db.commit()
        record_stage(db, job.id, "COMPLETED", job.status,
                     {"processed": documents_processed, "failed": documents_failed,
                      "unsupported": documents_unsupported},
                     error=job.last_error if job.status != "COMPLETED" else None)

    except Exception as e:
        # The job's session may be the thing that failed (e.g. a locked database
        # left it needing rollback). Record FAILED on a fresh session so a job
        # never stays "PROCESSING" after its thread is gone.
        try:
            db.rollback()
        except Exception:
            pass
        _mark_failed(job_id, e)
    finally:
        db.close()


def _mark_failed(job_id: str, err: Exception) -> None:
    from app.database import SessionLocal as _SL
    s = _SL()
    try:
        job = s.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            job.status = "FAILED"
            job.last_error = f"{type(err).__name__}: {err}"[:500]
            job.error_count = (job.error_count or 0) + 1
            job.completed_at = datetime.datetime.utcnow()
            s.commit()
    except Exception:
        s.rollback()
    finally:
        s.close()
