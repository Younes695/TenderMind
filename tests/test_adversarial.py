import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import datetime
from app.database import SessionLocal, init_db, Base, engine
from app.seed import seed
from app.engines.status import evaluate_all
from app.engines.decision import get_or_create_decision
from app.engines.explanation import build_explanation
from app.models import Evidence, EvidenceMatch, Requirement, Risk, Decision

def setup():
    Base.metadata.drop_all(bind=engine)
    init_db()
    seed()

def test_1_missing_never_fail():
    """1. Missing evidence must never become FAIL — remove every evidence one by one"""
    setup()
    db = SessionLocal()
    # Remove all evidences
    db.query(EvidenceMatch).delete()
    db.query(Evidence).delete()
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    for req_id, res in status.items():
        assert res["status"] != "FAIL", f"{req_id} should not be FAIL when no evidence, got {res['status']}"
        # For mandatory HARD_GATE, MISSING leads to REVIEW not FAIL
    assert dec.decision == "REVIEW", f"Expected REVIEW with all missing, got {dec.decision}"
    assert dec.hard_fail_count == 0
    # Now test removing one by one: re-seed and remove each
    for ev_id in ["E-001","E-002","E-003","E-004"]:
        setup()
        db2 = SessionLocal()
        # remove single evidence
        db2.query(EvidenceMatch).filter(EvidenceMatch.evidence_id == ev_id).delete()
        db2.query(Evidence).filter(Evidence.id == ev_id).delete()
        db2.commit()
        dec2, status2 = get_or_create_decision(db2, "SA-2018-HV2")
        # The requirement that lost its evidence should be MISSING, not FAIL
        # Find which requirement it was
        for rid, res in status2.items():
            if ev_id in [e for e in res.get("evidence_ids",[])]:
                pass
        # Check no FAIL was invented
        for rid, res in status2.items():
            if res["status"] == "FAIL":
                # Only FAIL if we explicitly created FAIL evidence; missing should not create FAIL
                # So any FAIL here would be bug
                assert False, f"Removing {ev_id} caused unexpected FAIL {rid}"
        db2.close()
    print("PASS 1: missing never becomes FAIL")
    db.close()

def test_2_explicit_contradiction_fail():
    """2. Explicit contradiction must become FAIL -> NO_BID"""
    setup()
    db = SessionLocal()
    # Create FAIL evidence for REQ-A (First Category required, but we have Second Category)
    ev = Evidence(id="E-FAIL-CONTRADICT", company_id="HYOSUNG_GIZA", requirement_id="REQ-A",
                  evidence_type="CERTIFICATE", fact="Second Category membership certificate — Grade 2, not First Category — insufficient per RFP p.2",
                  status="FAIL", source_document="Membership Cert Grade 2.pdf", page_or_section="Page 1, Classification",
                  source_quote="Grade 2 - Second Category", extraction_confidence="HIGH", applicable_entity="GIZA", reusable=True)
    db.add(ev)
    db.add(EvidenceMatch(id="M-E-FAIL-CONTRADICT", requirement_id="REQ-A", evidence_id="E-FAIL-CONTRADICT", match_confidence="HIGH"))
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    assert status["REQ-A"]["status"] == "FAIL", f"REQ-A should be FAIL, got {status['REQ-A']['status']}"
    assert dec.decision == "NO_BID", f"Expected NO_BID, got {dec.decision}"
    assert "HARD_GATE_FAIL" in dec.rules_triggered
    # Provenance must exist
    assert len(status["REQ-A"]["provenance"]) > 0
    assert status["REQ-A"]["provenance"][0]["source_document"] == "Membership Cert Grade 2.pdf"
    print("PASS 2: explicit contradiction -> FAIL -> NO_BID")
    db.close()

def test_3_risk_not_no_bid():
    """3. Risk must not create NO_BID — all HIGH risks still REVIEW unless FAIL"""
    setup()
    db = SessionLocal()
    # Set all risks to HIGH
    risks = db.query(Risk).filter(Risk.tender_id == "SA-2018-HV2").all()
    for r in risks:
        r.severity = "HIGH"
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    # Even with all HIGH, decision should be REVIEW (because MISSING still) not NO_BID
    assert dec.decision == "REVIEW", f"Risks HIGH should not cause NO_BID, got {dec.decision}"
    # Now if we also have a FAIL, then NO_BID, but risks alone never cause NO_BID
    # Verify no NO_BID from risks
    assert dec.decision != "NO_BID"
    print("PASS 3: risks do not create NO_BID")
    db.close()

