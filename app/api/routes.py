from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Tender, Requirement, Evidence, EvidenceMatch, Risk, MissingEvidence, Decision, DecisionAudit, Company, TenderDocument
from app.engines.status import evaluate_all
from app.engines.decision import get_or_create_decision
from app.engines.explanation import build_explanation
from datetime import datetime
import uuid

router = APIRouter()

@router.get("/tenders")
def list_tenders(db: Session = Depends(get_db)):
    return db.query(Tender).all()

@router.get("/tenders/{tender_id}")
def get_tender(tender_id: str, db: Session = Depends(get_db)):
    t = db.query(Tender).filter(Tender.id == tender_id).first()
    if not t:
        raise HTTPException(404, "Tender not found")
    return t

@router.get("/tenders/{tender_id}/requirements")
def get_requirements(tender_id: str, db: Session = Depends(get_db)):
    reqs = db.query(Requirement).filter(Requirement.tender_id == tender_id).all()
    status_results = evaluate_all(db, tender_id)
    out = []
    for r in reqs:
        sr = status_results.get(r.id, {})
        out.append({
            "requirement_id": r.id,
            "category": r.category,
            "requirement": r.requirement,
            "mandatory": r.mandatory,
            "requirement_type": r.requirement_type,
            "evidence_required": r.evidence_required,
            "source_document": r.source_document,
            "page_or_section": r.page_or_section,
            "status": sr.get("status"),
            "evidence_ids": sr.get("evidence_ids", []),
            "reason": sr.get("reason"),
            "provenance": sr.get("provenance", [])
        })
    return out

@router.get("/tenders/{tender_id}/evidence")
def get_evidence(tender_id: str, db: Session = Depends(get_db)):
    # All evidence for company linked to tender (for Test001, all)
    evidences = db.query(Evidence).all()
    return evidences

@router.get("/tenders/{tender_id}/risks")
def get_risks(tender_id: str, db: Session = Depends(get_db)):
    risks = db.query(Risk).filter(Risk.tender_id == tender_id).all()
    return risks

@router.get("/tenders/{tender_id}/missing-evidence")
def get_missing(tender_id: str, db: Session = Depends(get_db)):
    # ensure generated
    status_results = evaluate_all(db, tender_id)
    from app.engines.missing_evidence import generate_missing_evidence
    generate_missing_evidence(db, tender_id, status_results)
    return db.query(MissingEvidence).all()

@router.get("/tenders/{tender_id}/decision")
def get_decision(tender_id: str, db: Session = Depends(get_db)):
    # return latest decision, or create one
    dec = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not dec:
        dec, _ = get_or_create_decision(db, tender_id)
    status_results = evaluate_all(db, tender_id)
    return {
        "decision": dec.decision,
        "confidence": dec.confidence,
        "decision_id": dec.id,
        "tender_id": dec.tender_id,
        "timestamp": dec.timestamp,
        "rules_triggered": dec.rules_triggered,
        "hard_fail_count": dec.hard_fail_count,
        "mandatory_missing_evidence_count": dec.mandatory_missing_count,
        "top_blockers": dec.top_blockers,
        "top_risks": dec.top_risks,
        "supporting_requirements": dec.supporting_requirements,
        "supporting_evidence": dec.supporting_evidence,
        "missing_evidence": dec.missing_evidence,
        "risks": dec.risks,
        "is_override": dec.is_override,
        "status_results": status_results
    }

@router.post("/tenders/{tender_id}/decision/recompute")
def recompute(tender_id: str, db: Session = Depends(get_db)):
    dec, _ = get_or_create_decision(db, tender_id)
    return {"decision": dec.decision, "confidence": dec.confidence, "decision_id": dec.id, "rules_triggered": dec.rules_triggered}

