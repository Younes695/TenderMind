"""Stage 4G pilot tests (fast: TestClient + direct calls; no live server, no Sarai)."""
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.database import Base, SessionLocal, engine
from app import models as M

P = Path(__file__).resolve().parents[1]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    dbfile = tmp_path / "t4g.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{dbfile}")
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path / "uploads"))
    # rebind engine session for isolation
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    eng = create_engine(f"sqlite:///{dbfile}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    import app.database as DB
    monkeypatch.setattr(DB, "SessionLocal", sessionmaker(autocommit=False, autoflush=False, bind=eng))
    import app.api.routes as R
    monkeypatch.setattr(R, "SessionLocal", DB.SessionLocal, raising=False)
    import app.processing as PR
    monkeypatch.setattr(PR, "SessionLocal", DB.SessionLocal)
    (tmp_path / "uploads").mkdir(exist_ok=True)
    return TestClient(main_module.app)


def _tender(client, tid="T-4G-1"):
    r = client.post("/api/tenders", json={"id": tid, "title": "Pilot"})
    assert r.status_code == 200, r.text
    return tid


def _upload(client, tid, name, content: bytes):
    return client.post(f"/api/tenders/{tid}/documents", files={"files": (name, content)})


def test_fresh_job_and_duplicate_active_prevention(client):
    from app.processing import create_processing_job
    from app.database import SessionLocal as _SL
    tid = _tender(client)
    db = _SL()
    job = create_processing_job(db, tid)
    assert job.status == "QUEUED"
    with pytest.raises(ValueError, match="already exists"):
        create_processing_job(db, tid)
    db.close()
    # API mirrors with 409
    r = client.post(f"/api/tenders/{tid}/process")
    assert r.status_code == 409


def test_reprocess_after_terminal_creates_new_job(client):
    from app.processing import create_processing_job, process_tender
    from app.database import SessionLocal as _SL
    tid = _tender(client, "T-4G-RE")
    _upload(client, tid, "a.txt", b"The 220kV GIS transformer must be installed and tested. " * 10)
    db = _SL()
    j1 = create_processing_job(db, tid)
    process_tender(tid, j1.id)  # legacy path, deterministic
    db2 = _SL()
    jobs = db2.query(M.ProcessingJob).filter(M.ProcessingJob.tender_id == tid).all()
    assert {j.status for j in jobs} <= {"COMPLETED", "PARTIAL", "FAILED"}
    j2 = create_processing_job(db2, tid)  # explicit reprocess: NEW job, no silent dup
    assert j2.id != j1.id
    db.close()
    db2.close()


def test_stage_events_recorded_and_refresh_stable(client):
    from app.processing import create_processing_job, process_tender
    from app.database import SessionLocal as _SL
    tid = _tender(client, "T-4G-STG")
    _upload(client, tid, "a.txt", b"Delivery within twelve months please. " * 10)
    db = _SL()
    job = create_processing_job(db, tid)
    process_tender(tid, job.id)
    db2 = _SL()
    evs = db2.query(M.StageEvent).filter(M.StageEvent.job_id == job.id).all()
    stages = [e.stage for e in evs]
    assert "INVENTORY" in stages and "EXTRACTION" in stages and "PERSISTENCE" in stages
    assert all(e.created_at for e in evs)
    # refresh: job endpoint returns same terminal state + history twice
    r1 = client.get(f"/api/processing-jobs/{job.id}").json()
    r2 = client.get(f"/api/processing-jobs/{job.id}").json()
    assert r1["status"] == r2["status"] and len(r1["stage_history"]) == len(r2["stage_history"]) > 0
    db.close()
    db2.close()


def test_partial_on_unsupported_and_failed_files(client):
    from app.processing import create_processing_job, process_tender
    from app.database import SessionLocal as _SL
    tid = _tender(client, "T-4G-PART")
    _upload(client, tid, "a.dwg", b"fakecad")
    db = _SL()
    job = create_processing_job(db, tid)
    process_tender(tid, job.id)
    db2 = _SL()
    j = db2.query(M.ProcessingJob).filter(M.ProcessingJob.id == job.id).first()
    assert j.status == "PARTIAL" and j.documents_unsupported == 1
    db.close()
    db2.close()


def test_security_upload_guards(client):
    tid = _tender(client, "T-4G-SEC")
    r = _upload(client, tid, "../evil.txt", b"x")
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        doc = r.json()["documents"][0] if "documents" in r.json() else r.json()
        # stored filename sanitized; resolved path confined to tender storage root
        assert ".." not in doc.get("filename", "") and ".." not in doc.get("source_path", "")
    r = _upload(client, tid, "weird.xyz", b"data")
    assert r.status_code == 200
    assert "UNSUPPORTED" in json.dumps(r.json())
    r1 = _upload(client, tid, "dup.txt", b"one")
    r2 = _upload(client, tid, "dup.txt", b"two")
    assert r1.status_code == r2.status_code == 200  # collision rename, no overwrite crash
    # Cap is configurable (default 5 GB); pin it to
    # 1MB here so the rejection path is exercised without a huge payload.
    import os as _os
    _old = _os.environ.get("TENDERMIND_MAX_UPLOAD_MB")
    _os.environ["TENDERMIND_MAX_UPLOAD_MB"] = "1"
    try:
        r = _upload(client, tid, "big.bin", b"x" * (1024 * 1024 + 1))
        assert r.status_code == 413  # Payload Too Large, partial file removed
        r = _upload(client, tid, "ok.bin", b"x" * (1024 * 1024))
        assert r.status_code == 200
    finally:
        if _old is None:
            _os.environ.pop("TENDERMIND_MAX_UPLOAD_MB", None)
        else:
            _os.environ["TENDERMIND_MAX_UPLOAD_MB"] = _old


def test_analysis_backward_compatible_keys(client):
    from app.processing import create_processing_job, process_tender
    from app.database import SessionLocal as _SL
    tid = _tender(client, "T-4G-API")
    _upload(client, tid, "a.txt", b"Payment in EGP within 30 days. " * 10)
    db = _SL()
    job = create_processing_job(db, tid)
    process_tender(tid, job.id)
    db.close()
    a = client.get(f"/api/tenders/{tid}/analysis").json()
    for k in ("tender", "documents", "requirements", "evidence", "processing", "status"):
        assert k in a, k
    # endpoint presence (routes registered, API stable)
    assert client.get(f"/api/tenders/{tid}/documents").status_code == 200


def test_ai_budget_observable_stub():
    from app.pipeline import intelligence_runner as IR
    from app.pipeline.contracts import SourceText
    from app.pipeline.ai_router import AITask, Router, QwenMinimalContractProvider
    prov = QwenMinimalContractProvider(transport=lambda c: (
        {"summary": "s", "category": "TECHNICAL", "mandatory": None,
         "applicable_entity": None}, "ok", 0.01, "{}"))
    router = Router({AITask.REQUIREMENT_NORMALIZATION.value: prov})
    a, tel = IR.run_intelligence(
        "T", [SourceText("A.pdf", 1, ("The 220kV GIS must be installed ok " * 40))], router=router)
    for k in ("candidates_generated", "candidates_compressed", "candidates_structured_covered",
              "candidates_sent_to_ai", "model_call_count", "success_count", "failure_count",
              "requirements_final"):
        assert hasattr(tel, k), k


def test_no_mock_stats_in_analysis_shape(client):
    # analysis payload must not contain demo/score placeholders
    from app.processing import create_processing_job, process_tender
    from app.database import SessionLocal as _SL
    tid = _tender(client, "T-4G-REAL")
    _upload(client, tid, "a.txt", b"Delivery within twelve months. " * 10)
    db = _SL()
    job = create_processing_job(db, tid)
    process_tender(tid, job.id)
    db.close()
    blob = client.get(f"/api/tenders/{tid}/analysis").text.lower()
    for token in ("sar 12.5m", "92%", "82/100", "demo", "mock"):
        assert token not in blob
