"""Stage 5C — uploaded tenders reach the decision engine with evidence provenance."""
import os
import tempfile
import uuid
from pathlib import Path

import pytest

from app.matchers.base import BaseMatcher, MatcherOutput


class StubMatcher(BaseMatcher):
    """Deterministic stand-in for HybridMatcher: verdict by requirement category."""
    name = "stub"

    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.llm_calls = 0
        self.seen = []

    def match(self, inp):
        self.seen.append((inp.requirement_category, inp.source_document, inp.page_or_section))
        v = self.verdicts.get(inp.requirement_category, "MISSING")
        return MatcherOutput(support=v == "PASS", contradiction=v == "FAIL",
                             supporting_facts=["fact"] if v == "PASS" else [],
                             contradictory_facts=["contra"] if v == "FAIL" else [],
                             applicability=v, confidence=0.9, reason=f"stub {v}")


@pytest.fixture()
def db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.database import Base
    from app import models  # noqa: F401
    eng = create_engine(f"sqlite:///{(tmp_path / 't.db').as_posix()}")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _tender_with_analysis(db, tid="T-5C"):
    from app.models import Tender, TenderAnalysis
    db.add(Tender(id=tid, title="t", client="c", location="l"))
    reqs = [
        {"requirement_id": "REQ-001", "category": "EXPERIENCE", "summary": "Bidder must have completed three similar substation projects",
         "mandatory": None, "source_document": "vol1.pdf", "page_number": 12, "source_text": "similar projects"},
        {"requirement_id": "REQ-002", "category": "FINANCIAL", "summary": "Average annual turnover of at least 100 million",
         "mandatory": None, "source_document": "vol1.pdf", "page_number": 14, "source_text": "turnover"},
        {"requirement_id": "REQ-003", "category": "TECHNICAL", "summary": "Transformers rated 125 MVA",
         "mandatory": None, "source_document": "vol2.pdf", "page_number": 3, "source_text": "125 MVA"},
        {"requirement_id": "REQ-004", "category": "UNKNOWN", "summary": "noise", "mandatory": None,
         "source_document": "vol2.pdf", "page_number": 9, "source_text": "noise"},
    ]
    db.add(TenderAnalysis(id=f"AN-{uuid.uuid4().hex[:6]}", tender_id=tid, requirements=reqs, evidence=[],
                          documents=[], tender={}))
    db.commit()
    return tid


def _company_doc(db, tmp_path):
    from app.engines.tender_bridge import COMPANY_ID, ensure_company
    from app.models import CompanyDocument
    ensure_company(db)
    p = tmp_path / "profile.txt"
    p.write_text("Company profile.\nWe completed three similar substation projects in 2019, 2021 and 2023 for EETC.\n"
                 "Our average annual turnover over the last three years was 40 million EGP.\n", encoding="utf-8")
    db.add(CompanyDocument(id="CDOC-1", company_id=COMPANY_ID, document_type="TXT", title="profile.txt",
                           source_path=str(p)))
    db.commit()


def test_sync_quarantines_unknown_and_gates_only_qualification(db):
    from app.engines.tender_bridge import sync_requirements
    from app.models import Requirement
    tid = _tender_with_analysis(db)
    res = sync_requirements(db, tid)
    assert res == {"synced": 3, "skipped_unknown": 1, "mandatory": 2}
    rows = {r.category: r for r in db.query(Requirement).filter(Requirement.tender_id == tid)}
    assert rows["EXPERIENCE"].mandatory and rows["EXPERIENCE"].requirement_type == "HARD_GATE"
    assert rows["TECHNICAL"].mandatory is False  # specification lines never block
    assert rows["FINANCIAL"].page_or_section == "p.14" and rows["FINANCIAL"].source_document == "vol1.pdf"
    # idempotent: re-sync replaces, never duplicates
    sync_requirements(db, tid)
    assert db.query(Requirement).filter(Requirement.tender_id == tid).count() == 3


def test_no_company_evidence_means_review_never_no_bid(db, tmp_path):
    from app.engines.tender_bridge import evaluate_tender
    tid = _tender_with_analysis(db)
    res = evaluate_tender(db, tid, matcher=StubMatcher({}))
    assert res["decision"] == "REVIEW"  # MISSING != FAIL
    assert res["MISSING"] == 2


def test_all_pass_with_provenance_gives_bid(db, tmp_path):
    from app.engines.tender_bridge import evaluate_tender
    from app.models import Evidence
    tid = _tender_with_analysis(db)
    _company_doc(db, tmp_path)
    m = StubMatcher({"EXPERIENCE": "PASS", "FINANCIAL": "PASS"})
    res = evaluate_tender(db, tid, matcher=m)
    assert res["decision"] == "BID" and res["PASS"] == 2
    ev = db.query(Evidence).filter(Evidence.status == "PASS").first()
    assert ev.source_document == "profile.txt" and ev.page_or_section == "p.1" and ev.source_quote


def test_explicit_contradiction_on_hard_gate_gives_no_bid(db, tmp_path):
    from app.engines.tender_bridge import evaluate_tender
    tid = _tender_with_analysis(db)
    _company_doc(db, tmp_path)
    res = evaluate_tender(db, tid, matcher=StubMatcher({"EXPERIENCE": "PASS", "FINANCIAL": "FAIL"}))
    assert res["decision"] == "NO_BID"


