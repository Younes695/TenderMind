from sqlalchemy import Column, String, Boolean, Text, DateTime, Float, Integer, JSON, ForeignKey, UniqueConstraint
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
    owner_email = Column(String, nullable=True, index=True)  # app/access.py

class Tender(Base):
    __tablename__ = "tenders"
    id = Column(String, primary_key=True)  # SA/2018/HV2
    title = Column(String)
    client = Column(String)
    location = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    owner_email = Column(String, nullable=True, index=True)  # app/access.py
    outcome = Column(String, nullable=True)  # Stage 6: WON | LOST | SUBMITTED | NOT_SUBMITTED
    stage = Column(String, nullable=True)  # Stage 8: ELIGIBILITY | STUDY | PRICING | SUBMISSION | SUBMITTED | CLOSED
    submission_deadline = Column(DateTime, nullable=True)  # Stage 8: set by the team
    final_decision = Column(String, nullable=True)  # Stage 9: GO | NO_GO — the authorised team's decision
    final_reason = Column(Text, nullable=True)
    final_by = Column(String, nullable=True)
    final_at = Column(DateTime, nullable=True)

class TenderDocument(Base):
    __tablename__ = "tender_documents"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"))
    title = Column(String)  # original filename / human title, never full path
    doc_type = Column(String)
    page = Column(String)
    section = Column(String)
    language = Column(String, default="EN")
    # Canonical persisted file reference — absolute or storage-root-relative path
    # Added in Stage 1B; title remains human-readable filename.
    source_path = Column(String, nullable=True)
    file_size = Column(Float, nullable=True)
    original_filename = Column(String, nullable=True)

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

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"))
    status = Column(String, default="QUEUED")  # QUEUED, PROCESSING, COMPLETED, PARTIAL, FAILED
    current_stage = Column(String, default="INVENTORY")
    progress = Column(Float, default=0)
    documents_total = Column(Float, default=0)
    documents_processed = Column(Float, default=0)
    documents_failed = Column(Float, default=0)
    documents_unsupported = Column(Float, default=0)
    error_count = Column(Float, default=0)
    last_error = Column(Text, nullable=True)
    result_version = Column(String, default="1.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    pipeline_version = Column(String, default="1.0")
    model = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)

class TenderAnalysis(Base):
    __tablename__ = "tender_analyses"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"))
    processing_job_id = Column(String, ForeignKey("processing_jobs.id"))
    analysis_version = Column(String, default="1.0")
    pipeline_version = Column(String, default="1.0")
    model = Column(String, nullable=True)
    prompt_version = Column(String, nullable=True)
    status = Column(String, default="COMPLETED")  # COMPLETED, PARTIAL, FAILED
    created_at = Column(DateTime, default=datetime.utcnow)
    # Canonical analysis JSON — validated against schemas/tender_agnostic_schema.json
    tender = Column(JSON)  # {id, title, client, location}
    documents = Column(JSON)  # [{filename, document_type, processing_status, ...}]
    requirements = Column(JSON)  # [{id, summary, category, mandatory, ... , source_document, page_number, source_chunk_id, source_text}]
    evidence = Column(JSON)  # [{id, requirement_id, summary, source_document, ...}]
    deadlines = Column(JSON)
    commercial = Column(JSON)
    risks = Column(JSON)
    derived_features = Column(JSON)
    processing = Column(JSON)  # {job_id, status, progress, documents_total, etc.}