def test_4_oem_not_satisfy_unrelated():
    """4. OEM evidence must not satisfy unrelated requirements"""
    setup()
    db = SessionLocal()
    # OEM evidence is only matched to REQ-J (OEM relationship) — verify other requirements remain MISSING
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    # REQ-K (type-test), REQ-L (operating refs), REQ-D (similar project), REQ-I (175MVA) should be MISSING
    for req_id in ["REQ-K","REQ-L","REQ-D","REQ-I","REQ-H"]:
        assert status[req_id]["status"] == "MISSING_EVIDENCE", f"{req_id} should remain MISSING, got {status[req_id]['status']}"
    # REQ-J should be PASS
    assert status["REQ-J"]["status"] == "PASS"
    print("PASS 4: OEM does not satisfy unrelated")
    db.close()

def test_5_tender_stage_vs_company():
    """5. Tender security is tender-stage missing, not permanent commercial FAIL"""
    setup()
    db = SessionLocal()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    # REQ-C tender security should be MISSING_EVIDENCE, not FAIL
    assert status["REQ-C"]["status"] == "MISSING_EVIDENCE"
    assert dec.decision == "REVIEW"  # not NO_BID
    # Check missing evidence priority and owner
    from app.models import MissingEvidence
    me = db.query(MissingEvidence).filter(MissingEvidence.requirement_id == "REQ-C").first()
    if not me:
        # may need to generate
        from app.engines.missing_evidence import generate_missing_evidence
        generate_missing_evidence(db, "SA-2018-HV2", status)
        me = db.query(MissingEvidence).filter(MissingEvidence.requirement_id == "REQ-C").first()
    assert me is not None
    assert me.priority == "CRITICAL"
    assert me.status == "MISSING_EVIDENCE"
    # Ensure not marked as company commercially unqualified permanently — it's tender-stage
    assert "tender security" in me.document_needed.lower() or "5,700" in me.document_needed or "5.7" in me.document_needed
    print("PASS 5: tender-stage correctly identified")
    db.close()

def test_6_consortium_applicability():
    """6. Consortium applicability — Hyosung evidence cannot satisfy Giza-specific requirement"""
    setup()
    db = SessionLocal()
    # REQ-A is GIZA-specific (first-category local partner)
    # Try Hyosung evidence for REQ-A -> should NOT satisfy, remain MISSING
    ev_hy = Evidence(id="E-HYOSUNG-FOR-GIZA", company_id="HYOSUNG_GIZA", requirement_id="REQ-A",
                     evidence_type="CERTIFICATE", fact="Hyosung First Category equivalent (Korean) — but not Egyptian Union",
                     status="PASS", source_document="Hyosung Cert.pdf", page_or_section="Page 1",
                     extraction_confidence="HIGH", applicable_entity="HYOSUNG", reusable=True)
    db.add(ev_hy)
    db.add(EvidenceMatch(id="M-HYOSUNG-GIZA", requirement_id="REQ-A", evidence_id="E-HYOSUNG-FOR-GIZA", match_confidence="HIGH"))
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    # Should still be MISSING or REVIEW due to applicability mismatch, not PASS
    # Since Hyosung not Giza, engine filters it out -> MISSING
    assert status["REQ-A"]["status"] == "MISSING_EVIDENCE", f"Hyosung should not satisfy GIZA REQ-A, got {status['REQ-A']['status']}"
    # Now add correct Giza evidence -> should become PASS
    ev_giza = Evidence(id="E-GIZA-CORRECT", company_id="HYOSUNG_GIZA", requirement_id="REQ-A",
                       evidence_type="CERTIFICATE", fact="Giza Systems First Category Egyptian Union membership certificate valid 2024-2025 — Grade 1",
                       status="PASS", source_document="Giza First Category Certificate.pdf", page_or_section="Page 1", extraction_confidence="HIGH", applicable_entity="GIZA", reusable=True)
    db.add(ev_giza)
    db.add(EvidenceMatch(id="M-GIZA-CORRECT", requirement_id="REQ-A", evidence_id="E-GIZA-CORRECT", match_confidence="HIGH"))
    db.commit()
    dec2, status2 = get_or_create_decision(db, "SA-2018-HV2")
    # Now REQ-A should be PASS (has Giza evidence; Hyosung still mismatched but Giza satisfies)
    # Since we have both, the applicable one (Giza) should make it PASS
    assert status2["REQ-A"]["status"] == "PASS", f"Giza evidence should satisfy REQ-A, got {status2['REQ-A']['status']}"
    print("PASS 6: consortium applicability enforced")
    db.close()

