"""Broken endpoints and silent extraction failures.

Before:
- GET /tenders/{id}/evidence and /export raised NameError (or_ was never imported).
- A document whose OCR failed on some pages was COMPLETE; one whose OCR failed
  on every page, a corrupt .docx, and Word/Excel backups (.bak) were PARTIAL with
  no error. All were counted as processed, cached for good, and absent from the
  package gaps.
Now: an unreadable page carries "error", the document status follows from those
pages, failures are retried instead of reused from the cache, and unreadable
pages are reported as a gap.
"""
import uuid
from pathlib import Path

import pytest


# ---------------------------------------------------------------- endpoints
def test_evidence_and_export_answer_for_an_existing_tender():
    from fastapi.testclient import TestClient
    from app.database import SessionLocal, init_db
    from app.main import app
    from app.models import Evidence, Requirement, Tender
    init_db()
    db = SessionLocal()
    tid = f"T16-{uuid.uuid4().hex[:8]}"
    db.add(Tender(id=tid, title="Evidence export"))
    db.add(Requirement(id=f"{tid}::REQ-000", tender_id=tid, category="LEGAL", requirement="Registration",
                       mandatory=True, requirement_type="HARD_GATE", applicable_entity="ANY",
                       evidence_required=[], evaluation_logic={}))
    db.add(Evidence(id=f"E-{tid}-req", company_id="OUR_COMPANY", requirement_id=f"{tid}::REQ-000",
                    evidence_type="DOCUMENT", fact="registered", status="PASS", source_document="reg.pdf",
                    page_or_section="p.1", extraction_confidence="HIGH"))
    db.add(Evidence(id=f"E-{tid}-src", company_id="OUR_COMPANY", requirement_id=None, evidence_type="DOCUMENT",
                    fact="sourced here", status="REVIEW", source_document="x.pdf", page_or_section="p.2",
                    extraction_confidence="LOW", tender_source_id=tid))
    db.commit()
    db.close()
    c = TestClient(app)
    r = c.get(f"/api/tenders/{tid}/evidence")
    assert r.status_code == 200
    assert {e["id"] for e in r.json()} == {f"E-{tid}-req", f"E-{tid}-src"}
    r = c.get(f"/api/tenders/{tid}/export")
    assert r.status_code == 200
    assert {e["id"] for e in r.json()["evidences"]} == {f"E-{tid}-req", f"E-{tid}-src"}


# ---------------------------------------------------------------- page -> document status
def _failed(n):
    return {"page_number": n, "text": "", "ocr_applied": True, "error": f"tesseract crashed on {n}",
            "method": "tesseract_5.4.0_ara+eng_psm6_dpi300_failed_RuntimeError"}


def _read(n):
    return {"page_number": n, "text": "native page text " * 10, "method": "fitz_direct_native"}


def test_every_page_unreadable_is_failed():
    from app.pipeline.file_extractors import _entry
    e = _entry([_failed(1), _failed(2)])
    assert e["status"] == "FAILED"
    assert e["failed_pages"] == [1, 2] and e["error"] == "tesseract crashed on 1"


def test_some_pages_unreadable_is_partial_with_the_pages_listed():
    from app.pipeline.file_extractors import _entry
    e = _entry([_read(1), _failed(2), _read(3), _failed(4)])
    assert e["status"] == "PARTIAL"
    assert e["failed_pages"] == [2, 4]
    assert e["error"] == "2 of 4 pages could not be read: tesseract crashed on 2"


def test_fully_read_document_is_complete_and_short_text_is_partial():
    from app.pipeline.file_extractors import _entry
    full = _entry([_read(1), _read(2)])
    assert full["status"] == "COMPLETE" and "failed_pages" not in full and "error" not in full
    short = _entry([{"page_number": 1, "text": "Yes", "method": "txt"}])
    assert short["status"] == "PARTIAL" and "failed_pages" not in short


def test_no_pages_is_failed_with_a_reason():
    from app.pipeline.file_extractors import _entry
    e = _entry([])
    assert e["status"] == "FAILED" and e["error"]


def test_legacy_failure_page_without_error_key_still_counts():
    """Extraction caches written before carry the old markers without "error"."""
    from app.pipeline.file_extractors import _entry, entry_has_failures
    e = _entry([{"page_number": 1, "text": "", "method": "unknown_doc_ext"}])
    assert e["status"] == "FAILED"
    old = {"status": "PARTIAL", "pages": [{"page_number": 1, "text": "", "method": "no_handler for .bak"}]}
    assert entry_has_failures(old)
    old_scan = {"status": "COMPLETE", "pages": [_read(1), {"page_number": 2, "text": "",
                                                          "method": "scanned_no_text_ocr_needed"}]}
    assert entry_has_failures(old_scan)  # the direct route wrote this for every page under 50 chars


