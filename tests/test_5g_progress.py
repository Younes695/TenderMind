"""Stage 5G — processing progress follows the real work, and files are extracted once.

Before: the job sat at "EXTRACTION 20%" for the whole extraction (documents_processed
stayed 0 until every file was done) and at "PERSISTENCE 95%" for the whole AI run;
and build_generic_extraction re-extracted every file (OCR ran twice).
"""
import threading
import uuid
from pathlib import Path

from app.pipeline import progress


def test_report_without_listener_is_a_no_op():
    progress.report("pages", 1, 2)  # must not raise


def test_listener_is_per_thread_and_restored():
    seen, other = [], []
    with progress.listen(lambda *a: seen.append(a)):
        progress.report("pages", 1, 3)
        t = threading.Thread(target=lambda: progress.report("pages", 9, 9))
        t.start(); t.join()
    progress.report("pages", 2, 3)
    assert seen == [("pages", 1, 3)] and other == []


def test_listener_errors_never_escape():
    def boom(*_a):
        raise RuntimeError("x")
    with progress.listen(boom):
        progress.report("ai", 1, 1)


def test_fitz_page_loop_reports_each_page(tmp_path):
    import fitz
    from evaluation.run_real_benchmark import extract_pdf_text
    pdf = tmp_path / "three.pdf"
    doc = fitz.open()
    for i in range(3):
        doc.new_page().insert_text((72, 72), f"Page {i + 1} tender security EGP 500,000 " * 5)
    doc.save(pdf)
    seen = []
    with progress.listen(lambda phase, d, t: seen.append((phase, d, t))):
        pages = extract_pdf_text(pdf, ocr_needed_hint=False)
    assert len(pages) == 3
    assert [s for s in seen if s[0] == "pages"] == [("pages", 1, 3), ("pages", 2, 3), ("pages", 3, 3)]


def test_build_generic_extraction_reuses_given_doc_results(tmp_path, monkeypatch):
    import evaluation.generic_extraction as ge
    monkeypatch.setattr(ge, "ingest_tender", lambda *a, **k: (_ for _ in ()).throw(AssertionError("re-extracted")))
    doc_results = {"a.txt": {"pages": [{"page_number": 1, "text": "The bidder shall submit a tender security of EGP 500,000.",
                                         "method": "txt"}], "page_count": 1, "total_text_chars": 57, "status": "COMPLETE"}}
    out = ge.build_generic_extraction(tmp_path, tender_id="T-REUSE", doc_results=doc_results)
    assert out["documents"][0]["filename"] == "a.txt"


def test_processing_job_progress_moves_during_extraction(tmp_path, monkeypatch):
    """Every document bumps documents_processed and progress while extraction runs."""
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    monkeypatch.delenv("TENDERMIND_TWO_STAGE_LLM", raising=False)
    from app.database import SessionLocal, init_db
    from app.models import ProcessingJob, Tender, TenderDocument
    from app import processing
    init_db()
    tid = f"PROG-{uuid.uuid4().hex[:6]}"
    tdir = tmp_path / tid
    tdir.mkdir()
    db = SessionLocal()
    try:
        db.add(Tender(id=tid, title="p"))
        for i in range(3):
            f = tdir / f"doc{i}.txt"
            f.write_text(f"Requirement {i}: the contractor shall provide a performance bond. " * 3, encoding="utf-8")
            db.add(TenderDocument(id=f"D-{tid}-{i}", tender_id=tid, title=f.name, doc_type="TXT",
                                  source_path=str(f), original_filename=f.name))
        db.commit()
        job = processing.create_processing_job(db, tid)
        job_id = job.id
    finally:
        db.close()

    snapshots = []
    real_extract_any = processing_extract_any = None
    from app.pipeline import file_extractors

    real_extract_any = file_extractors.extract_any

    def spy(*a, **k):
        s = SessionLocal()
        try:
            j = s.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            snapshots.append((j.current_stage, j.progress, j.documents_processed))
        finally:
            s.close()
        return real_extract_any(*a, **k)

    monkeypatch.setattr(file_extractors, "extract_any", spy)
    processing.process_tender(tid, job_id)
    assert [s[2] for s in snapshots] == [0, 1, 2]
    progresses = [s[1] for s in snapshots]
    assert progresses == sorted(progresses) and progresses[-1] > progresses[0]
    db = SessionLocal()
    try:
        j = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        assert j.documents_processed == 3 and j.progress == 100
    finally:
        db.close()


def _mixed_pdf(path, n=8):
    import fitz
    doc = fitz.open()
    for i in range(n):
        page = doc.new_page()
        if i % 2 == 0:  # native text page
            page.insert_text((72, 72), f"Native page {i + 1}: the contractor shall submit a bid bond. " * 3)
    doc.save(path)


