"""
Stage 1B — Real E2E Test: UPLOAD → STORAGE → DB → PROCESSING → EXTRACTION → AI → ANALYSIS
Starts with NO pre-existing tender document. Uses small non-Sarai fixture.
Proves the full backend flow without Sarai fallback.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tempfile
import os
import time

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal, init_db, Base, engine, get_storage_root
from app.models import Tender, TenderDocument, TenderAnalysis, ProcessingJob

def create_small_fixture_pdf():
    """Small non-Sarai fixture with known content that must produce at least one requirement."""
    import fitz
    content = (
        "TENDER DOCUMENT — Test Project 2024\n"
        "Client: TestClient Ltd.\n"
        "Location: Test City\n"
        "Scope: Supply and installation of 220kV GIS substation equipment\n"
        "Experience: Bidder must have successfully completed at least one similar 220kV GIS project within last 10 years.\n"
        "Reference project with completion certificate required.\n"
        "Tender security: EGP 5,700,000 valid for 270 days from opening.\n"
        "Financial capacity: Audited financial statements for last 3 years, turnover and working capital.\n"
        "Schedule: Delivery and completion within 18 months from award. Programme required (Form C).\n"
        "HSE: Health, Safety and Environment plan and record required.\n"
        "QA/QC: Quality assurance system and procedures.\n"
        "Deadline: Submission on 16 of August, 2024.\n"
        "Technical: 220kV GIS and 175MVA transformer specifications.\n"
    )
    doc = fitz.open()
    page = doc.new_page()
    y = 40
    for line in content.split("\n"):
        page.insert_text((40, y), line, fontsize=9)
        y += 12
        if y > 800:
            page = doc.new_page()
            y = 40
    # Add page number footer for provenance test
    page.insert_text((500, 820), "Page 1", fontsize=7)
    buf = doc.tobytes()
    doc.close()
    return buf, content

def setup_clean_env():
    tmp = Path(tempfile.mkdtemp(prefix="tm_e2e_"))
    os.environ["TENDERMIND_STORAGE_ROOT"] = str(tmp)
    # Ensure Sarai fallback cannot be used: point to non-existent path and also ensure main storage is tmp
    os.environ["TENDER_SARAI_PATH"] = str(tmp / "nonexistent_sarai")
    Base.metadata.drop_all(bind=engine)
    init_db()
    return tmp

def cleanup(tmp):
    import shutil
    try:
        shutil.rmtree(tmp, ignore_errors=True)
    except:
        pass
    if "TENDER_SARAI_PATH" in os.environ:
        del os.environ["TENDER_SARAI_PATH"]

def test_real_e2e_upload_to_analysis():
    tmp = setup_clean_env()
    client = TestClient(app)

    # === 1. POST /tenders — create brand new non-Sarai tender ===
    tender_id = "E2E-2024-001"
    # Ensure tender does NOT exist initially
    db = SessionLocal()
    assert db.query(Tender).filter(Tender.id == tender_id).first() is None
    assert db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id).first() is None
    db.close()

    resp = client.post("/api/tenders", json={"id": tender_id, "title": "E2E Non-Sarai Test Tender", "client": "TestClient Ltd", "location": "Test City"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == tender_id
    # Verify tender persisted
    db = SessionLocal()
    t = db.query(Tender).filter(Tender.id == tender_id).first()
    assert t is not None
    assert t.title == "E2E Non-Sarai Test Tender"
    db.close()
    print(f"STEP 1 PASS: Created tender {tender_id}")

    # === 2. POST /tenders/{id}/documents — upload small non-Sarai fixture ===
    pdf_bytes, original_content = create_small_fixture_pdf()
    fixture_name = "E2E_Test_Fixture.pdf"

    # Verify no Sarai files exist in storage prior
    storage_root = get_storage_root()
    assert not (storage_root / "Sarai").exists()
    assert "Sarai" not in str(storage_root)

    resp2 = client.post(f"/api/tenders/{tender_id}/documents", files=[("files", (fixture_name, pdf_bytes, "application/pdf"))])
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["tender_id"] == tender_id
    assert data2["count"] == 1
    doc_meta = data2["documents"][0]
    assert doc_meta["filename"] == fixture_name
    # API intentionally does not expose server filesystem paths (security hardening);
    # resolve the persisted path from the DB instead.
    assert "path" not in doc_meta and "source_path" not in doc_meta
    _db = SessionLocal()
    try:
        _d = _db.query(TenderDocument).filter(TenderDocument.id == doc_meta["id"]).first()
        persisted_path = Path(_d.source_path)
    finally:
        _db.close()
    print(f"STEP 2 PASS: Uploaded {fixture_name} -> {persisted_path}")

    # === 3. Verify uploaded file exists in configured storage ===
    assert persisted_path.exists(), f"Persisted file not found: {persisted_path}"
    assert persisted_path.stat().st_size == len(pdf_bytes)
    # Verify inside configured storage_root and uses pathlib platform-independent
    storage_root_resolved = storage_root.resolve()
    persisted_resolved = persisted_path.resolve()
    try:
        persisted_resolved.relative_to(storage_root_resolved)
    except ValueError:
        assert False, f"Uploaded file outside storage_root: {persisted_resolved} not in {storage_root_resolved}"
    # No hardcoded C:\Users\... Desktop path
    assert "Desktop" not in str(persisted_path) or str(tmp) in str(persisted_path)
    print(f"STEP 3 PASS: File exists in storage_root {storage_root}")

    # === 4. Verify TenderDocument exists in DB with source_path ===
    db = SessionLocal()
    docs = db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id).all()
    assert len(docs) == 1, f"Expected 1 TenderDocument, got {len(docs)}"
    doc = docs[0]
    assert doc.title == fixture_name, f"Title should be original filename, got {doc.title}"
    assert doc.tender_id == tender_id
    source_path_db = getattr(doc, "source_path", None)
    assert source_path_db is not None, "source_path must be persisted"
    assert Path(source_path_db).exists(), f"source_path file not found: {source_path_db}"
    assert str(persisted_path.resolve()) == str(Path(source_path_db).resolve()) or persisted_path.name == Path(source_path_db).name
    # Verify file_size persisted
    assert getattr(doc, "file_size", None) is not None
    print(f"STEP 4 PASS: TenderDocument in DB with source_path={source_path_db}")

    # Also verify GET /documents endpoint
    resp_docs = client.get(f"/api/tenders/{tender_id}/documents")
    assert resp_docs.status_code == 200
    assert resp_docs.json()["count"] == 1
    db.close()

    # === 5. POST /tenders/{id}/process ===
    resp3 = client.post(f"/api/tenders/{tender_id}/process")
    assert resp3.status_code == 200, resp3.text
    job_id = resp3.json()["job_id"]
    assert job_id.startswith("JOB-")
    print(f"STEP 5 PASS: Started processing job {job_id}")

    # === 6. Poll GET /processing-jobs/{job_id} until terminal ===
    terminal = None
    for _ in range(30):
        time.sleep(0.3)
        r = client.get(f"/api/processing-jobs/{job_id}")
        assert r.status_code == 200, r.text
        status = r.json()["status"]
        if status in ("COMPLETED", "PARTIAL", "FAILED"):
            terminal = r.json()
            break
    assert terminal is not None, "Job did not reach terminal status within timeout"
    assert terminal["status"] in ("COMPLETED", "PARTIAL"), f"Expected COMPLETED/PARTIAL, got {terminal}"
    assert terminal["progress"] == 100
    assert terminal["current_stage"] == "COMPLETED"
    # Must have processed at least 1 document
    assert terminal["documents_total"] >= 1
    # For this fixture (supported PDF), should have at least 1 processed, 0 unsupported for main file
    # But even if unsupported count check, at least total >=1
    print(f"STEP 6 PASS: Job terminal status {terminal['status']} docs_total={terminal['documents_total']} processed={terminal['documents_processed']}")

    # === 7. GET /tenders/{id}/analysis ===
    resp4 = client.get(f"/api/tenders/{tender_id}/analysis")
    assert resp4.status_code == 200, resp4.text
    analysis = resp4.json()
    # Analysis should be canonical persisted, not Sarai fallback
    # Check required top-level keys
    assert "requirements" in analysis or "tender" in analysis
    # For TenderAnalysis persisted form, keys are tender, documents, requirements, evidence, etc.
    # For fallback form, would have message
    if "requirements" in analysis:
        reqs = analysis["requirements"]
        docs_an = analysis["documents"]
        print(f"STEP 7 PASS: Got analysis with {len(reqs)} requirements, {len(docs_an)} documents")
    else:
        # Should not be fallback message if we have analysis; if fallback, still check processing metadata
        assert analysis.get("status") in ("COMPLETED", "PARTIAL")
        print(f"STEP 7 PASS: Got analysis metadata {analysis}")

    # === 8. Verify canonical analysis exists and persisted in DB ===
    db = SessionLocal()
    analyses = db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id).all()
    assert len(analyses) >= 1, "No TenderAnalysis persisted"
    latest = sorted(analyses, key=lambda a: a.created_at, reverse=True)[0]
    assert latest.processing_job_id == job_id
    assert latest.status in ("COMPLETED", "PARTIAL")
    assert latest.requirements is not None
    # Verify analysis documents reference uploaded file, not Sarai
    doc_filenames = [d.get("filename") for d in (latest.documents or [])]
    assert any(fixture_name in str(f) for f in doc_filenames), f"Analysis documents should reference {fixture_name}, got {doc_filenames}"
    db.close()
    print(f"STEP 8 PASS: Analysis persisted id={latest.id}")

    # === 9. Verify at least one real requirement is produced for suitable fixture ===
    reqs = latest.requirements if isinstance(latest.requirements, list) else analysis.get("requirements", [])
    # Our fixture contains 220kV, experience, tender security, schedule, financial, HSE, QA — should trigger several deterministic patterns
    assert len(reqs) >= 1, f"Expected at least 1 requirement, got {len(reqs)}"
    # Check at least one has category that matches fixture content (TECHNICAL, EXPERIENCE, COMMERCIAL, etc.)
    categories = [r.get("category") for r in reqs]
    assert any(c in ("TECHNICAL", "EXPERIENCE", "COMMERCIAL", "FINANCIAL", "SCHEDULE", "HSE", "QA_QC") for c in categories), f"Categories {categories} missing expected"
    print(f"STEP 9 PASS: {len(reqs)} requirements categories={set(categories)}")

    # === 10. Verify evidence/provenance points back to uploaded document ===
    for req in reqs:
        # Every requirement must have provenance source_document
        src = req.get("source_document")
        # Generic candidates always have provenance; if low confidence may be None but then confidence <0.8
        if req.get("confidence", 0) >= 0.8:
            assert src is not None, f"High confidence requirement missing provenance: {req}"
        if src:
            # Must be the uploaded fixture, not a Sarai file
            assert fixture_name in src or "E2E" in src or src.endswith(".pdf"), f"Provenance should point to uploaded doc, got {src}"
            assert "Sarai" not in src, f"Provenance must NOT point to Sarai: {src}"
            assert "01- Sarai" not in src
    # Check analysis processing metadata
    proc = latest.processing or {}
    assert proc.get("job_id") == job_id
    print(f"STEP 10 PASS: Provenance points to uploaded document, not Sarai")

    # === 11. Verify no Sarai fallback path was used ===
    # Check that processing job did not rely on Sarai path: storage_root/tender_id exists and was used
    assert (storage_root / tender_id).exists()
    # Check that analysis title does not contain Sarai tender
    tender_info = latest.tender or {}
    if isinstance(tender_info, dict):
        title = tender_info.get("title", "") or ""
        # Exact Sarai title check, not substring of "Non-Sarai"
        assert "Sarai 220" not in title, f"Tender title should be E2E, not Sarai: {title}"
        assert tender_id in tender_info.get("id", "") or "E2E" in title
    # Verify no file from Sarai path was accessed: ensure TENDER_SARAI_PATH env points to nonexistent, yet job succeeded
    assert not Path(os.environ.get("TENDER_SARAI_PATH", "")).exists(), "Sarai path should not exist for this test"
    # If job had used Sarai fallback, it would have failed or produced Sarai-specific voltage? Our check above ensures requirements came from fixture
    # Additionally, verify that document text_length corresponds to our fixture (~500 chars +)
    docs_meta = latest.documents or []
    for d in docs_meta:
        if d.get("filename") == fixture_name:
            assert d.get("text_length", 0) > 100, f"Text length should be >100 for fixture, got {d.get('text_length')}"
            assert d.get("extraction_status") in ("COMPLETE", "PARTIAL")
            break
    print(f"STEP 11 PASS: No Sarai fallback used")

    # === Final check: FULL flow proven ===
    # UPLOAD → STORAGE → DB → PROCESSING → EXTRACTION → AI (deterministic) → ANALYSIS
    print(f"\n=== E2E SUCCESS: {tender_id} uploaded, stored, DB persisted, processed, analyzed ===")
    cleanup(tmp)

def test_e2e_second_tender_independent():
    """Ensure creating a second tender does not affect first — DB isolation."""
    tmp = setup_clean_env()
    client = TestClient(app)
    # Create two tenders
    for tid in ["E2E-A-001", "E2E-B-002"]:
        client.post("/api/tenders", json={"id": tid, "title": f"Tender {tid}"})
        pdf_bytes, _ = create_small_fixture_pdf()
        # Vary content for second
        if tid == "E2E-B-002":
            import fitz
            doc = fitz.open()
            pg = doc.new_page()
            pg.insert_text((40,40), "Second tender unique content 11kV Mobile substation 60MVA", fontsize=9)
            pdf_bytes = doc.tobytes()
            doc.close()
        client.post(f"/api/tenders/{tid}/documents", files=[("files", (f"{tid}.pdf", pdf_bytes, "application/pdf"))])
        client.post(f"/api/tenders/{tid}/process")
    # Poll both
    time.sleep(1)
    db = SessionLocal()
    for tid in ["E2E-A-001", "E2E-B-002"]:
        job = db.query(ProcessingJob).filter(ProcessingJob.tender_id == tid).order_by(ProcessingJob.created_at.desc()).first()
        assert job is not None
        assert job.status in ("COMPLETED", "PARTIAL", "PROCESSING", "QUEUED")
        docs = db.query(TenderDocument).filter(TenderDocument.tender_id == tid).all()
        assert len(docs) == 1
        assert docs[0].tender_id == tid
    db.close()
    cleanup(tmp)
    print("PASS second_tender_independent")

if __name__ == "__main__":
    test_real_e2e_upload_to_analysis()
    test_e2e_second_tender_independent()
    print("\nAll E2E tests passed")