class StageEvent(Base):
    """Stage 4G — persisted per-stage job history (auto-created; no migration).

    One row per stage transition: recoverable progress after refresh/reconnect,
    per-stage timestamps, failure reasons, truthful counts. `progress` on the
    job remains a coarse stage marker; this table is the source of truth.
    """
    __tablename__ = "stage_events"
    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("processing_jobs.id"))
    stage = Column(String)
    status = Column(String, default="COMPLETED")  # STARTED | COMPLETED | PARTIAL | FAILED
    counts = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    """Stage 5F — accounts: email + password, or Google / Microsoft sign-in.

    password_hash is null for accounts created through an identity provider;
    such a user can add a password later. Emails are stored lower-case and are
    the login identity (one account per email across providers).
    """
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    password_hash = Column(String, nullable=True)
    provider = Column(String, default="password")  # password | google | microsoft
    provider_subject = Column(String, nullable=True)
    # Bumped on password change and account takeover; sessions carry it and are
    # refused once it moves on (app/auth.py _principal).
    session_version = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class TenderIssue(Base):
    """Stage 5H — things a person must look at, per tender.

    category "missing": review required (missing / unreadable / unsupported files,
    referenced documents not in the package, mandatory requirements with no
    company evidence) — surfaced as notifications.
    category "question": the Q&A list (ambiguous clauses, unreadable scanned
    pages, requirements the AI could not classify) with an answer field.
    dedupe_key keeps rebuilds idempotent and never reopens a resolved item.
    """
    __tablename__ = "tender_issues"
    __table_args__ = (UniqueConstraint("tender_id", "dedupe_key", name="uq_issue_tender_key"),)
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"), index=True, nullable=False)
    category = Column(String, nullable=False)  # missing | question
    kind = Column(String, nullable=False)
    title = Column(String, nullable=False)
    detail = Column(Text, nullable=True)
    source_document = Column(String, nullable=True)
    page = Column(String, nullable=True)
    priority = Column(String, default="MEDIUM")  # HIGH | MEDIUM | LOW
    status = Column(String, default="OPEN", index=True)  # OPEN | RESOLVED
    answer = Column(Text, nullable=True)
    resolved_by = Column(String, nullable=True)
    dedupe_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class NewsItem(Base):
    """Stage 5H — tender notices from official sources (no personal contact data)."""
    __tablename__ = "news_items"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_news_source_ext"),)
    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    external_id = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    country = Column(String, nullable=True, index=True)
    notice_type = Column(String, nullable=True)
    organization = Column(String, nullable=True)
    url = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True, index=True)
    deadline_at = Column(DateTime, nullable=True)
    relevant = Column(Boolean, default=False, index=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class Rfq(Base):
    """Stage 5I — a request for quotation for one work package of a tender."""
    __tablename__ = "rfqs"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"), index=True, nullable=False)
    reference = Column(String, nullable=False)       # e.g. RFQ-MECH-04
    package_name = Column(String, nullable=False)    # e.g. Mechanical Work Package
    discipline = Column(String, nullable=True)       # e.g. HVAC
    scope = Column(Text, nullable=True)              # keywords / scope used to pick requirements
    invited_count = Column(Float, nullable=True)
    closes_at = Column(DateTime, nullable=True)
    currency = Column(String, default="SAR")
    status = Column(String, default="OPEN")          # OPEN | CLOSED | AWARDED
    created_at = Column(DateTime, default=datetime.utcnow)


class Quotation(Base):
    """One subcontractor's answer to an RFQ. Technical fit is entered by the engineer."""
    __tablename__ = "quotations"
    id = Column(String, primary_key=True)
    rfq_id = Column(String, ForeignKey("rfqs.id"), index=True, nullable=False)
    contractor = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    duration_weeks = Column(Float, nullable=False)
    technical_fit = Column(Float, nullable=False)    # 0-100 %
    payment_terms_days = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    selected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Feedback(Base):
    """Stage 5I — problems / suggestions sent from inside the product."""
    __tablename__ = "feedback"
    id = Column(String, primary_key=True)
    user_email = Column(String, index=True, nullable=True)
    kind = Column(String, default="problem")         # problem | suggestion | upgrade
    message = Column(Text, nullable=False)
    page = Column(String, nullable=True)
    plan = Column(String, nullable=True)
    status = Column(String, default="NEW")           # NEW | IN_PROGRESS | DONE
    created_at = Column(DateTime, default=datetime.utcnow)


class CompanyProfile(Base):
    """Stage 5J — the bidder's own details, used in bid emails (one per account)."""
    __tablename__ = "company_profiles"
    id = Column(String, primary_key=True)  # account email, or "local" when auth is off
    name = Column(String, nullable=True)
    intro = Column(Text, nullable=True)
    contact_name = Column(String, nullable=True)
    contact_title = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    address = Column(String, nullable=True)
    account_type = Column(String, nullable=True)  # company (default) | individual professional
    updated_at = Column(DateTime, default=datetime.utcnow)



class CompanyCapability(Base):
    """Stage 6 — what the company can bid for (one row per account, like CompanyProfile)."""
    __tablename__ = "company_capabilities"
    id = Column(String, primary_key=True)             # account email or "local"
    work_types = Column(JSON, default=list)           # app/tender_facts.WORK_TYPES
    max_kv = Column(Float, nullable=True)
    countries = Column(JSON, default=list)
    registrations = Column(JSON, default=list)        # e.g. "SEC approved contractor"
    certifications = Column(JSON, default=list)       # e.g. "ISO 9001"
    years_experience = Column(Float, nullable=True)
    annual_turnover = Column(Float, nullable=True)
    turnover_currency = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class EligibilityResult(Base):
    """Stage 6 — outcome of the eligibility gate for a tender, and any override."""
    __tablename__ = "eligibility_results"
    tender_id = Column(String, ForeignKey("tenders.id"), primary_key=True)
    status = Column(String, nullable=False)           # ELIGIBLE | INELIGIBLE | SKIPPED
    checks = Column(JSON, default=list)
    override_by = Column(String, nullable=True)       # the account that continued
    override_name = Column(String, nullable=True)     # the person named (shared company login)
    override_reason = Column(Text, nullable=True)
    overridden_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TeamMember(Base):
    """Stage 6 — people who work on the company's tenders (one shared login)."""
    __tablename__ = "team_members"
    id = Column(String, primary_key=True)
    owner_email = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    department = Column(String, nullable=True)
    role = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TenderTask(Base):
    """Stage 6 — a task of the tender team on one tender."""
    __tablename__ = "tender_tasks"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"), index=True, nullable=False)
    title = Column(String, nullable=False)
    assignee = Column(String, nullable=True)          # team member name
    department = Column(String, nullable=True)
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="OPEN")           # OPEN | DONE
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    done_at = Column(DateTime, nullable=True)


