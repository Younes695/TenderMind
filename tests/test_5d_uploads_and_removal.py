"""Stage 5D — 5 GB streamed uploads, removing uploaded files, interrupted jobs."""
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path / "store"))
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def tender(client):
    tid = f"T-5D-{uuid.uuid4().hex[:6]}"
    assert client.post("/api/tenders", json={"id": tid, "title": "5D"}).status_code == 200
    yield tid
    from app.database import SessionLocal
    from app.models import ProcessingJob, Tender, TenderDocument
    db = SessionLocal()
    try:
        db.query(TenderDocument).filter(TenderDocument.tender_id == tid).delete()
        db.query(ProcessingJob).filter(ProcessingJob.tender_id == tid).delete()
        db.query(Tender).filter(Tender.id == tid).delete()
        db.commit()
    finally:
        db.close()


def _up(client, tid, name, data):
    return client.post(f"/api/tenders/{tid}/documents", files=[("files", (name, data))])


def _stored(tid):
    from app.database import get_storage_root
    d = get_storage_root() / tid
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


def test_default_cap_is_2gb_and_plan_override(monkeypatch):
    # Was 5 GB; lowered to what the bundled Caddy front accepts (request_body max_size 2GB).
    from app.api.routes import _max_upload_bytes
    monkeypatch.delenv("TENDERMIND_MAX_UPLOAD_MB", raising=False)
    assert _max_upload_bytes() == 2 * 1024 ** 3
    monkeypatch.setenv("TENDERMIND_MAX_UPLOAD_MB_STARTER", "500")
    assert _max_upload_bytes("starter") == 500 * 1024 ** 2
    assert _max_upload_bytes("enterprise") == 2 * 1024 ** 3  # no plan override -> global


def test_upload_is_streamed_in_chunks_and_oversize_leaves_no_partial_file(client, tender, monkeypatch):
    import app.api.routes as r
    monkeypatch.setattr(r, "_UPLOAD_CHUNK", 1024)  # force many chunks
    monkeypatch.setenv("TENDERMIND_MAX_UPLOAD_MB", "1")
    ok = _up(client, tender, "ok.txt", b"a" * (1024 * 1024))
    assert ok.status_code == 200 and ok.json()["documents"][0]["size"] == 1024 * 1024
    big = _up(client, tender, "big.txt", b"b" * (1024 * 1024 + 1))
    assert big.status_code == 413 and "1 MB" in big.json()["detail"]
    assert _stored(tender) == ["ok.txt"]  # rejected upload removed from disk
    empty = _up(client, tender, "empty.txt", b"")
    assert empty.status_code == 400
    assert _stored(tender) == ["ok.txt"]


def test_remove_one_file(client, tender):
    a = _up(client, tender, "a.txt", b"alpha " * 50).json()["documents"][0]
    _up(client, tender, "b.txt", b"beta " * 50)
    r = client.delete(f"/api/tenders/{tender}/documents/{a['id']}")
    assert r.status_code == 200 and r.json()["removed_count"] == 1 and r.json()["remaining_count"] == 1
    titles = [d["title"] for d in client.get(f"/api/tenders/{tender}/documents").json()["documents"]]
    assert titles == ["b.txt"] and _stored(tender) == ["b.txt"]
    assert client.delete(f"/api/tenders/{tender}/documents/{a['id']}").status_code == 404


def test_remove_all_files(client, tender):
    _up(client, tender, "a.txt", b"alpha " * 50)
    _up(client, tender, "b.txt", b"beta " * 50)
    r = client.delete(f"/api/tenders/{tender}/documents")
    assert r.status_code == 200 and r.json()["removed_count"] == 2 and r.json()["remaining_count"] == 0
    assert client.get(f"/api/tenders/{tender}/documents").json()["count"] == 0
    assert _stored(tender) == []


def test_removed_file_is_not_processed(client, tender):
    from app.database import SessionLocal
    from app.processing import create_processing_job, process_tender
    wrong = _up(client, tender, "wrong.txt", b"Tender security of EGP 999 required. " * 20).json()["documents"][0]
    _up(client, tender, "right.txt", b"Payment in EGP within 30 days of invoice. " * 20)
    client.delete(f"/api/tenders/{tender}/documents/{wrong['id']}")
    db = SessionLocal()
    try:
        job = create_processing_job(db, tender)
        process_tender(tender, job.id)
    finally:
        db.close()
    a = client.get(f"/api/tenders/{tender}/analysis").json()
    names = [d.get("filename") for d in a.get("documents", [])]
    assert "right.txt" in names and "wrong.txt" not in names


def test_cannot_remove_files_while_processing(client, tender):
    from app.database import SessionLocal
    from app.models import ProcessingJob
    doc = _up(client, tender, "a.txt", b"alpha " * 50).json()["documents"][0]
    db = SessionLocal()
    try:
        db.add(ProcessingJob(id=f"JOB-{uuid.uuid4().hex[:8]}", tender_id=tender, status="PROCESSING"))
        db.commit()
    finally:
        db.close()
    assert client.delete(f"/api/tenders/{tender}/documents/{doc['id']}").status_code == 409
    assert client.delete(f"/api/tenders/{tender}/documents").status_code == 409


def test_interrupted_jobs_are_failed_on_startup(tender):
    from app.database import SessionLocal
    from app.main import _fail_interrupted_jobs
    from app.models import ProcessingJob
    jid = f"JOB-{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        db.add(ProcessingJob(id=jid, tender_id=tender, status="PROCESSING"))
        db.commit()
        assert _fail_interrupted_jobs(db) >= 1
        job = db.query(ProcessingJob).filter(ProcessingJob.id == jid).first()
        assert job.status == "FAILED" and "Interrupted" in job.last_error
    finally:
        db.close()


def test_spa_index_is_never_cached(client):
    """Stale index.html kept users on the previous build after a deploy."""
    from app.main import _dist_index
    import os
    if not os.path.exists(_dist_index):
        pytest.skip("frontend not built")
    for path in ("/", "/tenders/new", "/company-knowledge"):
        r = client.get(path)
        assert r.status_code == 200 and "no-store" in r.headers.get("cache-control", "")