def test_every_page_flagged_but_text_kept_is_partial_and_its_text_is_analysed():
    """OCR unavailable, every page an image plus a short caption: the captions were
    kept. FAILED would make every reader skip the document, captions and all."""
    from app.pipeline.file_extractors import _entry
    from app.pipeline.two_stage_runner import adapt_doc_results
    pages = [{"page_number": n, "text": f"Drawing sheet {n} - substation layout", "ocr_applied": True,
              "method": "tesseract_unavailable", "error": "OCR not available"} for n in (1, 2)]
    e = _entry(pages)
    assert e["status"] == "PARTIAL" and e["failed_pages"] == [1, 2]
    sources = adapt_doc_results({"sheets.pdf": e})[0]
    assert any("Drawing sheet 2" in s.text for s in sources)


# ---------------------------------------------------------------- real extractors
def _pdf(path, hint):
    from evaluation.run_real_benchmark import extract_pdf_text
    return extract_pdf_text(path, ocr_needed_hint=hint)


def _extract(path):
    from app.pipeline.file_extractors import extract_any
    ((_name, entry),) = extract_any(path, path.name, _pdf)
    return entry


def test_word_backup_is_read(tmp_path):
    docx = pytest.importorskip("docx")
    d = docx.Document()
    d.add_paragraph("Bidders must submit a bank guarantee of five percent of the offer value.")
    d.save(tmp_path / "w.docx")
    bak = (tmp_path / "w.docx").rename(tmp_path / "specs.bak")
    e = _extract(bak)
    assert e["status"] == "COMPLETE" and "bank guarantee" in e["pages"][0]["text"]


def test_excel_backup_is_read(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.append(["Item", "Qty"])
    wb.active.append(["Transformer 220kV", 2])
    wb.save(tmp_path / "b.xlsx")
    bak = (tmp_path / "b.xlsx").rename(tmp_path / "boq.bak")
    e = _extract(bak)
    assert "Transformer 220kV" in e["pages"][0]["text"] and "failed_pages" not in e


def test_corrupt_docx_is_failed_with_its_error(tmp_path):
    pytest.importorskip("docx")
    bad = tmp_path / "broken.docx"
    bad.write_bytes(b"PK\x03\x04 not a real document")
    e = _extract(bad)
    assert e["status"] == "FAILED" and e["error"]


def _png(fitz, gray=180):
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60), False)
    pix.clear_with(gray)
    return pix.tobytes("png")


def _insert_scan(fitz, page):
    """An image over the page and no text layer: what a scanned page looks like."""
    page.insert_image(fitz.Rect(36, 36, page.rect.width - 36, page.rect.height - 36), stream=_png(fitz))


def _pdf_with_scanned_page(path):
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Section 1 General conditions of contract and scope of supply. " * 3)
    _insert_scan(fitz, doc.new_page())  # no text layer: routed to OCR
    doc.save(str(path))


def test_ocr_failure_on_a_page_is_reported_not_complete(tmp_path, monkeypatch):
    """Real routing, OCR broken: a scanned page whose OCR raised must not leave the file COMPLETE."""
    pdf = tmp_path / "vol1.pdf"
    _pdf_with_scanned_page(pdf)
    fake = tmp_path / "not-tesseract.exe"
    fake.write_bytes(b"this is not a program")
    monkeypatch.setenv("TENDERMIND_TESSERACT_PATH", str(fake))
    e = _extract(pdf)
    assert e["status"] == "PARTIAL"
    assert e["failed_pages"] == [2]
    assert "Section 1 General conditions" in e["pages"][0]["text"]


def test_pdf_read_without_ocr_marks_scanned_pages(tmp_path):
    """No-OCR route (used when OCR routing is unavailable): a scanned page was not read."""
    pdf = tmp_path / "vol2.pdf"
    _pdf_with_scanned_page(pdf)
    from evaluation.run_real_benchmark import extract_pdf_text
    from app.pipeline.file_extractors import _entry
    e = _entry(extract_pdf_text(pdf, ocr_needed_hint=False))
    assert e["status"] == "PARTIAL" and e["failed_pages"] == [2]


def test_pdf_that_breaks_mid_way_keeps_read_pages_and_marks_where_it_stopped(tmp_path, monkeypatch):
    import evaluation.run_real_benchmark as RB
    if not RB.HAS_FITZ:
        pytest.skip("PyMuPDF not installed")

    class _Page:
        rect = (0, 0, 612, 792)

        def get_text(self, _kind):
            return "Payment terms: 30 days from invoice, retention five percent. " * 3

    class _Doc:
        def __iter__(self):
            yield _Page()
            raise RuntimeError("cannot read object 12")

        def __len__(self):
            return 3

        def close(self):
            pass

    monkeypatch.setattr(RB.fitz, "open", lambda _p: _Doc())
    from app.pipeline.file_extractors import _entry
    e = _entry(RB.extract_pdf_text(tmp_path / "x.pdf", ocr_needed_hint=False))
    assert e["status"] == "PARTIAL" and e["failed_pages"] == [2]
    assert "cannot read object 12" in e["error"]


