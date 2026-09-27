"""Stage 5G — per-account data isolation (app/access.py).

Before 5G any signed-up account could read, change and delete every tender
and company document on the server.
"""
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_auth_on(monkeypatch):
    monkeypatch.setenv("TENDERMIND_AUTH_ENABLED", "1")
    monkeypatch.setenv("TENDERMIND_SIGNUP_ENABLED", "1")
    monkeypatch.setenv("TENDERMIND_AUTH_EMAIL", "admin@tm.test")
    monkeypatch.setenv("TENDERMIND_AUTH_PASSWORD", "Admin2026x")
    from app.main import app
    return app


def _account(app):
    c = TestClient(app, base_url="https://testserver")
    c.__enter__()
    email = f"u-{uuid.uuid4().hex[:8]}@tm.test"
    assert c.post("/api/auth/signup", json={"email": email, "password": "Tender2026"}).status_code == 200
    return c, email


def _tender(c):
    tid = f"T-{uuid.uuid4().hex[:8]}"
    assert c.post("/api/tenders", json={"id": tid, "title": "Private"}).status_code == 200
    return tid


def test_other_account_cannot_see_or_touch_a_tender(app_auth_on):
    alice, _ = _account(app_auth_on)
    bob, _ = _account(app_auth_on)
    tid = _tender(alice)

    assert tid in [t["id"] for t in alice.get("/api/tenders").json()]
    assert tid not in [t["id"] for t in bob.get("/api/tenders").json()]
    for path in (f"/api/tenders/{tid}", f"/api/tenders/{tid}/documents", f"/api/tenders/{tid}/decision",
                 f"/api/tenders/{tid}/export", f"/api/tenders/{tid}/evaluation", f"/api/tenders/{tid}/audit"):
        assert bob.get(path).status_code == 404, path
    assert bob.delete(f"/api/tenders/{tid}/documents").status_code == 404
    assert bob.post(f"/api/tenders/{tid}/process").status_code == 404
    assert bob.post(f"/api/tenders/{tid}/decision/override",
                    json={"reviewer": "x", "new_decision": "BID", "reason": "x"}).status_code == 404
    # Owner still has full access.
    assert alice.get(f"/api/tenders/{tid}").status_code == 200


def test_demo_tender_is_shared_read_only(app_auth_on):
    bob, _ = _account(app_auth_on)
    assert "SA-2018-HV2" in [t["id"] for t in bob.get("/api/tenders").json()]
    assert bob.get("/api/tenders/SA-2018-HV2/requirements").status_code == 200
    r = bob.post("/api/tenders/SA-2018-HV2/decision/override",
                 json={"reviewer": "x", "new_decision": "BID", "reason": "x"})
    assert r.status_code == 403


def test_company_documents_are_per_account(app_auth_on):
    alice, _ = _account(app_auth_on)
    bob, _ = _account(app_auth_on)
    up = alice.post("/api/company-documents",
                    files={"files": ("profile.txt", b"Turnover EGP 1.2 billion", "text/plain")})
    assert up.status_code == 200
    doc_id = up.json()["documents"][0]["id"]
    assert [d["id"] for d in alice.get("/api/company-documents").json()["documents"]] == [doc_id]
    assert bob.get("/api/company-documents").json()["count"] == 0
    assert bob.delete(f"/api/company-documents/{doc_id}").status_code == 404
    assert alice.delete(f"/api/company-documents/{doc_id}").status_code == 200


def test_evaluation_only_uses_the_owners_company_documents(app_auth_on):
    from app.database import SessionLocal
    from app.engines.tender_bridge import company_paragraphs
    alice, a_email = _account(app_auth_on)
    bob, b_email = _account(app_auth_on)
    alice.post("/api/company-documents", files={"files": ("a.txt", b"ALICE-SECRET annual turnover of the company is EGP 1.2 billion", "text/plain")})
    r = bob.post("/api/company-documents", files={"files": ("b.txt", b"BOB-SECRET annual turnover of the company is EGP 3.4 billion", "text/plain")})
    assert r.status_code == 200, r.text
    db = SessionLocal()
    try:
        a_text = " ".join(p["text"] for p in company_paragraphs(db, a_email))
        b_text = " ".join(p["text"] for p in company_paragraphs(db, b_email))
    finally:
        db.close()
    assert "ALICE-SECRET" in a_text and "BOB-SECRET" not in a_text
    assert "BOB-SECRET" in b_text and "ALICE-SECRET" not in b_text


def test_evaluation_evidence_company_is_not_readable(app_auth_on):
    bob, _ = _account(app_auth_on)
    assert bob.get("/api/company/OUR_COMPANY").status_code == 404
    assert bob.get("/api/company/HYOSUNG_GIZA").status_code == 200


def test_processing_job_of_other_account_is_hidden(app_auth_on):
    from app.database import SessionLocal
    from app.models import ProcessingJob
    alice, _ = _account(app_auth_on)
    bob, _ = _account(app_auth_on)
    tid = _tender(alice)
    db = SessionLocal()
    try:
        job = ProcessingJob(id=f"JOB-{uuid.uuid4().hex[:8]}", tender_id=tid, status="COMPLETED")
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()
    assert alice.get(f"/api/processing-jobs/{job_id}").status_code == 200
    assert bob.get(f"/api/processing-jobs/{job_id}").status_code == 404


def test_legacy_rows_without_owner_belong_to_env_admin_only(app_auth_on):
    from app.database import SessionLocal
    from app.models import Tender
    tid = f"LEGACY-{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    try:
        db.add(Tender(id=tid, title="old"))
        db.commit()
    finally:
        db.close()
    bob, _ = _account(app_auth_on)
    assert bob.get(f"/api/tenders/{tid}").status_code == 404
    admin = TestClient(app_auth_on, base_url="https://testserver")
    admin.__enter__()
    assert admin.post("/api/auth/login", json={"email": "admin@tm.test", "password": "Admin2026x"}).status_code == 200
    assert admin.get(f"/api/tenders/{tid}").status_code == 200


@pytest.mark.parametrize("pw,ok", [("change-me-to-a-strong-password1", False), ("short1", False),
                                   ("onlylettersnodigits", False), ("Str0ng-Admin-2026", True)])
def test_production_refuses_weak_admin_password(monkeypatch, pw, ok):
    from app.auth import validate_auth_config
    monkeypatch.setenv("TENDERMIND_ENV", "production")
    monkeypatch.setenv("TENDERMIND_SESSION_SECRET", "x" * 64)
    monkeypatch.setenv("TENDERMIND_AUTH_EMAIL", "admin@tm.test")
    monkeypatch.setenv("TENDERMIND_AUTH_PASSWORD", pw)
    monkeypatch.delenv("TENDERMIND_AUTH_ENABLED", raising=False)
    if ok:
        validate_auth_config()
    else:
        with pytest.raises(RuntimeError):
            validate_auth_config()


def test_security_headers_and_health(app_auth_on):
    c = TestClient(app_auth_on, base_url="https://testserver")
    r = c.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
