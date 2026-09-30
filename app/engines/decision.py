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

# Bump whenever decide() can give a different answer for the same rows. Saved
# decisions from an older engine are recomputed once at startup
# (recompute_stale_decisions). 2: a contradicted mandatory non-gate requirement
# is REVIEW (it could be BID), and every mandatory gap counts.
ENGINE_VERSION = 2


def decide(db: Session, tender_id: str, status_results: dict):
    reqs = {r.id: r for r in db.query(Requirement).filter(Requirement.tender_id == tender_id).all()}
    risks = db.query(Risk).filter(Risk.tender_id == tender_id).all()

    hard_fail_count = 0
    mandatory_missing = 0
    mandatory_review = 0
    experience_missing = 0
    mandatory_contradicted = 0
    commercial_risk_high = 0

    supporting_requirements = []
    supporting_evidence = []
    missing_evidence_ids = []
    rules_triggered = []
    top_blockers = []
    contradicted_blockers = []  # listed first: the reason a person must look
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
                # Mandatory but not a hard gate (QUALIFICATION from uploads; EXPERIENCE,
                # FINANCIAL... in the seed). Only bidder-capability gates may give
                # NO_BID, but a mandatory requirement the company's own documents
                # contradict must not pass as BID either: a person looks first.
                if status == "FAIL":
                    mandatory_contradicted += 1
                    contradicted_blockers.append(f"{req.requirement} [CONTRADICTED]")
                elif status in ("MISSING_EVIDENCE", "REVIEW"):
                    # Every category counts: a mandatory gap is a gap (SUBCONTRACTOR,
                    # LEGAL and SUBMISSION used to be skipped by a category list).
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
    elif mandatory_contradicted > 0:
        decision = "REVIEW"
        rules_triggered.append("MANDATORY_REQUIREMENT_CONTRADICTED")
        confidence = "LOW"
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
        top_blockers=(contradicted_blockers + top_blockers)[:6],  # spec says ~6
        top_risks=top_risks[:4],
        is_override=False,
        engine_version=ENGINE_VERSION,
        contradicted_count=mandatory_contradicted,
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


def latest_decision(db: Session, tender_id: str):
    """The current decision, exactly as every screen reads it."""
    return (db.query(Decision).filter(Decision.tender_id == tender_id)
            .order_by(Decision.timestamp.desc()).first())


def contradiction_waived(dec) -> bool:
    """A person reviewed the contradiction and decided to bid anyway. A REVIEW
    or NO_BID override keeps it standing."""
    return bool(dec is not None and dec.is_override and dec.decision == "BID")


def recompute_stale_decisions(db: Session) -> tuple:
    """Recompute, once, every tender whose current decision was computed by an
    older engine, so a tender the old rules called BID is not still shown as BID.
    A human override on top stays the current decision. One tender that cannot
    be evaluated does not stop the others. Returns (recomputed ids, failed ids)."""
    redone, failed = [], []
    for (tid,) in db.query(Decision.tender_id).distinct().all():
        dec = latest_decision(db, tid)
        if dec is None or dec.is_override or (dec.engine_version or 0) >= ENGINE_VERSION:
            continue
        try:
            get_or_create_decision(db, tid)
            redone.append(tid)
        except Exception:
            db.rollback()
            failed.append(tid)
    return redone, failed