def _four_page_pdf(path):
    """p1 full text · p2 short text only · p3 blank · p4 an image plus a short caption."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Clause 4.1 The contractor shall provide a performance bond of ten percent. " * 3)
    doc.new_page().insert_text((72, 72), "Annex B - intentionally short")
    doc.new_page()
    p4 = doc.new_page()
    _insert_scan(fitz, p4)
    p4.insert_text((72, 72), "Scanned sheet 4")
    doc.save(str(path))


def test_without_an_ocr_engine_pages_are_not_rendered_and_text_layers_are_kept(tmp_path, monkeypatch):
    import evaluation.tesseract_local_ocr as tlo
    rendered = []
    monkeypatch.setattr(tlo, "tesseract_available", lambda: False)
    monkeypatch.setattr(tlo, "ocr_page_with_tesseract", lambda *a, **k: rendered.append(a) or {})
    pdf = tmp_path / "vol.pdf"
    _four_page_pdf(pdf)
    pages = tlo.extract_pdf_with_tesseract_routing(pdf)
    assert rendered == []                                   # nothing drawn for an engine that is not there
    assert "Annex B - intentionally short" in pages[1]["text"] and not pages[1].get("error")
    assert not pages[2].get("error")                        # blank: nothing on it was left unread
    assert "Tesseract is not installed" in pages[3]["error"]  # an image the text layer may not cover
    assert "Scanned sheet 4" in pages[3]["text"]            # its text layer is still kept
    from app.pipeline.file_extractors import _entry
    e = _entry(pages)
    assert e["status"] == "PARTIAL" and e["failed_pages"] == [4]


def test_ocr_failure_keeps_the_text_layer_of_a_short_page(tmp_path, monkeypatch):
    import evaluation.tesseract_local_ocr as tlo
    monkeypatch.setattr(tlo, "tesseract_available", lambda: True)

    def broken(*_a, **_k):
        raise RuntimeError("tesseract crashed")

    monkeypatch.setattr(tlo, "ocr_page_with_tesseract", broken)
    pdf = tmp_path / "vol.pdf"
    _four_page_pdf(pdf)
    pages = tlo.extract_pdf_with_tesseract_routing(pdf)
    assert "Annex B - intentionally short" in pages[1]["text"] and not pages[1].get("error")
    assert pages[1]["ocr_error"] == "tesseract crashed"
    assert "error" not in pages[2] and pages[3]["error"] == "tesseract crashed"
    assert pages[3]["method"].endswith("_failed_RuntimeError")


def test_both_pdf_routes_agree_on_what_was_left_unread(tmp_path, monkeypatch):
    """Direct route: a short text-only page and a blank page were read, not flagged
    (every native tender has covers and dividers); only the scanned page was not.
    It used to flag every page under 50 characters, and each became a HIGH gap."""
    import evaluation.tesseract_local_ocr as tlo
    from app.pipeline.file_extractors import _entry, entry_has_failures
    pdf = tmp_path / "vol.pdf"
    _four_page_pdf(pdf)
    direct = _pdf(pdf, False)
    assert [p["method"] for p in direct[1:]] == ["fitz_short_text", "fitz_short_text", "scanned_no_text_ocr_needed"]
    monkeypatch.setattr(tlo, "tesseract_available", lambda: False)
    routed = tlo.extract_pdf_with_tesseract_routing(pdf)
    assert [bool(p.get("error")) for p in direct] == [bool(p.get("error")) for p in routed] == [False, False, False, True]
    assert _entry(direct)["failed_pages"] == _entry(routed)["failed_pages"] == [4]
    short_only = _entry(direct[1:3])
    assert "failed_pages" not in short_only and not entry_has_failures(short_only)


def _decorated_and_drawn_pdf(path):
    """p1 cover: logo + title · p2 divider: frame, header rule, background · p3 short page
    with a stamp · p4 drawing sheet (600 lines) + title block · p5 scan + 66-char stamp text."""
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    p = doc.new_page()
    p.insert_image(fitz.Rect(72, 40, 112, 80), stream=_png(fitz, 60))
    p.insert_text((72, 200), "Volume 2 - Technical Specifications")
    p = doc.new_page()
    p.draw_rect(fitz.Rect(0, 0, p.rect.width, p.rect.height), color=None, fill=(0.95, 0.95, 0.9))
    p.draw_rect(fitz.Rect(30, 30, p.rect.width - 30, p.rect.height - 30), color=(0, 0, 0), width=1)
    p.draw_line((72, 60), (p.rect.width - 72, 60), color=(0, 0, 0), width=0.5)
    p.insert_text((72, 300), "Annex 3 - Forms")
    p = doc.new_page()
    p.insert_image(fitz.Rect(400, 700, 480, 780), stream=_png(fitz, 90))
    p.insert_text((72, 100), "Approved - signed and stamped")
    p = doc.new_page()
    for k in range(600):
        x = 40 + (k * 7) % (p.rect.width - 80)
        p.draw_line((x, 60), (x + 30, p.rect.height - 120), color=(0, 0, 0), width=0.3)
    p.insert_text((p.rect.width - 200, p.rect.height - 40), "Sheet 3 of 9 - SLD")
    p = doc.new_page()
    _insert_scan(fitz, p)
    p.insert_text((72, p.rect.height - 20), "Stamped copy - Ministry of Energy - registry ref 4471/2026 - page 5")
    doc.save(str(path))


def test_logos_frames_and_stamps_are_not_unread_but_drawings_and_scans_are(tmp_path, monkeypatch):
    """A 40 pt logo, a page frame or a stamp made every cover and divider a HIGH
    'pages could not be read' gap; a drawing sheet with a title block was 'read'."""
    import evaluation.tesseract_local_ocr as tlo
    pdf = tmp_path / "vol.pdf"
    _decorated_and_drawn_pdf(pdf)
    direct = _pdf(pdf, False)
    monkeypatch.setattr(tlo, "tesseract_available", lambda: False)
    routed = tlo.extract_pdf_with_tesseract_routing(pdf)
    want = [False, False, False, True, True]
    assert [bool(p.get("error")) for p in direct] == want
    assert [bool(p.get("error")) for p in routed] == want
    assert "Stamped copy" in routed[4]["text"] and routed[4]["ocr_applied"] is False  # native layer, not OCR


def test_page_numbers_alone_do_not_make_an_unread_scan_partial():
    """Every page unread, a 1-character text layer each: FAILED (job FAILED, not 'complete: 1')."""
    from app.pipeline.file_extractors import _entry
    pages = [{"page_number": n, "text": str(n), "method": "tesseract_unavailable", "error": "OCR not available"}
             for n in (1, 2, 3)]
    assert _entry(pages)["status"] == "FAILED"


def test_a_scan_only_tender_fails_with_the_reason_on_the_job(tmp_path, monkeypatch):
    """The workspace shows only last_error for a FAILED job; it was empty."""
    import uuid as _uuid
    import evaluation.tesseract_local_ocr as tlo
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    monkeypatch.delenv("TENDERMIND_TWO_STAGE_LLM", raising=False)
    monkeypatch.setattr(tlo, "tesseract_available", lambda: False)
    fitz = pytest.importorskip("fitz")
    from app import processing
    from app.database import SessionLocal, init_db
    from app.models import ProcessingJob, Tender, TenderDocument
    init_db()
    tid = f"T16F-{_uuid.uuid4().hex[:6]}"
    (tmp_path / tid).mkdir()
    pdf = tmp_path / tid / "scanned-volume.pdf"
    doc = fitz.open()
    for _ in range(2):
        _insert_scan(fitz, doc.new_page())
    doc.save(str(pdf))
    db = SessionLocal()
    db.add(Tender(id=tid, title="scans"))
    db.add(TenderDocument(id=f"D-{tid}", tender_id=tid, title=pdf.name, doc_type="PDF", source_path=str(pdf),
                          original_filename=pdf.name))
    db.commit()
    job_id = processing.create_processing_job(db, tid).id
    db.close()
    processing.process_tender(tid, job_id)
    s = SessionLocal()
    job = s.query(ProcessingJob).get(job_id)
    status, err = job.status, job.last_error or ""
    s.close()
    assert status == "FAILED"
    assert "No document could be read" in err and "Tesseract is not installed" in err, err


def test_flag_off_analysis_keeps_the_extractor_status():
    """Without the two-stage flag the status was re-derived from the character count."""
    from evaluation.generic_extraction import _doc_status
    assert _doc_status({"status": "PARTIAL", "total_text_chars": 5000}) == "PARTIAL"
    assert _doc_status({"status": "FAILED", "total_text_chars": 3}) == "FAILED"
    assert _doc_status({"status": "COMPLETE", "total_text_chars": 5000}) == "COMPLETE"


def test_arabic_file_name_on_a_windows_console_does_not_lose_the_word_document(tmp_path, monkeypatch):
    """The extractors' diagnostic prints ran inside their try blocks: on a cp1252
    console an Arabic name raised UnicodeEncodeError and the document was dropped."""
    import io
    import sys
    import evaluation.run_real_benchmark as RB
    if not RB.HAS_DOCX:
        pytest.skip("python-docx not installed")
    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr(sys, "stdout", console)
    doc = tmp_path / "الجدول أ - أحكام وشروط عامة.doc"
    doc.write_bytes(b"not a real word file")
    pages = RB.extract_docx_text(str(doc))
    assert not any("charmap" in str(p.get("method")) + str(p.get("error")) for p in pages)
    console.flush()
    assert b"DOC_EXTRACTOR" in console.buffer.getvalue()   # the line is still logged, escaped


def test_excel_file_saved_with_the_old_extension_is_read(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.append(["Item", "Qty"])
    wb.active.append(["Busbar 132kV", 3])
    wb.save(tmp_path / "x.xlsx")
    misnamed = (tmp_path / "x.xlsx").rename(tmp_path / "2- ITB-Tech - Annex.xls")
    e = _extract(misnamed)
    assert "Busbar 132kV" in e["pages"][0]["text"] and "failed_pages" not in e


# ---------------------------------------------------------------- progress
def test_share_reports_a_slice_of_the_parent():
    from app.pipeline import progress
    seen = []
    with progress.listen(lambda *a: seen.append(a)):
        with progress.share(0.5, 0.25):
            progress.report("pages", 2, 4)
            with progress.share(0.5, 0.5):          # nested archive
                progress.report("pages", 1, 1)
        progress.report("ai", 1, 2)
    S = progress.SCALE
    assert seen == [("fraction", round(0.625 * S), S), ("fraction", round(0.75 * S), S), ("ai", 1, 2)]


def _zip_with_pdfs(path):
    import zipfile
    fitz = pytest.importorskip("fitz")
    with zipfile.ZipFile(path, "w") as z:
        for name, n in (("a.pdf", 6), ("b.pdf", 2)):
            doc = fitz.open()
            for i in range(n):
                doc.new_page().insert_text((72, 72), f"{name} page {i + 1}: the bidder shall submit a bid bond. " * 3)
            z.writestr(name, doc.tobytes())
        z.writestr("c.txt", "Clause: delivery within 90 days of the purchase order. " * 3)


def test_archive_progress_moves_forward_through_its_files(tmp_path):
    from app.pipeline import progress
    z = tmp_path / "pkg.zip"
    _zip_with_pdfs(z)
    seen = []
    with progress.listen(lambda *a: seen.append(a)):
        entries = _extract_all(z)
    assert len(entries) == 3
    assert {phase for phase, _, _ in seen} == {"fraction"}   # inner pages never reach the job raw
    values = [d / t for _, d, t in seen]
    assert values == sorted(values) and values[-1] == 1.0 and max(values) <= 1.0


def _extract_all(path):
    from app.pipeline.file_extractors import extract_any
    return extract_any(path, path.name, _pdf)


def test_zip_job_progress_is_not_pinned_at_99_during_extraction(tmp_path, monkeypatch):
    """A zip is estimated at 1 page; its first PDF's pages sent the bar to 99%."""
    import uuid as _uuid
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    monkeypatch.delenv("TENDERMIND_TWO_STAGE_LLM", raising=False)
    from app import processing
    from app.database import SessionLocal, init_db
    from app.models import ProcessingJob, Tender, TenderDocument
    from app.pipeline import file_extractors
    init_db()
    tid = f"T16Z-{_uuid.uuid4().hex[:6]}"
    (tmp_path / tid).mkdir()
    z = tmp_path / tid / "pkg.zip"
    _zip_with_pdfs(z)
    db = SessionLocal()
    db.add(Tender(id=tid, title="zip progress"))
    db.add(TenderDocument(id=f"D-{tid}", tender_id=tid, title=z.name, doc_type="ZIP", source_path=str(z),
                          original_filename=z.name))
    db.commit()
    job_id = processing.create_processing_job(db, tid).id
    db.close()
    snapshots, real = [], file_extractors.extract_any

    def spy(path, name, *a, **k):
        if "/" in name:  # a file inside the archive: what does the job show right now?
            s = SessionLocal()
            snapshots.append((name.split("/")[-1], s.query(ProcessingJob).get(job_id).progress))
            s.close()
        return real(path, name, *a, **k)

    monkeypatch.setattr(file_extractors, "extract_any", spy)
    processing.process_tender(tid, job_id)
    assert [n for n, _ in snapshots] == ["a.pdf", "b.pdf", "c.txt"]
    assert all(p is None or p <= 40 for _, p in snapshots), snapshots   # extraction owns 10-40%
    assert snapshots[1][1] and snapshots[1][1] > 10, snapshots          # and a.pdf moved it


