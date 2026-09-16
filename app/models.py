from sqlalchemy import Column, String, Boolean, Text, DateTime, Float, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
from datetime import datetime

def gen_id(prefix=""):
    return f"{prefix}{uuid.uuid4().hex[:8].upper()}"

class Company(Base):
    __tablename__ = "companies"
    id = Column(String, primary_key=True)  # e.g. HYOSUNG_GIZA
    name = Column(String, nullable=False)
    country = Column(String)
    role = Column(String)

class CompanyDocument(Base):
    __tablename__ = "company_documents"
    id = Column(String, primary_key=True)
    company_id = Column(String, ForeignKey("companies.id"))
    document_type = Column(String)
    title = Column(String)
    source_path = Column(String)
    page = Column(String)
    section = Column(String)

class Tender(Base):
    __tablename__ = "tenders"
    id = Column(String, primary_key=True)  # SA/2018/HV2
    title = Column(String)
    client = Column(String)
    location = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class TenderDocument(Base):
    __tablename__ = "tender_documents"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"))
    title = Column(String)
    doc_type = Column(String)
    page = Column(String)
    section = Column(String)
    language = Column(String, default="EN")

class Requirement(Base):
    __tablename__ = "requirements"
    id = Column(String, primary_key=True)  # REQ-A
    tender_id = Column(String, ForeignKey("tenders.id"))
    category = Column(String)  # LEGAL etc
    requirement = Column(Text)
    mandatory = Column(Boolean, default=True)
    requirement_type = Column(String)  # HARD_GATE etc
    evidence_required = Column(JSON)  # list
    evaluation_logic = Column(JSON)
    source_document = Column(String)
    page_or_section = Column(String)
    applicable_entity = Column(String, default="CONSORTIUM")  # CONSORTIUM / GIZA / HYOSUNG / ANY / AMBIGUOUS
    ambiguity_note = Column(Text, nullable=True)

class Evidence(Base):
    __tablename__ = "evidences"
    id = Column(String, primary_key=True)  # E-001
    company_id = Column(String, ForeignKey("companies.id"))
    requirement_id = Column(String, ForeignKey("requirements.id"), nullable=True)
    evidence_type = Column(String)
    fact = Column(Text)
    status = Column(String)  # PASS / FAIL / REVIEW
    source_document = Column(String)
    page_or_section = Column(String)
    source_link = Column(String, nullable=True)
    source_quote = Column(Text, nullable=True)
    extraction_confidence = Column(String)  # HIGH / MEDIUM / LOW
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    applicable_entity = Column(String, default="CONSORTIUM")  # CONSORTIUM / GIZA / HYOSUNG
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    tender_source_id = Column(String, nullable=True)  # tender this evidence was originally sourced from, for reuse check
    reusable = Column(Boolean, default=True)  # if True, company fact reusable across tenders (certs, projects); if False, tender-specific (bid security)

class EvidenceMatch(Base):
    __tablename__ = "evidence_matches"
    id = Column(String, primary_key=True)
    requirement_id = Column(String, ForeignKey("requirements.id"))
    evidence_id = Column(String, ForeignKey("evidences.id"))
    match_confidence = Column(String)
    notes = Column(Text)

class Risk(Base):
    __tablename__ = "risks"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"))
    type = Column(String)  # COMMERCIAL etc
    severity = Column(String)
    description = Column(Text)
    source_requirement = Column(String, nullable=True)
    evidence_ids = Column(JSON, default=list)
    mitigation = Column(Text)
    decision_impact = Column(String)  # REVIEW / BID / NO_BID

class MissingEvidence(Base):
    __tablename__ = "missing_evidences"
    id = Column(String, primary_key=True)
    requirement_id = Column(String, ForeignKey("requirements.id"))
    document_needed = Column(String)
    priority = Column(String)  # CRITICAL / HIGH / MEDIUM / LOW
    owner = Column(String)
    why_needed = Column(String)
    status = Column(String)  # MISSING_EVIDENCE / REVIEW

class Decision(Base):
    __tablename__ = "decisions"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"))
    decision = Column(String)  # BID / REVIEW / NO_BID
    confidence = Column(String)  # LOW / MEDIUM / HIGH
    timestamp = Column(DateTime, default=datetime.utcnow)
    rules_triggered = Column(JSON)
    supporting_requirements = Column(JSON)
    supporting_evidence = Column(JSON)
    missing_evidence = Column(JSON)
    risks = Column(JSON)
    hard_fail_count = Column(Float, default=0)
    mandatory_missing_count = Column(Float, default=0)
    top_blockers = Column(JSON)
    top_risks = Column(JSON)
    is_override = Column(Boolean, default=False)

class DecisionAudit(Base):
    __tablename__ = "decision_audits"
    id = Column(String, primary_key=True)
    decision_id = Column(String, ForeignKey("decisions.id"))
    reviewer = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    previous_decision = Column(String)
    new_decision = Column(String)
    reason = Column(Text)
    comments = Column(Text)