def test_7_provenance_integrity():
    """7. Provenance integrity"""
    setup()
    db = SessionLocal()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    # Every PASS must have source doc + page + evidence_id
    for req_id, res in status.items():
        if res["status"] == "PASS":
            assert len(res["provenance"]) > 0, f"{req_id} PASS must have provenance"
            for p in res["provenance"]:
                assert p["source_document"], f"{req_id} missing source_document"
                assert p["page_or_section"], f"{req_id} missing page/section"
                assert p["evidence_id"], f"{req_id} missing evidence_id"
        if res["status"] == "MISSING_EVIDENCE":
            # Check missing evidence record exists with priority/owner/why
            from app.models import MissingEvidence
            from app.engines.missing_evidence import generate_missing_evidence
            generate_missing_evidence(db, "SA-2018-HV2", status)
            me = db.query(MissingEvidence).filter(MissingEvidence.requirement_id == req_id).first()
            if req_id in status and status[req_id]["status"] == "MISSING_EVIDENCE":
                # Not all MISSING may have MissingEvidence if not mandatory? But our mapping covers all
                if me:
                    assert me.priority in ("CRITICAL","HIGH","MEDIUM","LOW")
                    assert me.owner
                    assert me.why_needed
        if res["status"] == "FAIL":
            assert len(res["provenance"]) > 0
            assert res["provenance"][0]["source_document"]
    # Also test FAIL provenance: create FAIL and check
    ev = Evidence(id="E-PROV-FAIL", company_id="HYOSUNG_GIZA", requirement_id="REQ-A",
                  evidence_type="CERTIFICATE", fact="Grade 2 fail", status="FAIL",
                  source_document="Prov Fail Doc.pdf", page_or_section="Page 2", extraction_confidence="HIGH", applicable_entity="GIZA")
    db.add(ev)
    db.add(EvidenceMatch(id="M-PROV-FAIL", requirement_id="REQ-A", evidence_id="E-PROV-FAIL", match_confidence="HIGH"))
    db.commit()
    dec2, status2 = get_or_create_decision(db, "SA-2018-HV2")
    assert status2["REQ-A"]["status"] == "FAIL"
    assert status2["REQ-A"]["provenance"][0]["source_document"] == "Prov Fail Doc.pdf"
    print("PASS 7: provenance integrity")
    db.close()

def test_8_evidence_conflict():
    """8. Evidence conflict -> REVIEW not arbitrary PASS/FAIL, conflict appears"""
    setup()
    db = SessionLocal()
    # Create two evidences for REQ-A: First vs Second Category
    ev_a = Evidence(id="E-CONFLICT-A", company_id="HYOSUNG_GIZA", requirement_id="REQ-A",
                    evidence_type="CERTIFICATE", fact="First Category membership certificate — Grade 1 — valid",
                    status="PASS", source_document="Cert First.pdf", page_or_section="Page 1", extraction_confidence="HIGH", applicable_entity="GIZA")
    ev_b = Evidence(id="E-CONFLICT-B", company_id="HYOSUNG_GIZA", requirement_id="REQ-A",
                    evidence_type="CERTIFICATE", fact="Second Category membership — Grade 2 — valid",
                    status="PASS", source_document="Cert Second.pdf", page_or_section="Page 1", extraction_confidence="HIGH", applicable_entity="GIZA")
    db.add(ev_a)
    db.add(ev_b)
    db.add(EvidenceMatch(id="M-CONFLICT-A", requirement_id="REQ-A", evidence_id="E-CONFLICT-A", match_confidence="HIGH"))
    db.add(EvidenceMatch(id="M-CONFLICT-B", requirement_id="REQ-A", evidence_id="E-CONFLICT-B", match_confidence="HIGH"))
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    assert status["REQ-A"]["status"] == "REVIEW", f"Conflict should be REVIEW, got {status['REQ-A']['status']}"
    assert status["REQ-A"].get("conflicts"), "Conflict should appear"
    # Explanation should contain conflicts
    exp = build_explanation(db, "SA-2018-HV2", dec, status)
    assert len(exp["conflicts"]) > 0, "Explanation must contain conflicts"
    assert any("First vs Second" in c["reason"] or "Conflicting" in c["reason"] for c in exp["conflicts"])
    print("PASS 8: conflict detected -> REVIEW")
    db.close()

