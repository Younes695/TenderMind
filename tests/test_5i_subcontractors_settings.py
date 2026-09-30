"""Stage 5I — subcontractor RFQ comparison, RFQ drafting, feedback, account settings."""
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


def _client_and_tender():
    from app.main import app
    c = TestClient(app)
    tid = f"SUB-{uuid.uuid4().hex[:6]}"
    assert c.post("/api/tenders", json={"id": tid, "title": "Sub test"}).status_code == 200
    return c, tid


def test_best_quotation_balances_fit_price_duration_terms():
    from app.subcontractors import score_quotations
    q = lambda name, price, dur, fit, terms: {"id": name, "contractor": name, "price": price, "duration_weeks": dur,
                                             "technical_fit": fit, "payment_terms_days": terms}
    out = {o["contractor"]: o for o in score_quotations([
        q("DesertCool", 1.94e6, 11, 94, 60), q("Najd", 2.08e6, 12, 88, 45),
        q("GulfAir", 1.87e6, 14, 71, 90), q("Rawafid", 2.21e6, 10, 90, 30), q("Cheap", 1.2e6, 9, 50, 90)])}
    assert out["DesertCool"]["is_best"] and "highest technical fit" in out["DesertCool"]["best_reason"]
    assert not out["Cheap"]["eligible"] and not out["Cheap"]["is_best"]  # cheapest but below 60% fit
    assert sum(o["is_best"] for o in out.values()) == 1


def test_rfq_flow_create_quote_select_delete():
    c, tid = _client_and_tender()
    r = c.post(f"/api/tenders/{tid}/rfqs", json={"reference": "RFQ-MECH-04", "package_name": "Mechanical Work Package",
                                                 "discipline": "HVAC", "invited_count": 6, "closes_at": "2026-10-03"})
    assert r.status_code == 200
    rid = r.json()["id"]
    for name, price, dur, fit, terms in [("A", 100, 10, 90, 60), ("B", 90, 12, 80, 30)]:
        resp = c.post(f"/api/rfqs/{rid}/quotations", json={"contractor": name, "price": price, "duration_weeks": dur,
                                                           "technical_fit": fit, "payment_terms_days": terms})
        assert resp.status_code == 200
    data = resp.json()
    assert data["quoted_count"] == 2 and data["invited_count"] == 6
    assert sum(q["is_best"] for q in data["quotations"]) == 1
    assert c.post(f"/api/rfqs/{rid}/quotations", json={"contractor": "X", "price": 1, "duration_weeks": 1,
                                                       "technical_fit": 150, "payment_terms_days": 1}).status_code == 400
    qid = data["quotations"][1]["id"]
    sel = c.post(f"/api/quotations/{qid}/select").json()
    assert sel["status"] == "AWARDED" and [q["selected"] for q in sel["quotations"] if q["id"] == qid] == [True]
    listed = c.get("/api/rfqs", params={"tender_id": tid}).json()["rfqs"]
    assert [x["reference"] for x in listed] == ["RFQ-MECH-04"]
    assert c.delete(f"/api/rfqs/{rid}").status_code == 200
    assert c.get("/api/rfqs", params={"tender_id": tid}).json()["rfqs"] == []


def test_rfq_draft_uses_tender_requirements_for_the_package():
    from app.database import SessionLocal
    from app.models import TenderAnalysis
    c, tid = _client_and_tender()
    db = SessionLocal()
    db.add(TenderAnalysis(id=f"AN-{uuid.uuid4().hex[:8]}", tender_id=tid, analysis_version="t", status="COMPLETED",
                          tender={}, evidence=[], documents=[], deadlines=[], commercial=None, risks=[], derived_features={},
                          requirements=[{"requirement_id": "R1", "summary": "HVAC chillers N+1 redundancy", "category": "TECHNICAL",
                                         "mandatory": True, "source_document": "SOW.pdf", "page_number": 212},
                                        {"requirement_id": "R2", "summary": "Tender security 2%", "category": "COMMERCIAL",
                                         "mandatory": True}]))
    db.commit(); db.close()
    rid = c.post(f"/api/tenders/{tid}/rfqs", json={"reference": "RFQ-1", "package_name": "Mechanical", "discipline": "HVAC"}).json()["id"]
    d = c.get(f"/api/rfqs/{rid}/draft").json()
    assert d["requirements_used"] == 1 and "HVAC chillers" in d["text"] and "SOW.pdf, p.212" in d["text"]
    assert "Tender security" not in d["text"]


def test_other_account_cannot_see_rfqs(monkeypatch):
    monkeypatch.setenv("TENDERMIND_AUTH_ENABLED", "1")
    from app.main import app
    a, b = TestClient(app, base_url="https://testserver"), TestClient(app, base_url="https://testserver")
    for cl in (a, b):
        cl.post("/api/auth/signup", json={"email": f"u-{uuid.uuid4().hex[:6]}@t.test", "password": "Tender2026"})
    tid = f"SUBA-{uuid.uuid4().hex[:6]}"
    a.post("/api/tenders", json={"id": tid, "title": "x"})
    rid = a.post(f"/api/tenders/{tid}/rfqs", json={"reference": "R", "package_name": "P"}).json()["id"]
    assert b.get("/api/rfqs").json()["rfqs"] == [] or all(r["id"] != rid for r in b.get("/api/rfqs").json()["rfqs"])
    assert b.post(f"/api/rfqs/{rid}/quotations", json={"contractor": "X", "price": 1, "duration_weeks": 1,
                                                       "technical_fit": 90, "payment_terms_days": 1}).status_code == 404
    assert b.post(f"/api/tenders/{tid}/rfqs", json={"reference": "R", "package_name": "P"}).status_code == 404


def test_feedback_and_upgrade_request_are_stored_per_user():
    from app.main import app
    c = TestClient(app)
    assert c.post("/api/feedback", json={"kind": "problem", "message": ""}).status_code == 400
    assert c.post("/api/feedback", json={"kind": "problem", "message": "OCR missed page 7", "page": "/tenders/T1"}).status_code == 200
    assert c.post("/api/feedback", json={"kind": "upgrade", "plan": "Professional"}).status_code == 200
    kinds = [i["kind"] for i in c.get("/api/feedback").json()["items"]]
    assert "problem" in kinds and "upgrade" in kinds


def test_profile_name_and_password_change():
    from app.main import app
    c = TestClient(app)
    email = f"p-{uuid.uuid4().hex[:6]}@t.test"
    c.post("/api/auth/signup", json={"email": email, "password": "Tender2026"})
    assert c.patch("/api/auth/me", json={"name": "Omar"}).json()["name"] == "Omar"
    assert c.post("/api/auth/change-password", json={"current_password": "wrong", "new_password": "NewPass2026"}).status_code == 401
    assert c.post("/api/auth/change-password", json={"current_password": "Tender2026", "new_password": "short"}).status_code == 400
    assert c.post("/api/auth/change-password", json={"current_password": "Tender2026", "new_password": "NewPass2026"}).status_code == 200
    c.post("/api/auth/logout")
    assert c.post("/api/auth/login", json={"email": email, "password": "NewPass2026"}).status_code == 200