def test_scanned_pages_ocr_in_parallel_keep_order_and_report(tmp_path, monkeypatch):
    import threading
    import time as _t
    import evaluation.tesseract_local_ocr as tlo
    pdf = tmp_path / "mixed.pdf"
    _mixed_pdf(pdf)
    active, peak, lock = [0], [0], threading.Lock()

    def fake_ocr(path, page_number, **_k):
        with lock:
            active[0] += 1; peak[0] = max(peak[0], active[0])
        _t.sleep(0.2)
        with lock:
            active[0] -= 1
        return {"source_page_number": page_number, "text": f"OCR text {page_number}", "ocr_applied": True}

    monkeypatch.setattr(tlo, "ocr_page_with_tesseract", fake_ocr)
    monkeypatch.setenv("TENDERMIND_OCR_WORKERS", "4")
    seen = []
    t0 = _t.time()
    with progress.listen(lambda ph, d, t: seen.append((ph, d, t))):
        pages = tlo.extract_pdf_with_tesseract_routing(pdf)
    elapsed = _t.time() - t0
    assert [p["source_page_number"] for p in pages] == list(range(1, 9))  # page order kept
    assert pages[1]["text"] == "OCR text 2" and "Native page 1" in pages[0]["text"]
    assert peak[0] > 1 and elapsed < 0.6          # 4 scanned pages ran concurrently (serial = 0.8s)
    assert seen[-1] == ("pages", 8, 8) and [d for _, d, _ in seen] == sorted(d for _, d, _ in seen)


def test_single_pass_ocr_returns_text_and_confidence(tmp_path):
    """One Tesseract run gives the same text image_to_string gave, plus confidence."""
    import shutil
    import pytest
    from evaluation import tesseract_local_ocr as tlo
    if not shutil.which(tlo.pytesseract.pytesseract.tesseract_cmd) and not \
            __import__("os").path.exists(tlo.pytesseract.pytesseract.tesseract_cmd):
        pytest.skip("tesseract binary not installed")
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (900, 120), "white")
    ImageDraw.Draw(img).text((20, 40), "TENDER SECURITY 500000", fill="black")
    img = img.resize((2700, 360))
    import io
    buf = io.BytesIO(); img.save(buf, format="PNG")
    text, conf = tlo.ocr_png_text_and_confidence(buf.getvalue(), lang="eng")
    assert text == tlo.pytesseract.image_to_string(img, lang="eng", config=tlo.TESS_CONFIG)
    assert conf is None or 0 <= conf <= 1


def test_sqlite_runs_in_wal_mode_with_busy_timeout():
    """Readers must not fail with 'database is locked' while a job writes progress."""
    from sqlalchemy import text
    from app.database import engine
    with engine.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"
        assert int(c.execute(text("PRAGMA busy_timeout")).scalar()) >= 30000


def test_crash_after_db_error_still_marks_job_failed(tmp_path, monkeypatch):
    """A DB error poisons the job's session; the failure handler used to reuse it,
    fail silently, and leave the job 'PROCESSING' forever."""
    import sqlalchemy.exc
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    from app.database import SessionLocal, init_db
    from app.models import ProcessingJob, Tender, TenderDocument
    from app import processing
    from app.pipeline import file_extractors
    init_db()
    tid = f"CRASH-{uuid.uuid4().hex[:6]}"
    (tmp_path / tid).mkdir()
    f = tmp_path / tid / "a.txt"
    f.write_text("The contractor shall provide a bid bond of 2%.", encoding="utf-8")
    db = SessionLocal()
    try:
        db.add(Tender(id=tid, title="c"))
        db.add(TenderDocument(id=f"D-{tid}", tender_id=tid, title="a.txt", doc_type="TXT",
                              source_path=str(f), original_filename="a.txt"))
        db.commit()
        job_id = processing.create_processing_job(db, tid).id
    finally:
        db.close()

    real_record = processing.record_stage

    def poisoned_record(db, jid, stage, *a, **k):
        if stage == "EXTRACTION":
            # A failed flush leaves the session unusable until rollback — the
            # state a 'database is locked' commit left the real job in.
            db.add(ProcessingJob(id=jid, tender_id=tid))
            db.flush()
        return real_record(db, jid, stage, *a, **k)

    monkeypatch.setattr(processing, "record_stage", poisoned_record)
    processing.process_tender(tid, job_id)
    db = SessionLocal()
    try:
        j = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        assert j.status == "FAILED" and j.last_error
    finally:
        db.close()


def test_progress_commit_failure_does_not_stop_processing(tmp_path, monkeypatch):
    import sqlalchemy.exc
    from sqlalchemy.orm import Session
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    from app.database import SessionLocal, init_db
    from app.models import ProcessingJob, Tender, TenderDocument
    from app import processing
    init_db()
    tid = f"LOCK-{uuid.uuid4().hex[:6]}"
    (tmp_path / tid).mkdir()
    db = SessionLocal()
    try:
        db.add(Tender(id=tid, title="l"))
        for i in range(3):
            f = tmp_path / tid / f"d{i}.txt"
            f.write_text(f"Clause {i}: the contractor shall submit a performance bond. " * 3, encoding="utf-8")
            db.add(TenderDocument(id=f"D-{tid}-{i}", tender_id=tid, title=f.name, doc_type="TXT",
                                  source_path=str(f), original_filename=f.name))
        db.commit()
        job_id = processing.create_processing_job(db, tid).id
    finally:
        db.close()
    real_commit, calls = Session.commit, [0]

    import sys as _sys

    def flaky_commit(self):
        if _sys._getframe(1).f_code.co_name == "_set_progress":
            calls[0] += 1
        if calls[0] == 1 and _sys._getframe(1).f_code.co_name == "_set_progress":
            calls[0] += 1  # only the first progress commit fails
            raise sqlalchemy.exc.OperationalError("UPDATE processing_jobs", {}, Exception("database is locked"))
        return real_commit(self)

    monkeypatch.setattr(Session, "commit", flaky_commit)
    processing.process_tender(tid, job_id)
    monkeypatch.setattr(Session, "commit", real_commit)
    db = SessionLocal()
    try:
        j = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        assert j.status == "COMPLETED" and j.documents_processed == 3
    finally:
        db.close()