def test_pdf_pages_move_the_bar_across_that_files_share(tmp_path, monkeypatch):
    """Two uploads: a 6-page PDF (estimate 6) and a text file (estimate 1). Mid-PDF,
    6 of 6 pages read = 6/7 of the extraction band."""
    import uuid as _uuid
    import evaluation.run_real_benchmark as RB
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    monkeypatch.delenv("TENDERMIND_TWO_STAGE_LLM", raising=False)
    fitz = pytest.importorskip("fitz")
    from app import processing
    from app.database import SessionLocal, init_db
    from app.models import ProcessingJob, Tender, TenderDocument
    from app.pipeline.progress import report
    init_db()
    tid = f"T16P-{_uuid.uuid4().hex[:6]}"
    (tmp_path / tid).mkdir()
    pdf, txt = tmp_path / tid / "a.pdf", tmp_path / tid / "b.txt"
    doc = fitz.open()
    for i in range(6):
        doc.new_page().insert_text((72, 72), f"page {i}: the bidder shall submit a bid bond. " * 3)
    doc.save(str(pdf))
    txt.write_text("Delivery within 90 days of the purchase order. " * 3, encoding="utf-8")
    db = SessionLocal()
    db.add(Tender(id=tid, title="pdf progress"))
    for f in (pdf, txt):
        db.add(TenderDocument(id=f"D-{tid}-{f.suffix}", tender_id=tid, title=f.name, doc_type="X",
                              source_path=str(f), original_filename=f.name))
    db.commit()
    job_id = processing.create_processing_job(db, tid).id
    db.close()
    seen = []

    def routing(path):
        report("pages", 6, 6)                      # first progress write of the job: always committed
        s = SessionLocal()
        seen.append(s.query(ProcessingJob).get(job_id).progress)
        s.close()
        return [{"page_number": i + 1, "text": f"page {i}: the bidder shall submit a bid bond.", "method": "x"}
                for i in range(6)]

    monkeypatch.setattr(RB, "_call_tesseract_routing", routing)
    processing.process_tender(tid, job_id)
    assert seen == [round(10 + 30 * 6 / 7, 1)]


