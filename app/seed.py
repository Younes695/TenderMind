"""
Test #001 Seed - Sarai 220/22kV GIS Substation SA/2018/HV2
HYOSUNG / GIZA SYSTEMS CONSORTIUM

Implements Sections 5,7,8 of spec with provenance.
"""
from app.database import SessionLocal, init_db
from app.models import Company, Tender, TenderDocument, Requirement, Evidence, EvidenceMatch, Risk
import uuid

def seed():
    init_db()
    db = SessionLocal()
    try:
        # Clear existing Test001 data
        for m in [EvidenceMatch, Risk, Evidence, Requirement, TenderDocument, Tender, Company]:
            db.query(m).delete()
        db.commit()

        # Company
        company = Company(id="HYOSUNG_GIZA", name="HYOSUNG / GIZA SYSTEMS CONSORTIUM", country="KR/EG", role="Consortium: Hyosung (off-shore, engineering/manufacturing) + Giza Systems (on-shore lead, local services/procurement/invoicing)")
        db.add(company)

        # Tender — stored ID uses hyphen to avoid URL slash issues; original tender no SA/2018/HV2 preserved in title/client display
        tender = Tender(id="SA-2018-HV2", title="Sarai 220/22kV GIS Substation (No. SA/2018/HV2)", client="Madinet Nasr for Housing and Development (MNHD)", location="Sarai, Egypt")
        db.add(tender)

        # Tender Documents
        docs = [
            TenderDocument(id="TD-001", tender_id="SA-2018-HV2", title="Sarai RFP", doc_type="RFP", page="p.2", section="Eligibility / First-category membership", language="EN"),
            TenderDocument(id="TD-002", tender_id="SA-2018-HV2", title="Volume 1 Section 1", doc_type="TENDER_VOLUME", page="p.2", section="General Requirements", language="EN"),
            TenderDocument(id="TD-003", tender_id="SA-2018-HV2", title="SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc", doc_type="CONSORTIUM_AGREEMENT", page="Page 1, Preamble", section="Preamble / Joint and Several Liability", language="EN"),
            TenderDocument(id="TD-004", tender_id="SA-2018-HV2", title="Tender General Conditions", doc_type="GENERAL_CONDITIONS", page="Various", section="Commercial / Schedule / Guarantees", language="EN"),
        ]
        for d in docs:
            db.add(d)

        # Requirements A-U (21)
        reqs = [
            Requirement(id="REQ-A", tender_id="SA-2018-HV2", category="LEGAL", requirement="First-category Egyptian Union for Construction Contractors membership (or equivalent 1st Category) required for local partner", mandatory=True, requirement_type="HARD_GATE", evidence_required=["valid_first_category_membership_certificate/card"], evaluation_logic={"PASS":"Valid evidence confirms required classification.", "FAIL":"Evidence explicitly shows classification is not sufficient.", "MISSING_EVIDENCE":"No valid evidence found.", "REVIEW":"Evidence exists but applicability/validity is ambiguous."}, source_document="Sarai RFP p.2; Volume 1 Section 1 p.2", page_or_section="RFP p.2 / Vol1 S1 p.2"),
            Requirement(id="REQ-B", tender_id="SA-2018-HV2", category="TECHNICAL", requirement="Equipment origin must be from approved countries: Europe, South Korea, Japan, North America", mandatory=True, requirement_type="HARD_GATE", evidence_required=["equipment_origin_country_per_component"], evaluation_logic={"PASS":"All major equipment origin within approved list.", "FAIL":"Equipment from non-approved origin.", "MISSING_EVIDENCE":"Origin not evidenced per component.", "REVIEW":"Origin evidenced for consortium but not per component."}, source_document="Technical Specification", page_or_section="Origin restriction clause"),
            Requirement(id="REQ-C", tender_id="SA-2018-HV2", category="COMMERCIAL", requirement="Tender security EGP 5,700,000 valid for 270 days", mandatory=True, requirement_type="SUBMISSION", evidence_required=["tender_security_EGP_5.7M_270d"], evaluation_logic={"PASS":"Valid tender security provided.", "FAIL":"Tender security invalid/insufficient.", "MISSING_EVIDENCE":"No tender security evidence.", "REVIEW":"Tender security draft or validity ambiguous."}, source_document="Instructions to Bidders", page_or_section="Bid Security section"),
            Requirement(id="REQ-D", tender_id="SA-2018-HV2", category="EXPERIENCE", requirement="Similar substation experience (qualifying reference projects)", mandatory=True, requirement_type="EXPERIENCE", evidence_required=["completed Form E / qualifying project references"], evaluation_logic={"PASS":"Qualifying projects meet criteria.", "FAIL":"References explicitly disqualify.", "MISSING_EVIDENCE":"No qualifying references found.", "REVIEW":"References incomplete/ambiguous."}, source_document="Qualification Requirements", page_or_section="Experience clause"),
            Requirement(id="REQ-E", tender_id="SA-2018-HV2", category="EXPERIENCE", requirement="Successful continuous operation threshold (equipment operating history)", mandatory=True, requirement_type="EXPERIENCE", evidence_required=["qualifying operating references and customer certificates"], evaluation_logic={"PASS":"Operating history meets threshold.", "FAIL":"Operating history insufficient.", "MISSING_EVIDENCE":"No operating references.", "REVIEW":"Operating references ambiguous."}, source_document="Technical Qualification", page_or_section="Operation threshold clause"),
            Requirement(id="REQ-F", tender_id="SA-2018-HV2", category="EXPERIENCE", requirement="Experience within required historical window (project dates within window)", mandatory=True, requirement_type="EXPERIENCE", evidence_required=["project dates + completion/operation evidence"], evaluation_logic={"PASS":"Dates within window.", "FAIL":"Projects outside window.", "MISSING_EVIDENCE":"Dates not evidenced.", "REVIEW":"Dates ambiguous."}, source_document="Experience Requirements", page_or_section="Historical window clause"),
            Requirement(id="REQ-G", tender_id="SA-2018-HV2", category="EXPERIENCE", requirement="Employer completion/reference certificates for claimed projects", mandatory=True, requirement_type="EXPERIENCE", evidence_required=["employer_completion_certificates"], evaluation_logic={"PASS":"Certificates confirm completion.", "FAIL":"Certificates contradict.", "MISSING_EVIDENCE":"No certificates.", "REVIEW":"Certificates partial/uncertified."}, source_document="Submission Forms", page_or_section="Form E / Completion cert section"),
            Requirement(id="REQ-H", tender_id="SA-2018-HV2", category="EXPERIENCE", requirement="220kV GIS experience (voltage-specific)", mandatory=True, requirement_type="EXPERIENCE", evidence_required=["220kV GIS project references"], evaluation_logic={"PASS":"220kV GIS experience evidenced.", "FAIL":"220kV GIS not evidenced / contradicted.", "MISSING_EVIDENCE":"No 220kV GIS reference.", "REVIEW":"Reference does not clearly state 220kV."}, source_document="Technical Qualification", page_or_section="220kV GIS clause"),
            Requirement(id="REQ-I", tender_id="SA-2018-HV2", category="EXPERIENCE", requirement="175MVA transformer experience", mandatory=True, requirement_type="EXPERIENCE", evidence_required=["175MVA transformer project references"], evaluation_logic={"PASS":"175MVA experience evidenced.", "FAIL":"Experience contradicted.", "MISSING_EVIDENCE":"No 175MVA reference.", "REVIEW":"Capacity ambiguous."}, source_document="Technical Qualification", page_or_section="Transformer clause"),
            Requirement(id="REQ-J", tender_id="SA-2018-HV2", category="TECHNICAL", requirement="OEM/manufacturer relationship (authorization/consortium manufacturing linkage)", mandatory=False, requirement_type="TECHNICAL", evidence_required=["OEM_authorization_or_consortium_manufacturing_link"], evaluation_logic={"PASS":"OEM linkage evidenced.", "FAIL":"Linkage contradicted.", "MISSING_EVIDENCE":"No OEM linkage.", "REVIEW":"Linkage structural but not per-equipment."}, source_document="Technical Requirements", page_or_section="OEM clause"),
            Requirement(id="REQ-K", tender_id="SA-2018-HV2", category="TECHNICAL", requirement="Type-test certificates for major equipment (GIS, transformer)", mandatory=True, requirement_type="TECHNICAL", evidence_required=["type_test_certificates"], evaluation_logic={"PASS":"Valid type tests.", "FAIL":"Type tests invalid/failed.", "MISSING_EVIDENCE":"No type tests.", "REVIEW":"Certificates exist but validity ambiguous."}, source_document="Technical Specification", page_or_section="Type-test clause"),
            Requirement(id="REQ-L", tender_id="SA-2018-HV2", category="EQUIPMENT", requirement="Equipment operating references (installed base references)", mandatory=True, requirement_type="EQUIPMENT", evidence_required=["equipment_operating_references"], evaluation_logic={"PASS":"Operating refs meet criteria.", "FAIL":"Refs contradict.", "MISSING_EVIDENCE":"No operating refs.", "REVIEW":"Refs partial."}, source_document="Equipment Qualification", page_or_section="Operating refs clause"),
            Requirement(id="REQ-M", tender_id="SA-2018-HV2", category="PERSONNEL", requirement="Key personnel with required experience (project manager, commissioning, GIS specialists) — CVs, years, credentials", mandatory=True, requirement_type="PERSONNEL", evidence_required=["CVs, role, years, credentials"], evaluation_logic={"PASS":"Key personnel meet criteria.", "FAIL":"Personnel insufficient.", "MISSING_EVIDENCE":"No CVs.", "REVIEW":"CVs incomplete/uncertified."}, source_document="Personnel Requirements", page_or_section="Key personnel clause"),
            Requirement(id="REQ-N", tender_id="SA-2018-HV2", category="HSE", requirement="HSE capability (policy, plan, record)", mandatory=True, requirement_type="HSE", evidence_required=["HSE_policy_plan_record"], evaluation_logic={"PASS":"HSE evidenced.", "FAIL":"HSE contradicted.", "MISSING_EVIDENCE":"No HSE evidence.", "REVIEW":"HSE evidence generic."}, source_document="HSE Requirements", page_or_section="HSE clause"),
            Requirement(id="REQ-O", tender_id="SA-2018-HV2", category="QA_QC", requirement="QA/QC capability (system, procedures, certificates)", mandatory=True, requirement_type="QA_QC", evidence_required=["QA_QC_system_procedures"], evaluation_logic={"PASS":"QA/QC evidenced.", "FAIL":"QA/QC insufficient.", "MISSING_EVIDENCE":"No QA/QC evidence.", "REVIEW":"QA/QC generic/not project-specific."}, source_document="QA/QC Requirements", page_or_section="QA/QC clause"),
            Requirement(id="REQ-P", tender_id="SA-2018-HV2", category="EQUIPMENT", requirement="Construction equipment and manpower capability", mandatory=True, requirement_type="EQUIPMENT", evidence_required=["construction_equipment_list"], evaluation_logic={"PASS":"Equipment adequate.", "FAIL":"Equipment insufficient.", "MISSING_EVIDENCE":"No equipment list.", "REVIEW":"List generic."}, source_document="Resources Requirements", page_or_section="Equipment clause"),
            Requirement(id="REQ-Q", tender_id="SA-2018-HV2", category="SUBCONTRACTOR", requirement="Subcontractor qualifications (where applicable)", mandatory=False, requirement_type="SUBCONTRACTOR", evidence_required=["subcontractor_qualification_docs"], evaluation_logic={"PASS":"Subcontractors qualified.", "FAIL":"Subcontractors disqualify.", "MISSING_EVIDENCE":"No subcontractor evidence.", "REVIEW":"Subcontractor list incomplete."}, source_document="Subcontractor Requirements", page_or_section="Subcontractor clause"),
            Requirement(id="REQ-R", tender_id="SA-2018-HV2", category="LEGAL", requirement="Consortium/JV evidence — executed agreement with joint/several liability and scope split", mandatory=True, requirement_type="HARD_GATE", evidence_required=["executed_consortium_agreement"], evaluation_logic={"PASS":"Consortium agreement valid.", "FAIL":"Agreement invalid/unsigned.", "MISSING_EVIDENCE":"No agreement.", "REVIEW":"Agreement draft/unsigned."}, source_document="Consortium Requirements", page_or_section="JV clause"),
            Requirement(id="REQ-S", tender_id="SA-2018-HV2", category="FINANCIAL", requirement="Financial capacity (turnover, working capital, credit facilities, audited statements)", mandatory=True, requirement_type="FINANCIAL", evidence_required=["audited_financials_turnover_working_capital"], evaluation_logic={"PASS":"Financial capacity meets threshold.", "FAIL":"Capacity insufficient.", "MISSING_EVIDENCE":"No financial evidence.", "REVIEW":"Financials partial/unaudited."}, source_document="Financial Qualification", page_or_section="Financial clause"),
            Requirement(id="REQ-T", tender_id="SA-2018-HV2", category="SCHEDULE", requirement="Ability to meet schedule (Form C / resource plan / programme)", mandatory=True, requirement_type="SCHEDULE", evidence_required=["Form_C_schedule_capability"], evaluation_logic={"PASS":"Schedule capability evidenced.", "FAIL":"Cannot meet schedule.", "MISSING_EVIDENCE":"No schedule evidence.", "REVIEW":"Schedule generic."}, source_document="Schedule Requirements", page_or_section="Programme clause"),
            Requirement(id="REQ-U", tender_id="SA-2018-HV2", category="COMMERCIAL", requirement="Performance guarantee — joint commitment / bank guarantee capacity", mandatory=True, requirement_type="COMMERCIAL", evidence_required=["bank_facility_or_performance_guarantee_evidence"], evaluation_logic={"PASS":"Bank guarantee capacity evidenced.", "FAIL":"Cannot provide guarantee.", "MISSING_EVIDENCE":"No guarantee evidence.", "REVIEW":"Consortium agreement shows intent but not bank capacity."}, source_document="Commercial Conditions", page_or_section="Performance guarantee clause / Consortium Agreement"),
        ]
        # Set applicability per spec §19 #6: REQ-A must be Giza-specific
        for _r in reqs:
            if _r.id == "REQ-A":
                _r.applicable_entity = "GIZA"
            else:
                _r.applicable_entity = "CONSORTIUM"
        for r in reqs:
            db.add(r)

        # Evidences — ONLY what exists, do NOT invent
        evidences = [
            Evidence(id="E-001", company_id="HYOSUNG_GIZA", requirement_id="REQ-R", evidence_type="CONSORTIUM_AGREEMENT", fact="Hyosung and Giza Systems form a consortium with defined responsibilities: Hyosung off-shore engineering/manufacturing, Giza on-shore lead for local services/procurement/invoicing, with joint and several liability.", status="PASS", source_document="SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc", page_or_section="Page 1, Preamble + Joint Liability section", source_link="", source_quote="Consortium between Hyosung Corporation and Giza Systems...", extraction_confidence="HIGH", notes="Spec Section 5 R — PASS", applicable_entity="CONSORTIUM", reusable=True),
            Evidence(id="E-002", company_id="HYOSUNG_GIZA", requirement_id="REQ-B", evidence_type="EQUIPMENT_ORIGIN", fact="Hyosung Corporation is a South Korean manufacturer — South Korea is within approved origin list (Europe, South Korea, Japan, North America). Equipment of Hyosung origin satisfies origin gate, but component-level origin per equipment still requires verification.", status="PASS", source_document="SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc", page_or_section="Consortium members page — Hyosung Corporation, South Korea", source_link="", source_quote="Hyosung Corporation — South Korea", extraction_confidence="HIGH", notes="REQ-B PASS limited to Hyosung-origin; component check remains", applicable_entity="HYOSUNG", reusable=True),
            Evidence(id="E-003", company_id="HYOSUNG_GIZA", requirement_id="REQ-J", evidence_type="OEM_RELATIONSHIP", fact="Hyosung as consortium member IS the OEM/manufacturer for core GIS equipment, providing structural OEM linkage.", status="PASS", source_document="SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc", page_or_section="Page 1, Preamble — Hyosung Corporation", source_link="", extraction_confidence="HIGH", notes="Per spec correction #3: OEM PASS does not auto-satisfy type-tests/operating refs.", applicable_entity="HYOSUNG", reusable=True),
            Evidence(id="E-004", company_id="HYOSUNG_GIZA", requirement_id="REQ-U", evidence_type="PERFORMANCE_GUARANTEE_COMMITMENT", fact="Consortium agreement contains joint commitment mechanism and joint/several liability for performance, indicating contractual intent/structure.", status="REVIEW", source_document="SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc", page_or_section="Joint and Several Liability section", source_link="", extraction_confidence="MEDIUM", notes="Per spec Section 5 U and Section 19 correction #1: structural commitment, NOT proof of bank issuance capacity. Must be REVIEW.", applicable_entity="CONSORTIUM", reusable=True),
        ]
        for e in evidences:
            db.add(e)

        # EvidenceMatches
        for e in evidences:
            m = EvidenceMatch(id=f"M-{e.id}", requirement_id=e.requirement_id, evidence_id=e.id, match_confidence="HIGH" if e.status=="PASS" else "MEDIUM", notes=f"Match for {e.requirement_id}")
            db.add(m)

        # Risks (Section 7)
        risks = [
            Risk(id="R-001", tender_id="SA-2018-HV2", type="COMMERCIAL", severity="HIGH", description="Fixed-price exposure during the project period.", source_requirement="COMMERCIAL_FIXED_PRICE", evidence_ids=[], mitigation="Commercial review before bid approval; price escalation analysis.", decision_impact="REVIEW"),
            Risk(id="R-002", tender_id="SA-2018-HV2", type="COMMERCIAL", severity="HIGH", description="Foreign-currency exposure (KRW/USD/EGP) on imported equipment.", source_requirement="COMMERCIAL_FX", evidence_ids=[], mitigation="FX hedging / currency clause review.", decision_impact="REVIEW"),
            Risk(id="R-003", tender_id="SA-2018-HV2", type="SCHEDULE", severity="HIGH", description="Aggressive execution milestones with liquidated-damages exposure.", source_requirement="SCHEDULE_LD", evidence_ids=[], mitigation="Schedule realism + resource-loaded programme review.", decision_impact="REVIEW"),
            Risk(id="R-004", tender_id="SA-2018-HV2", type="COMMERCIAL", severity="MEDIUM", description="Liquidated-damages exposure for delay.", source_requirement="SCHEDULE_LD", evidence_ids=[], mitigation="LD cap negotiation / schedule contingency.", decision_impact="REVIEW"),
            Risk(id="R-005", tender_id="SA-2018-HV2", type="COMMERCIAL", severity="MEDIUM", description="Transformer-loss commercial evaluation (capitalized loss evaluation).", source_requirement="TECHNICAL_TRANSFORMER_LOSS", evidence_ids=[], mitigation="Technical/commercial loss evaluation.", decision_impact="REVIEW"),
            Risk(id="R-006", tender_id="SA-2018-HV2", type="FINANCIAL", severity="HIGH", description="Performance-guarantee cash/credit exposure (bank facility needed).", source_requirement="PERFORMANCE_GUARANTEE", evidence_ids=["E-004"], mitigation="Confirm bank facility before bid; do not rely on consortium agreement alone.", decision_impact="REVIEW"),
            Risk(id="R-007", tender_id="SA-2018-HV2", type="COMMERCIAL", severity="MEDIUM", description="Potential unbalanced pricing rejection.", source_requirement="COMMERCIAL_PRICING", evidence_ids=[], mitigation="Pricing balance review.", decision_impact="REVIEW"),
        ]
        for r in risks:
            db.add(r)

        db.commit()
        print("Seed Test001 complete: Tender SA/2018/HV2, 21 requirements, 4 evidences, 7 risks")

    finally:
        db.close()

if __name__ == "__main__":
    seed()