class DepartmentVote(Base):
    """Stage 6 — one team member's go/no-go opinion, entered by the tender manager."""
    __tablename__ = "department_votes"
    __table_args__ = (UniqueConstraint("tender_id", "member_name", name="uq_vote_tender_member"),)
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"), index=True, nullable=False)
    member_name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    vote = Column(String, nullable=False)             # APPROVE | REJECT | ABSTAIN
    comment = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class ScoreSettings(Base):
    """Stage 6 — per-account Go/No-Go factor weights."""
    __tablename__ = "score_settings"
    id = Column(String, primary_key=True)             # account email or "local"
    weights = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow)


class SubmissionItem(Base):
    """Stage 7 — team state of one bid submission checklist item (items come from the analysis)."""
    __tablename__ = "submission_items"
    __table_args__ = (UniqueConstraint("tender_id", "item_key", name="uq_submission_item"),)
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"), index=True, nullable=False)
    item_key = Column(String, nullable=False)
    status = Column(String, default="TODO")           # TODO | READY | NOT_APPLICABLE
    assignee = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    """Stage 7 — who changed what on a tender, and when (decision pack audit trail)."""
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"), index=True, nullable=False)
    action = Column(String, nullable=False)
    detail = Column(JSON, default=dict)
    actor = Column(String, nullable=True)             # signed-in account
    actor_name = Column(String, nullable=True)        # person named on the shared login
    at = Column(DateTime, default=datetime.utcnow, index=True)


class TenderNote(Base):
    """Stage 8 — a note on a tender by a team member (shared login: the name is typed)."""
    __tablename__ = "tender_notes"
    id = Column(String, primary_key=True)
    tender_id = Column(String, ForeignKey("tenders.id"), index=True, nullable=False)
    author = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class PriceList(Base):
    """A supplier price list uploaded by the account (the only source of material prices)."""
    __tablename__ = "price_lists"
    id = Column(String, primary_key=True)
    owner = Column(String, index=True, nullable=False)   # account key (email, or "local" with auth off)
    supplier = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    price_date = Column(DateTime, nullable=False)        # the date printed on / given for the list
    filename = Column(String, nullable=True)
    items_count = Column(Float, default=0)
    uploaded_at = Column(DateTime, default=datetime.utcnow)


class PriceItem(Base):
    __tablename__ = "price_items"
    id = Column(String, primary_key=True)
    list_id = Column(String, ForeignKey("price_lists.id"), index=True, nullable=False)
    description = Column(Text, nullable=False)
    unit = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String, nullable=False)
    min_qty = Column(Float, default=0)                   # a price break: this price from this quantity
    key = Column(String, index=True, nullable=True)      # app.materials.material_key


class DemoRequest(Base):
    """A demo / sales request sent from the public website (no account needed)."""
    __tablename__ = "demo_requests"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    company = Column(String, nullable=True)
    country = Column(String, nullable=True)
    topic = Column(String, nullable=True)      # e.g. plan:growth, security, industry:power
    message = Column(Text, nullable=True)
    status = Column(String, default="NEW")     # NEW | CONTACTED
    created_at = Column(DateTime, default=datetime.utcnow)