# ---------------------------------------------------------------- cache
def _tender_file(name, data=b"payload"):
    from app.database import get_storage_root
    tid = f"T16-{uuid.uuid4().hex[:8]}"
    d = get_storage_root() / tid
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_bytes(data)
    return tid, p


def test_failures_are_stored_but_not_reused():
    """Stored: sections, materials, etc. read this file for the pages that were read.
    Not reused: the next run reads the file again instead of keeping the failure."""
    from app.pipeline.checkpoint import _extraction_path, file_digest, load_extraction, save_extraction
    from app.pipeline.file_extractors import _entry
    tid, p = _tender_file("pkg.zip")
    entries = [("pkg.zip/a.txt", _entry([_read(1)])), ("pkg.zip/b.docx", _entry([], "FAILED", "corrupt"))]
    save_extraction(tid, p, "pkg.zip", entries)
    assert _extraction_path(tid, file_digest(p)).is_file()
    assert load_extraction(tid, p, "pkg.zip") is None


def test_partially_read_file_is_not_reused():
    from app.pipeline.checkpoint import load_extraction, save_extraction
    from app.pipeline.file_extractors import _entry
    tid, p = _tender_file("vol1.pdf")
    save_extraction(tid, p, "vol1.pdf", [("vol1.pdf", _entry([_read(1), _failed(2)]))])
    assert load_extraction(tid, p, "vol1.pdf") is None