@router.post("/tenders/{tender_id}/decision/override")
def override(tender_id: str, payload: dict, db: Session = Depends(get_db)):
    # payload: reviewer, new_decision, reason, comments
    reviewer = payload.get("reviewer", "unknown")
    new_decision = payload.get("new_decision")
    reason = payload.get("reason", "")
    comments = payload.get("comments", "")
    if new_decision not in ("BID","REVIEW","NO_BID"):
        raise HTTPException(400, "new_decision must be BID/REVIEW/NO_BID")
    last = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not last:
        raise HTTPException(404, "No decision to override")
    # create new decision as override
    override_dec = Decision(
        id=f"DEC-{uuid.uuid4().hex[:6].upper()}",
        tender_id=tender_id,
        decision=new_decision,
        confidence="OVERRIDE",
        timestamp=datetime.utcnow(),
        rules_triggered=["HUMAN_OVERRIDE"],
        supporting_requirements=last.supporting_requirements,
        supporting_evidence=last.supporting_evidence,
        missing_evidence=last.missing_evidence,
        risks=last.risks,
        hard_fail_count=last.hard_fail_count,
        mandatory_missing_count=last.mandatory_missing_count,
        top_blockers=last.top_blockers,
        top_risks=last.top_risks,
        is_override=True
    )
    db.add(override_dec)
    audit = DecisionAudit(
        id=f"AUD-{uuid.uuid4().hex[:6].upper()}",
        decision_id=override_dec.id,
        reviewer=reviewer,
        timestamp=datetime.utcnow(),
        previous_decision=last.decision,
        new_decision=new_decision,
        reason=reason,
        comments=comments
    )
    db.add(audit)
    db.commit()
    return {"override_decision": new_decision, "audit_id": audit.id, "previous": last.decision}

@router.get("/tenders/{tender_id}/audit")
def get_audit(tender_id: str, db: Session = Depends(get_db)):
    decisions = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.asc()).all()
    audits = db.query(DecisionAudit).all()
    # filter audits where decision tender matches
    # need join: audits where decision_id in decisions ids
    dec_ids = [d.id for d in decisions]
    filtered_audits = [a for a in audits if a.decision_id in dec_ids]
    return {"decisions": decisions, "audits": filtered_audits}

@router.get("/tenders/{tender_id}/export")
def export_json(tender_id: str, db: Session = Depends(get_db)):
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(404, "Tender not found")
    reqs = db.query(Requirement).filter(Requirement.tender_id == tender_id).all()
    status_results = evaluate_all(db, tender_id)
    dec = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not dec:
        dec, status_results = get_or_create_decision(db, tender_id)
    risks = db.query(Risk).filter(Risk.tender_id == tender_id).all()
    missing = db.query(MissingEvidence).all()
    evidences = db.query(Evidence).all()
    return {
        "tender": {"id": tender.id, "title": tender.title, "client": tender.client, "location": tender.location},
        "decision": {"decision": dec.decision, "confidence": dec.confidence, "decision_id": dec.id, "timestamp": str(dec.timestamp), "rules_triggered": dec.rules_triggered, "hard_fail_count": dec.hard_fail_count, "mandatory_missing_evidence_count": dec.mandatory_missing_count, "top_blockers": dec.top_blockers, "top_risks": dec.top_risks},
        "requirements": [
            {
                "requirement_id": r.id,
                "category": r.category,
                "requirement": r.requirement,
                "mandatory": r.mandatory,
                "requirement_type": r.requirement_type,
                "status": status_results.get(r.id, {}).get("status"),
                "evidence_ids": status_results.get(r.id, {}).get("evidence_ids"),
                "reason": status_results.get(r.id, {}).get("reason"),
                "provenance": status_results.get(r.id, {}).get("provenance"),
                "source_document": r.source_document,
                "page_or_section": r.page_or_section
            } for r in reqs
        ],
        "evidences": [{"id": e.id, "requirement_id": e.requirement_id, "fact": e.fact, "status": e.status, "source_document": e.source_document, "page_or_section": e.page_or_section, "extraction_confidence": e.extraction_confidence} for e in evidences],
        "risks": [{"id": r.id, "type": r.type, "severity": r.severity, "description": r.description, "mitigation": r.mitigation, "decision_impact": r.decision_impact, "source_requirement": r.source_requirement} for r in risks],
        "missing_evidence": [{"id": m.id, "requirement_id": m.requirement_id, "document_needed": m.document_needed, "priority": m.priority, "owner": m.owner, "why_needed": m.why_needed, "status": m.status} for m in missing],
        "provenance_chain": "Requirement → Evidence → Source Document → Page/Section → Rule → Decision"
    }

@router.get("/tenders/{tender_id}/explanation")
def get_explanation(tender_id: str, db: Session = Depends(get_db)):
    dec = db.query(Decision).filter(Decision.tender_id == tender_id).order_by(Decision.timestamp.desc()).first()
    if not dec:
        dec, status_results = get_or_create_decision(db, tender_id)
    else:
        status_results = evaluate_all(db, tender_id)
    exp = build_explanation(db, tender_id, dec, status_results)
    return exp

@router.get("/company/{company_id}")
def get_company(company_id: str, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(404, "Company not found")
    docs = db.query(Evidence).filter(Evidence.company_id == company_id).all()
    return {"company": c, "evidences": docs}
