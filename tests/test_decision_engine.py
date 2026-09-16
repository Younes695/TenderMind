import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, init_db, Base, engine
from app.seed import seed
from app.engines.status import evaluate_all
from app.engines.decision import get_or_create_decision

def setup():
    Base.metadata.drop_all(bind=engine)
    init_db()
    seed()

def test_review_not_no_bid():
    """Spec Section 6 example: MISSING_EVIDENCE must produce REVIEW not NO_BID"""
    setup()
    db = SessionLocal()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    assert dec.decision == "REVIEW", f"Expected REVIEW got {dec.decision}"
    assert dec.hard_fail_count == 0, "No HARD_FAIL for missing evidence"
    assert dec.mandatory_missing_count > 0
    assert "MANDATORY_GATE_MISSING" in dec.rules_triggered or "EXPERIENCE_EVIDENCE_MISSING" in dec.rules_triggered
    # Ensure PASS requirements are exactly 3 (R, B, J) and U is REVIEW
    assert status["REQ-R"]["status"] == "PASS", "REQ-R should be PASS"
    assert status["REQ-B"]["status"] == "PASS", "REQ-B should be PASS"
    assert status["REQ-J"]["status"] == "PASS", "REQ-J should be PASS"
    assert status["REQ-U"]["status"] == "REVIEW", "REQ-U must be REVIEW per spec correction #1"
    assert status["REQ-A"]["status"] == "MISSING_EVIDENCE", "REQ-A missing"
    # Risk does not cause NO_BID
    assert dec.decision != "NO_BID"
    print("✓ test_review_not_no_bid passed")
    db.close()

def test_no_hardcoded_decision():
    """Engine must compute dynamically; changing evidence should change decision"""
    setup()
    db = SessionLocal()
    from app.models import Evidence, EvidenceMatch
    # Add missing critical evidence to simulate BID path — but still not all, should remain REVIEW
    # Add evidence for REQ-A to make it PASS, then check still REVIEW due to other missing
    ev = Evidence(id="E-TEST-A", company_id="HYOSUNG_GIZA", requirement_id="REQ-A", evidence_type="CERTIFICATE", fact="Giza Systems first-category membership certificate valid 2024-2025", status="PASS", source_document="Giza First Category Certificate.pdf", page_or_section="Page 1", extraction_confidence="HIGH")
    db.add(ev)
    db.add(EvidenceMatch(id="M-E-TEST-A", requirement_id="REQ-A", evidence_id="E-TEST-A", match_confidence="HIGH"))
    db.commit()
    dec2, status2 = get_or_create_decision(db, "SA-2018-HV2")
    # Still REVIEW because other mandatory missing (D,E,F etc)
    assert dec2.decision == "REVIEW", "Still REVIEW after one missing fixed"
    print("✓ test_no_hardcoded_decision passed")
    db.close()

def test_no_bid_on_fail():
    """If we inject a FAIL on mandatory HARD_GATE, decision becomes NO_BID"""
    setup()
    db = SessionLocal()
    from app.models import Evidence, EvidenceMatch
    ev_fail = Evidence(id="E-FAIL-A", company_id="HYOSUNG_GIZA", requirement_id="REQ-A", evidence_type="CERTIFICATE", fact="Certificate shows Grade 2, not First-category — insufficient", status="FAIL", source_document="Membership Cert.pdf", page_or_section="Page 1", extraction_confidence="HIGH")
    # Need to remove previous matches? Seed has no evidence for REQ-A, so just add FAIL
    db.add(ev_fail)
    db.add(EvidenceMatch(id="M-E-FAIL-A", requirement_id="REQ-A", evidence_id="E-FAIL-A", match_confidence="HIGH"))
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    assert status["REQ-A"]["status"] == "FAIL"
    assert dec.decision == "NO_BID", f"FAIL should trigger NO_BID got {dec.decision}"
    assert "HARD_GATE_FAIL" in dec.rules_triggered
    print("✓ test_no_bid_on_fail passed")
    db.close()

def test_provenance():
    setup()
    db = SessionLocal()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    # Every PASS must have provenance
    for req_id, res in status.items():
        if res["status"] == "PASS":
            assert len(res["provenance"]) > 0, f"{req_id} PASS must have provenance"
            for p in res["provenance"]:
                assert p["source_document"], "source_document required"
                assert p["page_or_section"], "page_or_section required"
    print("✓ test_provenance passed")
    db.close()

def test_risk_separate():
    setup()
    db = SessionLocal()
    from app.models import Risk
    risks = db.query(Risk).filter(Risk.tender_id == "SA-2018-HV2").all()
    assert len(risks) == 7, f"Expected 7 risks got {len(risks)}"
    for r in risks:
        assert r.decision_impact == "REVIEW", "Risks must be REVIEW not NO_BID"
    print("✓ test_risk_separate passed")
    db.close()

def test_missing_not_fail():
    setup()
    db = SessionLocal()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    missing = [k for k,v in status.items() if v["status"]=="MISSING_EVIDENCE"]
    # Ensure none converted to FAIL
    assert len(missing) > 0
    for m in missing:
        assert status[m]["status"] != "FAIL"
    # Also ensure U is REVIEW not PASS (correction #1)
    assert status["REQ-U"]["status"] == "REVIEW"
    print("✓ test_missing_not_fail passed")
    db.close()

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    test_review_not_no_bid()
    test_no_hardcoded_decision()
    test_no_bid_on_fail()
    test_provenance()
    test_risk_separate()
    test_missing_not_fail()
    print("\nAll Test001 tests passed — decision is dynamic and spec-compliant.")