def test_clean_extraction_is_reused():
    from app.pipeline.checkpoint import load_extraction, save_extraction
    from app.pipeline.file_extractors import _entry
    tid, p = _tender_file("vol1.pdf")
    entries = [("vol1.pdf", _entry([_read(1)])), ("x.exe", _entry([], "UNSUPPORTED", "not a document"))]
    save_extraction(tid, p, "vol1.pdf", entries)
    assert load_extraction(tid, p, "vol1.pdf") == entries


def test_a_file_failing_the_same_way_again_is_reused(monkeypatch):
    """One page Tesseract always crashes on made every retry OCR the whole volume again.
    Now: read again once (the error may pass), then reuse while the readers are the same."""
    import app.pipeline.file_extractors as FE
    from app.pipeline.checkpoint import FAILED_READS_BEFORE_REUSE, load_extraction, save_extraction
    tools = {"ocr": True, "office": False, "unrar": False, "dwg": False}
    monkeypatch.setattr(FE, "extraction_tools", lambda: dict(tools))
    tid, p = _tender_file("vol1.pdf")
    entries = [("vol1.pdf", FE._entry([_read(1), _failed(2)]))]
    for _ in range(FAILED_READS_BEFORE_REUSE - 1):
        save_extraction(tid, p, "vol1.pdf", entries)
        assert load_extraction(tid, p, "vol1.pdf") is None
    save_extraction(tid, p, "vol1.pdf", entries)
    assert load_extraction(tid, p, "vol1.pdf") == entries
    tools["ocr"] = False  # a reader changed: its failures may read differently now
    assert load_extraction(tid, p, "vol1.pdf") is None


def test_a_different_failure_on_the_next_read_starts_the_count_again(monkeypatch):
    """Read 1 lost page 2, read 2 lost page 5 to a passing error: a third read can be
    clean, so read 2 is not frozen."""
    import app.pipeline.file_extractors as FE
    from app.pipeline.checkpoint import load_extraction, save_extraction
    monkeypatch.setattr(FE, "extraction_tools", lambda: {"ocr": "tesseract"})
    tid, p = _tender_file("vol1.pdf")
    save_extraction(tid, p, "vol1.pdf", [("vol1.pdf", FE._entry([_read(1), _failed(2), _read(5)]))])
    save_extraction(tid, p, "vol1.pdf", [("vol1.pdf", FE._entry([_read(1), _read(2), _failed(5)]))])
    assert load_extraction(tid, p, "vol1.pdf") is None


def test_an_unsupported_part_is_read_again_once_a_reader_is_installed(monkeypatch):
    """A .dwg read without ODA is UNSUPPORTED, not a failure: it was stored as clean
    and never read again after the converter was installed."""
    import app.pipeline.file_extractors as FE
    from app.pipeline.checkpoint import load_extraction, save_extraction
    tools = {"dwg": ""}
    monkeypatch.setattr(FE, "extraction_tools", lambda: dict(tools))
    tid, p = _tender_file("pkg.zip")
    entries = [("pkg.zip/a.txt", FE._entry([_read(1)])),
               ("pkg.zip/plan.dwg", FE._entry([], "UNSUPPORTED", "ODA File Converter not installed"))]
    save_extraction(tid, p, "pkg.zip", entries)
    assert load_extraction(tid, p, "pkg.zip") == entries  # nothing failed: reused while the readers stay
    tools["dwg"] = "oda"
    assert load_extraction(tid, p, "pkg.zip") is None


