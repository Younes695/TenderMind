"""
Decision Engine per spec Section 6 hierarchy.
NEVER convert MISSING_EVIDENCE into FAIL.
RISK does not auto NO_BID.
"""
from sqlalchemy.orm import Session
from app.models import Requirement, Risk, Decision
from app.engines.status import evaluate_all
from datetime import datetime
import uuid

def decide(db: Session, tender_id: str, status_results: dict):
    reqs = {r.id: r for r in db.query(Requirement).filter(Requirement.tender_id == tender_id).all()}
    risks = db.query(Risk).filter(Risk.tender_id == tender_id).all()

    hard_fail_count = 0
    mandatory_missing = 0
    mandatory_review = 0
    experience_missing = 0
    commercial_risk_high = 0

    supporting_requirements = []
    supporting_evidence = []
    missing_evidence_ids = []
    rules_triggered = []
    top_blockers = []
    top_risks = []

    for req_id, res in status_results.items():
        req = reqs.get(req_id)
        if not req:
            continue
        status = res["status"]
        if req.mandatory:
            if req.requirement_type == "HARD_GATE":
                if status == "FAIL":
                    hard_fail_count += 1
                elif status == "MISSING_EVIDENCE":
                    mandatory_missing += 1
                    missing_evidence_ids.append(f"ME-{req_id.replace('REQ-','')}")
                    top_blockers.append(req.requirement)
                elif status == "REVIEW":
                    mandatory_review += 1
                    missing_evidence_ids.append(f"ME-{req_id.replace('REQ-','')}")
                    top_blockers.append(f"{req.requirement} [REVIEW]")
            else:
                # mandatory but not HARD_GATE (EXPERIENCE, FINANCIAL etc)
                if status in ("MISSING_EVIDENCE", "REVIEW"):
                    # Count as blocker but not hard fail
                    if req.category in ("EXPERIENCE", "TECHNICAL", "EQUIPMENT", "PERSONNEL", "FINANCIAL", "HSE", "QA_QC", "SCHEDULE", "COMMERCIAL"):
                        experience_missing += 1
                        missing_evidence_ids.append(f"ME-{req_id.replace('REQ-','')}")
                        # avoid duplicate if already
                        if req.requirement not in top_blockers and f"{req.requirement} [REVIEW]" not in top_blockers:
                            top_blockers.append(req.requirement + (" [REVIEW]" if status=="REVIEW" else ""))
        # supporting
        if status == "PASS":
            supporting_requirements.append(req_id)
            supporting_evidence.extend(res.get("evidence_ids", []))
        elif status == "FAIL":
            # still supporting for audit
            supporting_requirements.append(req_id)

    for r in risks:
        if r.severity == "HIGH":
            commercial_risk_high += 1
            top_risks.append(r.description)
        elif r.severity == "MEDIUM":
            top_risks.append(r.description)

    # Decision hierarchy (spec 6)
    decision = None
    confidence = "HIGH"
    if hard_fail_count > 0:
        decision = "NO_BID"
        rules_triggered.append("HARD_GATE_FAIL")
        confidence = "HIGH"
    elif mandatory_missing > 0:
        decision = "REVIEW"
        rules_triggered.append("MANDATORY_GATE_MISSING")
        confidence = "LOW"
    elif mandatory_review > 0:
        decision = "REVIEW"
        rules_triggered.append("MANDATORY_GATE_REVIEW")
        confidence = "LOW"
    elif experience_missing > 0:
        decision = "REVIEW"
        rules_triggered.append("EXPERIENCE_EVIDENCE_MISSING")
        confidence = "LOW"
    elif commercial_risk_high > 0:
        decision = "REVIEW"
        rules_triggered.append("COMMERCIAL_RISK_REVIEW")
        confidence = "MEDIUM"
    else:
        decision = "BID"
        rules_triggered.append("ALL_MANDATORY_PASS")
        confidence = "HIGH"

    # Ensure NEVER NO_BID from missing alone: already handled — only FAIL triggers NO_BID

    # Build decision object but not yet persisted; caller will persist
    decision_id = f"DEC-{uuid.uuid4().hex[:6].upper()}"
    dec = Decision(
        id=decision_id,
        tender_id=tender_id,
        decision=decision,
        confidence=confidence,
        timestamp=datetime.utcnow(),
        rules_triggered=rules_triggered,
        supporting_requirements=supporting_requirements,
        supporting_evidence=list(set(supporting_evidence)),
        missing_evidence=missing_evidence_ids,
        risks=[r.id for r in risks],
        hard_fail_count=hard_fail_count,
        mandatory_missing_count=mandatory_missing + mandatory_review,
        top_blockers=top_blockers[:6],  # spec says ~6
        top_risks=top_risks[:4],
        is_override=False
    )
    return dec

def get_or_create_decision(db: Session, tender_id: str):
    from app.engines.missing_evidence import generate_missing_evidence
    status_results = evaluate_all(db, tender_id)
    generate_missing_evidence(db, tender_id, status_results)
    dec = decide(db, tender_id, status_results)
    db.add(dec)
    db.commit()
    db.refresh(dec)
    return dec, status_results
