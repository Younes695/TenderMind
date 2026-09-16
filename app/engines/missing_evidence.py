from sqlalchemy.orm import Session
from app.models import Requirement, MissingEvidence

# Priority and owner mapping per spec Section 8
PRIORITY_MAP = {
    "REQ-A": ("CRITICAL", "Giza Systems / Legal", "Mandatory tender eligibility gate — first-category membership"),
    "REQ-C": ("CRITICAL", "Finance / Commercial", "Tender security EGP 5.7M 270d — submission requirement"),
    "REQ-R": ("CRITICAL", "Legal", "Consortium/JV executed agreement"),
    "REQ-D": ("HIGH", "Technical / Projects", "Similar substation experience (Form E)"),
    "REQ-E": ("HIGH", "Technical", "Successful continuous operation threshold"),
    "REQ-F": ("HIGH", "Technical", "Experience within historical window"),
    "REQ-G": ("HIGH", "Technical / Projects", "Employer completion/reference certificates"),
    "REQ-H": ("HIGH", "Technical", "220kV GIS experience"),
    "REQ-I": ("HIGH", "Technical", "175MVA transformer experience"),
    "REQ-K": ("HIGH", "Technical / QA", "Type-test certificates"),
    "REQ-L": ("HIGH", "Technical", "Equipment operating references"),
    "REQ-M": ("HIGH", "HR / Personnel", "Key personnel CVs"),
    "REQ-N": ("MEDIUM", "HSE", "HSE capability"),
    "REQ-O": ("MEDIUM", "QA/QC", "QA/QC capability"),
    "REQ-P": ("MEDIUM", "Operations / Equipment", "Construction equipment list"),
    "REQ-Q": ("LOW", "Subcontracts", "Subcontractor qualifications"),
    "REQ-S": ("HIGH", "Finance", "Financial capacity — do not invent numbers"),
    "REQ-T": ("MEDIUM", "Planning", "Schedule capability Form C"),
    "REQ-U": ("HIGH", "Finance / Legal", "Bank performance guarantee facility (not just consortium intent)"),
    "REQ-B": ("HIGH", "Technical", "Component-by-component origin verification"),
    "REQ-J": ("MEDIUM", "Technical", "OEM authorization per equipment"),
}

def generate_missing_evidence(db: Session, tender_id: str, status_results: dict):
    # status_results: {req_id: {status, ...}}
    items = []
    for req_id, res in status_results.items():
        status = res["status"]
        if status in ("MISSING_EVIDENCE", "REVIEW"):
            req = db.query(Requirement).filter(Requirement.id == req_id).first()
            if not req:
                continue
            # Only generate for mandatory or for review items that are actionable
            # Spec: priorities CRITICAL for mandatory gate, HIGH for mandatory qualification
            pri, owner, why = PRIORITY_MAP.get(req_id, ("MEDIUM", "Tender Team", "Evidence required per tender"))
            # For NOT mandatory and status MISSING, lower priority but still report
            me_id = f"ME-{req_id.replace('REQ-','')}"
            # Avoid duplicates: delete existing?
            existing = db.query(MissingEvidence).filter(MissingEvidence.requirement_id == req_id).first()
            if existing:
                db.delete(existing)
            me = MissingEvidence(
                id=me_id,
                requirement_id=req_id,
                document_needed=", ".join(req.evidence_required) if req.evidence_required else req.requirement,
                priority=pri,
                owner=owner,
                why_needed=why if status=="MISSING_EVIDENCE" else why + " (validity ambiguous — human review needed)",
                status=status
            )
            db.add(me)
            items.append(me)
    db.commit()
    return items