def test_failed_reads_restart_when_the_readers_change(monkeypatch):
    import app.pipeline.file_extractors as FE
    from app.pipeline.checkpoint import load_extraction, save_extraction
    tools = {"ocr": False, "office": False, "unrar": False, "dwg": False}
    monkeypatch.setattr(FE, "extraction_tools", lambda: dict(tools))
    tid, p = _tender_file("vol1.pdf")
    entries = [("vol1.pdf", FE._entry([_read(1), _failed(2)]))]
    save_extraction(tid, p, "vol1.pdf", entries)
    tools["ocr"] = True  # Tesseract installed after the first read
    save_extraction(tid, p, "vol1.pdf", entries)
    assert load_extraction(tid, p, "vol1.pdf") is None  # 1 failed read with these readers, not 2


def test_legacy_cached_silent_failure_is_read_again():
    import json
    from app.pipeline.checkpoint import _extraction_path, cache_dir, file_digest, load_extraction
    tid, p = _tender_file("specs.bak")
    cache_dir(tid).mkdir(parents=True, exist_ok=True)
    old = {"pages": [{"page_number": 1, "text": "", "method": "unknown_doc_ext"}], "page_count": 1,
           "total_text_chars": 0, "status": "PARTIAL"}
    _extraction_path(tid, file_digest(p)).write_text(
        json.dumps({"filename": "specs.bak", "entries": [{"name": "specs.bak", "result": old}]}), encoding="utf-8")
    assert load_extraction(tid, p, "specs.bak") is None


# ---------------------------------------------------------------- reported, not silent
def _documents(doc_results):
    from app.pipeline.two_stage_runner import adapt_doc_results, document_artifacts
    return document_artifacts(adapt_doc_results(doc_results)[1])


def test_unreadable_pages_reach_the_package_gaps():
    from app.pipeline.file_extractors import _entry
    from app.pipeline.gaps import analyze_package_gaps
    docs = _documents({"vol1.pdf": _entry([_read(1), _failed(2), _read(3), _failed(7)])})
    assert docs[0].failed_pages == [2, 7]
    (gap,) = [g for g in analyze_package_gaps(docs, []) if g.kind == "partial-extraction"]
    assert gap.evidence == ["vol1.pdf#p2", "vol1.pdf#p7"]
    assert "2 page(s) could not be read (pages 2, 7)" in gap.description


def test_every_page_failing_is_a_failed_extraction_gap():
    from app.pipeline.file_extractors import _entry
    from app.pipeline.gaps import analyze_package_gaps
    docs = _documents({"scan.pdf": _entry([_failed(1), _failed(2)])})
    kinds = [g.kind for g in analyze_package_gaps(docs, [])]
    assert kinds == ["failed-extraction"]


def test_document_with_pages_but_no_text_is_empty_ocr():
    from app.pipeline.file_extractors import _entry
    from app.pipeline.gaps import analyze_package_gaps
    docs = _documents({"blank.png": _entry([{"page_number": 1, "text": "", "ocr_applied": True,
                                              "method": "tesseract_image_eng"}])})
    assert docs[0].status == "PARTIAL"
    assert [g.kind for g in analyze_package_gaps(docs, [])] == ["empty-ocr"]


def test_one_gap_for_a_file_with_an_unreadable_page_and_no_text():
    from app.pipeline.file_extractors import _entry
    from app.pipeline.gaps import analyze_package_gaps
    blank = {"page_number": 1, "text": "", "ocr_applied": True, "method": "tesseract_5.4.0_ara+eng_psm6_dpi300"}
    docs = _documents({"scan.pdf": _entry([blank, _failed(2)])})
    assert docs[0].status == "PARTIAL"
    assert [g.kind for g in analyze_package_gaps(docs, [])] == ["partial-extraction"]


def test_unreadable_pages_become_a_risk_on_the_file():
    from app.pipeline.commercial_schedule import CommercialFacts
    from app.pipeline.file_extractors import _entry
    from app.pipeline.gaps import analyze_package_gaps
    from app.pipeline.risk_synthesis import derive_risk_signals
    gaps = analyze_package_gaps(_documents({"vol1.pdf": _entry([_read(1), _failed(2)])}), [])
    (risk,) = [r for r in derive_risk_signals(gaps, [], [], CommercialFacts(bid_security="5%"), [])
               if r.risk_type == "failed-extraction"]
    assert risk.source_document == "vol1.pdf"


def test_a_hash_in_a_file_name_is_not_cut_as_a_page_mark():
    from app.pipeline.commercial_schedule import CommercialFacts
    from app.pipeline.file_extractors import _entry
    from app.pipeline.gaps import analyze_package_gaps, evidence_page
    from app.pipeline.risk_synthesis import derive_risk_signals
    assert evidence_page("Addendum #1.pdf") == ("Addendum #1.pdf", None)
    assert evidence_page("Addendum #1.pdf#p12") == ("Addendum #1.pdf", "12")
    assert evidence_page("Sheet #pA.pdf") == ("Sheet #pA.pdf", None)
    gaps = analyze_package_gaps(_documents({"Addendum #1.pdf": _entry([_failed(1)])}), [])
    (risk,) = [r for r in derive_risk_signals(gaps, [], [], CommercialFacts(bid_security="5%"), [])
               if r.risk_type == "failed-extraction"]
    assert risk.source_document == "Addendum #1.pdf"


