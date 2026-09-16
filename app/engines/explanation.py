from sqlalchemy.orm import Session
from app.models import Requirement, Risk, MissingEvidence

def build_explanation(db: Session, tender_id: str, decision_obj, status_results: dict):
    # hard_failures: requirements with FAIL
    hard_failures = []
    missing_evidence = []
    supporting_evidence = []
    conflicts = []
    # collect missing and conflicts from status_results
    for req_id, res in status_results.items():
        status = res.get("status")
        if status == "FAIL":
            req = db.query(Requirement).filter(Requirement.id == req_id).first()
            hard_failures.append({
                "requirement_id": req_id,
                "requirement": req.requirement if req else req_id,
                "category": req.category if req else "",
                "status": status,
                "evidence_ids": res.get("evidence_ids", []),
                "provenance": res.get("provenance", []),
                "reason": res.get("reason")
            })
        elif status in ("MISSING_EVIDENCE", "REVIEW"):
            # For explanation, missing_evidence includes both MISSING and REVIEW where evidence is absent/ambiguous
            # Use MissingEvidence table for details if exists
            me = db.query(MissingEvidence).filter(MissingEvidence.requirement_id == req_id).first()
            req = db.query(Requirement).filter(Requirement.id == req_id).first()
            missing_evidence.append({
                "requirement_id": req_id,
                "requirement": req.requirement if req else req_id,
                "category": req.category if req else "",
                "status": status,
                "priority": me.priority if me else ("CRITICAL" if req and req.mandatory else "MEDIUM"),
                "document_needed": me.document_needed if me else (", ".join(req.evidence_required) if req and req.evidence_required else req.requirement if req else ""),
                "owner": me.owner if me else "Tender Team",
                "why_needed": me.why_needed if me else res.get("reason"),
                "evidence_ids": res.get("evidence_ids", []),
                "provenance": res.get("provenance", [])
            })
        if res.get("conflicts"):
            for c in res["conflicts"]:
                conflicts.append({
                    "requirement_id": req_id,
                    "evidence_ids": c.get("evidence_ids", []),
                    "reason": c.get("reason")
                })
        # expired
        if res.get("expired"):
            conflicts.append({
                "requirement_id": req_id,
                "evidence_ids": res.get("expired_ids", []),
                "reason": res.get("reason")
            })

    risks = db.query(Risk).filter(Risk.tender_id == tender_id).all()
    risks_out = [
        {
            "risk_id": r.id,
            "type": r.type,
            "severity": r.severity,
            "description": r.description,
            "mitigation": r.mitigation,
            "decision_impact": r.decision_impact,
            "source_requirement": r.source_requirement
        } for r in risks
    ]

    # supporting evidence: collect provenance for PASS
    for req_id, res in status_results.items():
        if res.get("status") == "PASS":
            for p in res.get("provenance", []):
                supporting_evidence.append({
                    "requirement_id": req_id,
                    "evidence_id": p["evidence_id"],
                    "source_document": p["source_document"],
                    "page_or_section": p["page_or_section"],
                    "fact": p["fact"],
                    "confidence": p["extraction_confidence"]
                })

    # summary
    if decision_obj.decision == "REVIEW":
        summary = f"REVIEW — DO NOT BID YET: {len(missing_evidence)} evidence gaps require human review. Top blocker: {decision_obj.top_blockers[0] if decision_obj.top_blockers else 'multiple missing'}."
    elif decision_obj.decision == "NO_BID":
        summary = f"NO_BID: {len(hard_failures)} mandatory requirement(s) explicitly failed — {hard_failures[0]['requirement'] if hard_failures else 'hard fail'}."
    else:
        summary = f"BID: All {len(supporting_evidence)} mandatory requirements PASS with provenance; risks acceptable."

    return {
        "decision": decision_obj.decision,
        "confidence": decision_obj.confidence,
        "summary": summary,
        "hard_failures": hard_failures,
        "missing_evidence": missing_evidence,
        "risks": risks_out,
        "supporting_evidence": supporting_evidence,
        "conflicts": conflicts,
        "rules_triggered": decision_obj.rules_triggered or [],
        "provenance_chain": "Requirement → Evidence → Source Document → Page/Section → Rule → Decision",
        "tender_id": tender_id,
        "decision_id": decision_obj.id
    }
