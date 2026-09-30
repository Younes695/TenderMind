"""Stage 6 Task 3 — company capabilities and the eligibility gate."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.eligibility import check
from app.pipeline.contracts import SourceText


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


def _src(*pages):
    return [SourceText(source_document="ITB.pdf", page_number=i + 1, text=t) for i, t in enumerate(pages)]


CAP = {"work_types": ["substation"], "max_kv": 132, "countries": ["Saudi Arabia"], "registrations": [],
       "certifications": ["ISO 9001"], "years_experience": 12, "annual_turnover": 80e6, "turnover_currency": "SAR"}
PAGES = ("Instructions to bidders for the Riyadh project, Kingdom of Saudi Arabia.",
         "The Bidder shall be certified to ISO 9001 and ISO 45001.",
         "The Bidder shall have minimum 10 years of experience in similar substation works.",
         "Average annual turnover not less than SAR 50 million over the last 3 years.")


def _by_key(res):
    return {c["key"]: c for c in res["checks"]}


def test_empty_profile_skips_and_never_blocks():
    for cap in (None, {}, {k: ([] if isinstance(v, list) else None) for k, v in CAP.items()}):
        res = check(cap, "Turaif 380kV Substation", _src(*PAGES))
        assert res["status"] == "SKIPPED" and "Settings" in res["note"]


def test_voltage_above_company_limit_fails_with_evidence_page():
    res = check(CAP, "Turaif 380kV Substation", _src(*PAGES, "Two 380 kV GIS bays shall be added."))
    v = _by_key(res)["voltage"]
    assert res["status"] == "INELIGIBLE" and v["result"] == "FAIL" and "380 kV" in v["detail"]
    assert v["evidence"]["page"] == 5


def test_title_voltage_with_decimal_secondary_is_read_not_the_drawings():
    # SEC RFX-4000077315 "Maaden 132/13.8kV Substation": "13.8" broke the title match, so the gate fell
    # back to the most frequent kV in the drawings (the 380 kV upstream network) and failed a 220 kV company.
    drawings = _src("TRANSFORMER FROM 380kV (FUTURE)", "380kV GIS SWGR", "380kV BUSBAR", "132kV CABLE/PHASE")
    v = _by_key(check(CAP, "Construction of Maaden 132/13.8kV Substation", drawings))["voltage"]
    assert v["result"] == "PASS" and "132 kV" in v["detail"]


@pytest.mark.parametrize("text, kv", [("132/13.8kV", 132), ("132/13.8 kV", 132), ("380/132/13.8kV", 380),
                                      ("33/11kV", 33), ("132kV", 132),
                                      ("13.8kV", None)])  # a bare decimal voltage stays unread, as before
def test_kv_parsing_accepts_decimal_secondary_voltages(text, kv):
    from app.tender_facts import max_kv
    assert max_kv(text) == kv


def test_voltage_evidence_found_when_written_with_a_decimal_secondary():
    v = _by_key(check(CAP, "Riyadh 132/13.8kV Substation", _src(*PAGES, "Scope: one 132/13.8 kV GIS substation.")))
    assert v["voltage"]["result"] == "PASS" and v["voltage"]["evidence"]["page"] == 5


def test_work_type_mismatch_fails():
    res = check(CAP, "132kV Overhead Transmission Line", _src(*PAGES))
    assert _by_key(res)["work_type"]["result"] == "FAIL"


def test_unstated_facts_are_unclear_not_fail():
    res = check(CAP, "New project", _src("The contractor shall do the works."))
    k = _by_key(res)
    assert res["status"] == "ELIGIBLE"
    assert k["work_type"]["result"] == k["voltage"]["result"] == k["country"]["result"] == "UNCLEAR"


def test_iso_demanded_but_not_held_fails_and_numbers_compare():
    res = check(CAP, "Riyadh 132kV Substation", _src(*PAGES))
    k = _by_key(res)
    assert k["certifications"]["result"] == "FAIL" and "ISO 45001" in k["certifications"]["detail"]
    assert k["experience"]["result"] == "PASS" and k["turnover"]["result"] == "PASS"
    assert k["country"]["result"] == "PASS" and k["voltage"]["result"] == "PASS"
    low = dict(CAP, years_experience=5, annual_turnover=10e6, certifications=["ISO 9001", "ISO 45001"])
    k2 = _by_key(check(low, "Riyadh 132kV Substation", _src(*PAGES)))
    assert k2["experience"]["result"] == "FAIL" and k2["turnover"]["result"] == "FAIL"
    assert k2["certifications"]["result"] == "PASS"
    other_cur = dict(CAP, turnover_currency="USD")
    assert _by_key(check(other_cur, "Riyadh 132kV Substation", _src(*PAGES)))["turnover"]["result"] == "UNCLEAR"


def test_iso_mentioned_for_equipment_only_is_not_a_demand():
    res = check(CAP, "Riyadh 132kV Substation", _src("Paint system tested per ISO 12944.", "Cables per IEC 60502."))
    assert "certifications" not in _by_key(res)


def _setup_tender(db, tid):
    from app.models import CompanyCapability, EligibilityResult, Tender
    db.add(Tender(id=tid, title="Turaif 380kV Substation", client="SEC"))
    db.merge(CompanyCapability(id="local", work_types=["substation"], max_kv=132))
    db.query(EligibilityResult).filter(EligibilityResult.tender_id == tid).delete()
    db.commit()


def test_gate_blocks_job_and_raises_high_issue_then_override_clears_it():
    from app.database import SessionLocal
    from app.eligibility import run_gate
    from app.issues import sync_issues
    from app.models import EligibilityResult, ProcessingJob, TenderIssue
    tid = f"EL-{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    try:
        _setup_tender(db, tid)
        job = ProcessingJob(id=f"JOB-{uuid.uuid4().hex[:8]}", tender_id=tid, status="PROCESSING")
        db.add(job); db.commit()
        doc_results = {"ITB.pdf": {"status": "COMPLETE", "pages": [{"page": 1, "text": "Two 380 kV bays in Saudi Arabia."}],
                                   "page_count": 1, "total_text_chars": 30}}
        assert run_gate(db, tid, job, doc_results) is True
        assert job.status == "INELIGIBLE" and job.current_stage == "ELIGIBILITY"
        sync_issues(db, tid)
        issue = db.query(TenderIssue).filter(TenderIssue.tender_id == tid, TenderIssue.kind == "ineligible").one()
        assert issue.priority == "HIGH" and "380 kV" in issue.detail
        row = db.query(EligibilityResult).filter(EligibilityResult.tender_id == tid).one()
        row.override_by = "Manager"; db.commit()
        job2 = ProcessingJob(id=f"JOB-{uuid.uuid4().hex[:8]}", tender_id=tid, status="PROCESSING")
        db.add(job2); db.commit()
        assert run_gate(db, tid, job2, doc_results) is False and job2.status == "PROCESSING"
        sync_issues(db, tid)
        assert db.query(TenderIssue).filter(TenderIssue.tender_id == tid, TenderIssue.kind == "ineligible").count() == 0
    finally:
        db.close()


def test_capability_and_override_endpoints(monkeypatch):
    from app.api import routes
    from app.database import SessionLocal
    from app.main import app
    from app.models import EligibilityResult
    monkeypatch.setattr(routes, "process_tender", lambda *a, **k: None)
    c = TestClient(app)
    r = c.put("/api/company-capability", json={"work_types": ["substation", "cable"], "max_kv": "220",
                                               "countries": ["Egypt"], "turnover_currency": "sar"})
    assert r.status_code == 200 and r.json()["max_kv"] == 220 and r.json()["turnover_currency"] == "SAR"
    assert c.put("/api/company-capability", json={"work_types": ["spaceships"]}).status_code == 422
    assert c.put("/api/company-capability", json={"max_kv": -5}).status_code == 422
    assert c.get("/api/company-capability").json()["work_types"] == ["substation", "cable"]
    tid = f"EL-{uuid.uuid4().hex[:6]}"
    c.post("/api/tenders", json={"id": tid, "title": "x"})
    assert c.post(f"/api/tenders/{tid}/eligibility/override", json={}).status_code == 409
    db = SessionLocal()
    db.add(EligibilityResult(tender_id=tid, status="INELIGIBLE", checks=[])); db.commit(); db.close()
    r = c.post(f"/api/tenders/{tid}/eligibility/override", json={"by": "Omar", "reason": "strategic client"})
    assert r.status_code == 200 and r.json()["job_id"]
    e = c.get(f"/api/tenders/{tid}/eligibility").json()
    assert e["override_name"] == "Omar" and e["override_reason"] == "strategic client"
    assert e["override_by"] == "local"  # the signed-in account, not a typed name


def test_staff_experience_is_not_company_experience():
    cap = dict(CAP, years_experience=8)
    k = _by_key(check(cap, "Riyadh 132kV Substation",
                      _src("The Project Manager shall have a minimum of 15 years experience in substations.")))
    assert "experience" not in k or k["experience"]["result"] != "FAIL"
    k2 = _by_key(check(cap, "Riyadh 132kV Substation",
                       _src("The Bidder shall have a minimum of 10 years of experience in similar works.")))
    assert k2["experience"]["result"] == "FAIL"


def test_sub_supplier_iso_demand_does_not_block():
    k = _by_key(check(CAP, "Riyadh 132kV Substation",
                      _src("The Supplier of transformers shall be certified to ISO 14001.")))
    assert "certifications" not in k or k["certifications"]["result"] != "FAIL"


def test_work_type_from_body_only_is_unclear_not_fail():
    cap = dict(CAP, work_types=["renewables"])
    res = check(cap, "TURAIF", _src("Solar PV plant with 33kV cable to the substation."))
    assert _by_key(res)["work_type"]["result"] == "UNCLEAR" and res["status"] == "ELIGIBLE"


def test_override_needs_a_reason_and_records_the_account():
    from app.api import routes
    from app.database import SessionLocal
    from app.main import app
    from app.models import EligibilityResult
    import unittest.mock as um
    with um.patch.object(routes, "process_tender", lambda *a, **k: None):
        c = TestClient(app)
        tid = f"EL-{uuid.uuid4().hex[:6]}"
        c.post("/api/tenders", json={"id": tid, "title": "x"})
        db = SessionLocal()
        db.add(EligibilityResult(tender_id=tid, status="INELIGIBLE", checks=[])); db.commit(); db.close()
        assert c.post(f"/api/tenders/{tid}/eligibility/override", json={"by": "Omar"}).status_code == 422
        assert c.post(f"/api/tenders/{tid}/eligibility/override", json={"by": "Omar", "reason": "ok"}).status_code == 200
        e = c.get(f"/api/tenders/{tid}/eligibility").json()
        assert e["override_by"] == "local" and e["override_name"] == "Omar"