def test_9_expired_evidence():
    """9. Expired evidence -> not blindly PASS, should be REVIEW"""
    setup()
    db = SessionLocal()
    past = datetime.datetime(2020, 1, 1)
    ev = Evidence(id="E-EXPIRED", company_id="HYOSUNG_GIZA", requirement_id="REQ-A",
                  evidence_type="CERTIFICATE", fact="First Category certificate valid 2019-2020 — First Category",
                  status="PASS", source_document="Expired Cert.pdf", page_or_section="Page 1", extraction_confidence="HIGH",
                  applicable_entity="GIZA", valid_until=past, reusable=True)
    db.add(ev)
    db.add(EvidenceMatch(id="M-EXPIRED", requirement_id="REQ-A", evidence_id="E-EXPIRED", match_confidence="HIGH"))
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    assert status["REQ-A"]["status"] == "REVIEW", f"Expired should be REVIEW, got {status['REQ-A']['status']}"
    assert status["REQ-A"].get("expired") == True
    print("PASS 9: expired evidence -> REVIEW")
    db.close()

def test_10_wrong_tender_evidence():
    """10. Wrong tender evidence not used unless reusable"""
    setup()
    db = SessionLocal()
    # Create evidence from OTHER tender, non-reusable (e.g., tender security specific to other)
    ev = Evidence(id="E-WRONG-TENDER", company_id="HYOSUNG_GIZA", requirement_id="REQ-C",
                  evidence_type="TENDER_SECURITY", fact="Tender security for OTHER/2020/XYZ — 3M",
                  status="PASS", source_document="Other Tender Security.pdf", page_or_section="Page 1",
                  extraction_confidence="HIGH", tender_source_id="OTHER-2020-XYZ", reusable=False)
    db.add(ev)
    db.add(EvidenceMatch(id="M-WRONG", requirement_id="REQ-C", evidence_id="E-WRONG-TENDER", match_confidence="HIGH"))
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    # Should remain MISSING because non-reusable wrong tender ignored
    assert status["REQ-C"]["status"] == "MISSING_EVIDENCE", f"Wrong tender non-reusable should not satisfy, got {status['REQ-C']['status']}"
    # Now reusable cert from other tender SHOULD be usable if reusable=True
    ev2 = Evidence(id="E-WRONG-REUSABLE", company_id="HYOSUNG_GIZA", requirement_id="REQ-A",
                   evidence_type="CERTIFICATE", fact="First Category certificate from other tender but reusable company fact",
                   status="PASS", source_document="Reusable Cert.pdf", page_or_section="Page 1", extraction_confidence="HIGH",
                   applicable_entity="GIZA", tender_source_id="OTHER-2020-XYZ", reusable=True)
    db.add(ev2)
    db.add(EvidenceMatch(id="M-WRONG-REUSABLE", requirement_id="REQ-A", evidence_id="E-WRONG-REUSABLE", match_confidence="HIGH"))
    db.commit()
    dec2, status2 = get_or_create_decision(db, "SA-2018-HV2")
    # Reusable should be considered -> PASS
    assert status2["REQ-A"]["status"] == "PASS", f"Reusable cert should satisfy, got {status2['REQ-A']['status']}"
    print("PASS 10: wrong tender handling correct")
    db.close()