def test_reevaluation_replaces_previous_evidence(db, tmp_path):
    from app.engines.tender_bridge import evaluate_tender
    from app.models import Evidence
    tid = _tender_with_analysis(db)
    _company_doc(db, tmp_path)
    evaluate_tender(db, tid, matcher=StubMatcher({"EXPERIENCE": "PASS", "FINANCIAL": "PASS"}))
    evaluate_tender(db, tid, matcher=StubMatcher({"EXPERIENCE": "PASS", "FINANCIAL": "PASS"}))
    assert db.query(Evidence).count() == 2


def test_seeded_demo_tender_is_never_touched(db):
    from app.engines.tender_bridge import sync_requirements
    assert sync_requirements(db, "SA-2018-HV2")["synced"] == 0


def test_api_company_documents_and_decision_detail(tmp_path, monkeypatch):
    """HTTP level: upload company doc, decision-detail returns provenance for an uploaded tender."""
    from fastapi.testclient import TestClient
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path / "store"))
    from app.main import app
    from app.database import SessionLocal
    from app.engines import tender_bridge as tb
    c = TestClient(app)
    c.__enter__()  # run app startup (creates tables on a fresh test database)
    r = c.post("/api/company-documents", files=[("files", ("../evil<name>.txt", b"We completed similar projects.", "text/plain"))])
    assert r.status_code == 200
    doc = r.json()["documents"][0]
    assert "/" not in doc["title"] and "<" not in doc["title"]
    assert c.post("/api/company-documents", files=[("files", ("x.exe", b"MZ", "application/octet-stream"))]).status_code == 400
    tid = f"T-5C-API-{uuid.uuid4().hex[:6]}"
    db = SessionLocal()
    try:
        _tender_with_analysis(db, tid)
        tb.sync_requirements(db, tid)
    finally:
        db.close()
    d = c.get(f"/api/tenders/{tid}/decision-detail").json()
    assert d["available"] and d["decision"]["decision"] == "REVIEW"
    first = d["requirements"][0]
    assert first["mandatory"] and first["status"] == "MISSING_EVIDENCE" and first["page_or_section"].startswith("p.")
    assert c.delete(f"/api/company-documents/{doc['id']}").status_code == 200
    # leave the shared dev database as we found it
    from app.models import Decision, MissingEvidence, Requirement, Tender, TenderAnalysis
    db = SessionLocal()
    try:
        tb._clear_bridge_rows(db, tid)
        db.query(MissingEvidence).filter(MissingEvidence.requirement_id.like(f"{tid}::%")).delete(synchronize_session=False)
        db.query(Decision).filter(Decision.tender_id == tid).delete(synchronize_session=False)
        db.query(Requirement).filter(Requirement.tender_id == tid).delete(synchronize_session=False)
        db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tid).delete(synchronize_session=False)
        db.query(Tender).filter(Tender.id == tid).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()
    c.__exit__(None, None, None)


def _judge(reply):
    import json
    from app.engines.tender_bridge import EvidenceJudge
    return EvidenceJudge("stub", transport=lambda s, u: json.dumps(reply))


def _pair(fact="Average annual turnover over the last three years: EGP 1.2 billion."):
    from app.matchers.base import MatcherInput
    return MatcherInput(requirement_id="T::R1", requirement_text="Turnover at least EGP 2 billion",
                        requirement_category="FINANCIAL", evidence_id="e", evidence_fact=fact,
                        source_document="p.md", page_or_section="p.1", current_tender_id="T")


def test_judge_grounded_fail_with_high_confidence_is_kept():
    out = _judge({"verdict": "FAIL", "confidence": 0.9, "quote": "Average annual turnover over the last three years: EGP 1.2 billion"}).match(_pair())
    assert out.applicability == "FAIL" and out.contradiction and out.contradictory_facts


def test_judge_low_confidence_fail_becomes_review():
    out = _judge({"verdict": "FAIL", "confidence": 0.3, "quote": "Average annual turnover over the last three years"}).match(_pair())
    assert out.applicability == "REVIEW" and "downgraded" in out.reason


def test_judge_invented_quote_never_passes():
    out = _judge({"verdict": "PASS", "confidence": 0.95, "quote": "turnover of EGP 5 billion certified"}).match(_pair())
    assert out.applicability == "REVIEW" and not out.supporting_facts


def test_judge_garbage_reply_is_review_not_crash():
    from app.engines.tender_bridge import EvidenceJudge
    out = EvidenceJudge("stub", transport=lambda s, u: "not json").match(_pair())
    assert out.applicability == "REVIEW" and out.confidence == 0.0


def test_passages_never_cross_sections():
    from app.engines.tender_bridge import _paragraphs
    pages = [{"page_number": 2, "text": "# Legal\nWe are a registered company in Egypt since 1999.\n# Experience\n- 2023: 220 kV GIS substation in successful operation.\n- 2021: 66 kV substation in successful operation."}]
    ps = _paragraphs("c.md", pages)
    assert [p["heading"] for p in ps] == ["Legal", "Experience", "Experience"]
    assert all(p["page"] == 2 for p in ps)
