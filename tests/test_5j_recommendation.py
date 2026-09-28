"""Stage 5J — recommendation text, compliance %, email draft, company profile, value estimate."""
import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


def _detail(statuses):
    return {"available": True, "decision": {"decision": "REVIEW"},
            "requirements": [{"mandatory": True, "status": s, "requirement": f"req {i} {s}", "source_document": "RFP.pdf",
                              "page_or_section": f"p.{i}"} for i, s in enumerate(statuses)]}


def test_recommendation_explains_the_rule_decision_in_both_languages():
    from app.recommendation import build_recommendation
    d = _detail(["PASS", "PASS", "MISSING_EVIDENCE", "REVIEW"])
    en = build_recommendation(d, {"deadlines": [{"type": "submission", "date": "2026-11-02"}], "risks": []},
                              {"missing_open": 1, "question_open": 3}, "en")
    assert en["headline"].startswith("Recommendation: bid only if") and en["match_percent"] == 50
    titles = [s["title"] for s in en["sections"]]
    assert "Before bidding, close these gaps" in titles and "Key dates" in titles
    assert any("1 missing item(s) and 3 open question(s)" in n for n in en["notes"])
    ar = build_recommendation(d, None, None, "ar")
    assert ar["headline"].startswith("التوصية") and ar["match_percent"] == 50
    assert build_recommendation({"available": False}, None, None)["decision"] is None


def test_email_draft_uses_company_profile_and_open_questions():
    from app.recommendation import build_email
    mail = build_email({"id": "TURAIF-01", "title": "Turaif 132kV Substation", "client": "SEC"},
                       {"name": "Nile Power Contracting", "intro": "EPC contractor for 132-500 kV substations.",
                        "contact_name": "Omar Hassan", "email": "tenders@nilepower.example"},
                       [{"title": "Unclear wording — ask for clarification", "detail": "Bond amount TBD",
                         "source_document": "RFP.pdf", "page": "4"}],
                       [{"detail": "3 forms / annexes are mentioned but not in the package: ANNEX X"}])
    assert "Turaif 132kV Substation" in mail["subject"]
    for part in ("Dear SEC,", "Nile Power Contracting", "EPC contractor", "1. Bond amount TBD (RFP.pdf, p. 4)",
                 "ANNEX X", "Omar Hassan", "tenders@nilepower.example"):
        assert part in mail["body"], part
    assert "[Company name]" in build_email({"id": "T", "title": "T"}, None, [], [])["body"]


def test_profile_recommendation_email_and_estimate_endpoints():
    from app.database import SessionLocal
    from app.main import app
    from app.models import MarketAward
    c = TestClient(app)
    tid = f"REC-{uuid.uuid4().hex[:6]}"
    c.post("/api/tenders", json={"id": tid, "title": "Sample 132kV Substation", "client": "SEC"})
    assert c.put("/api/company-profile", json={"name": "Nile Power", "intro": "x" * 5000}).json()["intro"] == "x" * 2000
    assert c.get("/api/company-profile").json()["name"] == "Nile Power"
    rec = c.get(f"/api/tenders/{tid}/recommendation", params={"lang": "en"}).json()
    assert rec["decision"] is None and "process the tender" in rec["headline"]
    mail = c.get(f"/api/tenders/{tid}/email-draft").json()
    assert mail["company_profile_complete"] and "Nile Power" in mail["body"]
    db = SessionLocal()
    for i, (kv, amt) in enumerate([(110, 6e6), (132, 9e6), (132, 12e6), (220, 30e6), (33, 1e6)]):
        db.add(MarketAward(id=f"MA-{uuid.uuid4().hex[:8]}", external_id=f"T5J-{uuid.uuid4().hex}", title=f"{kv}kV substation {i}",
                           country="X", kind="substation", kv=kv, amount_usd=amt, awarded_at=dt.datetime(2026, 1, 1)))
    db.commit(); db.close()
    est = c.get(f"/api/tenders/{tid}/value-estimate").json()
    assert est["available"] and est["kind"] == "substation" and est["kv"] == 132
    assert est["low"] <= est["median"] <= est["high"] and est["comparables"] >= 3 and est["examples"]


def test_estimate_refuses_without_enough_comparables():
    from app.database import SessionLocal
    from app.market import estimate
    db = SessionLocal()
    try:
        assert estimate(db, "Supply of office furniture")["available"] is False
        r = estimate(db, "765kV transmission line interconnector")
        assert r["available"] is False or r["comparables"] >= 3
    finally:
        db.close()


def test_award_price_parsing():
    from app.market import _PRICE, classify_kind, max_kv
    assert _PRICE.search("Signed Contract Price: USD 7,052,665.00 and more").group(1) == "7,052,665.00"
    assert classify_kind("Construction of 330kV Transmission Lines") == "transmission line"
    assert max_kv("110/35/10 kV Shari substation and 220kV line") == 220


def test_tender_voltage_comes_from_title_and_unevaluated_match_is_not_zero():
    from app.market import main_kv
    from app.recommendation import build_recommendation
    assert main_kv("Turaif 132kV Substation", "connection to the 500kV grid; 132kV bays; 132 kV GIS") == 132
    assert main_kv("New substation", "13.8kV aux; 132kV bays; 132 kV GIS; 380kV line") == 132
    r = build_recommendation(_detail(["MISSING_EVIDENCE", "MISSING_EVIDENCE"]), None, None)
    assert r["match_percent"] is None and "not measured yet" in r["notes"][0]


def test_epc_tenders_compare_with_epc_awards_not_equipment_supply():
    from app.market import scope_of
    assert scope_of("Design, Supply & installation of 132/33kV substations") == "epc"
    assert scope_of("Supplying 36 and 11 KV Switchgear and Equipment") == "supply"
    assert scope_of("LSTK power transformer foundation and substation") == "epc"