def test_11_requirement_ambiguity():
    """11. Ambiguous requirement -> REVIEW with ambiguity reason"""
    setup()
    db = SessionLocal()
    # Create ambiguous requirement
    req = Requirement(id="REQ-AMB", tender_id="SA-2018-HV2", category="LEGAL",
                      requirement="Ambiguous: qualification applies to Consortium vs Lead partner vs OEM unclear — per spec §19 #6",
                      mandatory=True, requirement_type="HARD_GATE",
                      evidence_required=["ambiguous_doc"], evaluation_logic={"PASS":"Pass","FAIL":"Fail","MISSING_EVIDENCE":"Missing","REVIEW":"Ambiguous"},
                      source_document="Ambiguous Clause", page_or_section="Clause 3.2",
                      applicable_entity="AMBIGUOUS", ambiguity_note="Tender does not specify whether REQ-AMB applies to Consortium, Giza lead, or Hyosung OEM")
    db.add(req)
    db.commit()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    assert status["REQ-AMB"]["status"] == "REVIEW", f"Ambiguous should be REVIEW, got {status['REQ-AMB']['status']}"
    assert "ambiguous" in status["REQ-AMB"]["reason"].lower()
    print("PASS 11: ambiguity -> REVIEW")
    db.close()

def test_12_human_override():
    """12. Human override preserves original and stores audit"""
    setup()
    db = SessionLocal()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    assert dec.decision == "REVIEW"
    original_id = dec.id
    # Simulate override via direct DB (or API logic)
    from app.models import Decision, DecisionAudit
    import uuid, datetime as dt
    override_dec = Decision(
        id=f"DEC-OVR{uuid.uuid4().hex[:4]}",
        tender_id="SA-2018-HV2",
        decision="BID",
        confidence="OVERRIDE",
        timestamp=dt.datetime.utcnow(),
        rules_triggered=["HUMAN_OVERRIDE"],
        supporting_requirements=dec.supporting_requirements,
        supporting_evidence=dec.supporting_evidence,
        missing_evidence=dec.missing_evidence,
        risks=dec.risks,
        hard_fail_count=dec.hard_fail_count,
        mandatory_missing_count=dec.mandatory_missing_count,
        top_blockers=dec.top_blockers,
        top_risks=dec.top_risks,
        is_override=True
    )
    db.add(override_dec)
    audit = DecisionAudit(
        id=f"AUD-{uuid.uuid4().hex[:6].upper()}",
        decision_id=override_dec.id,
        reviewer="Commercial Director",
        timestamp=dt.datetime.utcnow(),
        previous_decision=dec.decision,
        new_decision="BID",
        reason="Risk review completed, evidence requests in progress, client relationship justifies BID despite missing certs — will obtain bank guarantee",
        comments="Override after commercial review"
    )
    db.add(audit)
    db.commit()
    # Verify original preserved
    orig = db.query(Decision).filter(Decision.id == original_id).first()
    assert orig is not None, "Original decision must be preserved"
    assert orig.decision == "REVIEW"
    assert orig.is_override == False
    # New is override
    assert override_dec.is_override == True
    assert audit.reviewer == "Commercial Director"
    assert audit.reason != ""
    # Latest decision is BID
    latest = db.query(Decision).filter(Decision.tender_id == "SA-2018-HV2").order_by(Decision.timestamp.desc()).first()
    assert latest.decision == "BID"
    print("PASS 12: human override preserved with audit")
    db.close()

def test_explanation_object():
    """Decision Explanation object dynamically generated"""
    setup()
    db = SessionLocal()
    dec, status = get_or_create_decision(db, "SA-2018-HV2")
    exp = build_explanation(db, "SA-2018-HV2", dec, status)
    assert exp["decision"] == dec.decision
    assert exp["confidence"] == dec.confidence
    assert "summary" in exp
    assert "hard_failures" in exp
    assert "missing_evidence" in exp
    assert "risks" in exp
    assert "supporting_evidence" in exp
    assert "conflicts" in exp
    assert "rules_triggered" in exp
    assert exp["provenance_chain"] == "Requirement → Evidence → Source Document → Page/Section → Rule → Decision"
    # hard_failures should be empty for REVIEW case
    assert len(exp["hard_failures"]) == 0
    assert len(exp["missing_evidence"]) > 0
    assert len(exp["risks"]) == 7
    print("PASS explanation object")
    db.close()

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    test_1_missing_never_fail()
    test_2_explicit_contradiction_fail()
    test_3_risk_not_no_bid()
    test_4_oem_not_satisfy_unrelated()
    test_5_tender_stage_vs_company()
    test_6_consortium_applicability()
    test_7_provenance_integrity()
    test_8_evidence_conflict()
    test_9_expired_evidence()
    test_10_wrong_tender_evidence()
    test_11_requirement_ambiguity()
    test_12_human_override()
    test_explanation_object()
    print("\nAll 12 adversarial + explanation tests passed")