def test_gap_pages_are_not_asked_again_as_low_quality_scans():
    """A page OCR could not read is one gap, not also a 'check this scan' question."""
    from app.database import SessionLocal, init_db
    from app.issues import build_candidates
    from app.models import Tender, TenderAnalysis
    init_db()
    db = SessionLocal()
    tid = f"T16-{uuid.uuid4().hex[:8]}"
    db.add(Tender(id=tid, title="Scans"))
    df = {"gaps": [{"kind": "partial-extraction", "description": "vol1.pdf: 1 page(s) could not be read",
                    "evidence": ["vol1.pdf#p2"]},
                   {"kind": "failed-extraction", "description": "scan.pdf failed: boom", "evidence": ["scan.pdf"]},
                   {"kind": "failed-extraction", "description": "Addendum #1.pdf failed: boom",
                    "evidence": ["Addendum #1.pdf"]}],
          "page_quality": [{"document": "vol1.pdf", "page": 2, "confidence": None, "chars": 0},
                           {"document": "vol1.pdf", "page": 5, "confidence": 0.3, "chars": 400},
                           {"document": "scan.pdf", "page": 1, "confidence": None, "chars": 0},
                           {"document": "Addendum #1.pdf", "page": 1, "confidence": None, "chars": 0}]}
    db.add(TenderAnalysis(id=f"A-{tid}", tender_id=tid, requirements=[], documents=[], derived_features=df))
    db.commit()
    items = build_candidates(db, tid)
    db.close()
    partial = [i for i in items if i["kind"] == "partial-extraction"]
    assert len(partial) == 1 and partial[0]["title"] == "Some pages could not be read"
    assert partial[0]["priority"] == "HIGH"
    scans = [i for i in items if i["kind"] == "unreadable-pages"]
    assert [(i["source_document"], i["page"]) for i in scans] == [("vol1.pdf", "5")]
    failed = [i for i in items if i["kind"] == "failed-extraction"]
    assert sorted(i["source_document"] for i in failed) == ["Addendum #1.pdf", "scan.pdf"]


def _sync_with_gaps(db, tid, gaps):
    from app.issues import sync_issues
    from app.models import TenderAnalysis, TenderIssue
    db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tid).delete()
    db.add(TenderAnalysis(id=f"A-{uuid.uuid4().hex[:8]}", tender_id=tid, requirements=[], documents=[],
                          derived_features={"gaps": gaps}))
    db.commit()
    sync_issues(db, tid)
    db.commit()
    return sorted((i.kind, i.detail) for i in db.query(TenderIssue).filter(
        TenderIssue.tender_id == tid, TenderIssue.status == "OPEN",
        TenderIssue.kind.in_(["failed-extraction", "partial-extraction"])))


def test_reading_a_file_again_does_not_pile_up_extraction_issues():
    """The description quotes the reader's error (a temp folder) and the page list:
    each re-read added another OPEN HIGH item, and a file read in full kept them."""
    from app.database import SessionLocal, init_db
    from app.models import Tender
    init_db()
    db = SessionLocal()
    tid = f"T16-{uuid.uuid4().hex[:8]}"
    db.add(Tender(id=tid, title="re-reads"))
    db.commit()
    fail = lambda tmp: {"kind": "failed-extraction", "evidence": ["pkg.zip/g.docx"],  # noqa: E731
                        "description": f"pkg.zip/g.docx failed: Package not found at '{tmp}/g.docx'"}
    part = lambda pages: {"kind": "partial-extraction", "evidence": [f"vol1.pdf#p{n}" for n in pages],  # noqa: E731
                          "description": f"vol1.pdf: pages {pages} could not be read"}
    from app.models import TenderIssue
    assert len(_sync_with_gaps(db, tid, [fail("C:/T/tm_arc_ab12"), part([2, 3])])) == 2
    answered = db.query(TenderIssue).filter(TenderIssue.tender_id == tid,
                                            TenderIssue.kind == "failed-extraction").one()
    answered.answer = "Asked the client for a readable copy"  # a touched item is never retired
    db.commit()
    open_items = _sync_with_gaps(db, tid, [fail("C:/T/tm_arc_cd34"), part([3])])
    assert len(open_items) == 2 and ("partial-extraction", "vol1.pdf: pages [3] could not be read") in open_items
    assert db.query(TenderIssue).filter(TenderIssue.tender_id == tid,
                                        TenderIssue.kind == "failed-extraction").count() == 1
    still = _sync_with_gaps(db, tid, [])  # both files read in full
    assert [k for k, _d in still] == ["failed-extraction"]  # only the answered one stays
    db.close()


def test_a_hash_in_a_file_name_keeps_ambiguities_apart():
    from app.pipeline.ambiguity_groups import _doc_of, _page_of
    assert _doc_of(["Addendum #1.pdf#p3"]) == "Addendum #1.pdf" != _doc_of(["Addendum #2.pdf#p3"])
    assert _page_of(["x#p3.pdf#p2"]) == [2]
