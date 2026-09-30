"""Stage 6 Task 1 — review-found fixes: real questions only, quoted; more rule cues; email."""
import uuid

import pytest

from app.pipeline.ambiguity import TBD_MARKER
from app.pipeline.rule_category import rule_category


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


def test_tbd_marker_ignores_contract_boilerplate():
    assert TBD_MARKER.search("Bond amount TBD")
    assert TBD_MARKER.search("rating to be confirmed by COMPANY")
    for boiler in ("Data Schedule as applicable", "as required by COMPANY", "if applicable", "table 3", "outbay"):
        assert not TBD_MARKER.search(boiler), boiler


@pytest.mark.parametrize("text,expected", [
    ("Delete in its entirety Paragraph 8.4.4 of this Schedule “A” and replace", "LEGAL"),
    ("All notices between the Parties shall be sufficient when delivered", "LEGAL"),
    ("4.3 Visas for CONTRACTOR’s Expatriate Personnel", "PERSONNEL"),
    ("Rated Duration of Short Circuit", "TECHNICAL"),
    ("HANDLING, DELIVERY AND STORAGE", "TECHNICAL"),
    ("Drive & personnel gates drawing", "TECHNICAL"),
])
def test_new_rule_cues(text, expected):
    assert rule_category(text) == expected


def _analysis(tid, reqs, ambiguities):
    from app.models import TenderAnalysis
    return TenderAnalysis(id=f"AN-{uuid.uuid4().hex[:8]}", tender_id=tid, analysis_version="t", status="COMPLETED",
                          tender={}, evidence=[], documents=[], deadlines=[], commercial=None, risks=[],
                          requirements=reqs, derived_features={"ambiguities": ambiguities})


def test_questions_quote_the_requirement_and_skip_model_doubts():
    from app.database import SessionLocal
    from app.issues import build_candidates
    from app.models import Tender
    tid = f"Q6-{uuid.uuid4().hex[:6]}"
    reqs = [{"requirement_id": "R1", "summary": "bond", "category": "COMMERCIAL", "source_document": "RFP.pdf",
             "page_number": 4, "source_text": "The performance bond amount is TBD by the COMPANY."},
            {"requirement_id": "R2", "summary": "data", "category": "TECHNICAL", "source_document": "RFP.pdf",
             "page_number": 9, "source_text": "Data Schedule as applicable."},
            {"requirement_id": "R3", "summary": "x", "category": "TECHNICAL", "source_document": "RFP.pdf",
             "page_number": 2, "source_text": "Contractor shall install the GIS."}]
    sig = lambda t, rid: {"ambiguity_type": t, "source_document": "RFP.pdf", "description": "internal",
                          "raw_signals": [{"requirement_id": rid}]}
    db = SessionLocal()
    try:
        db.add(Tender(id=tid, title="t"))
        db.add(_analysis(tid, reqs, [sig("missing-value", "R1"), sig("missing-value", "R2"),
                                     sig("unclear-applicability", "R3"), sig("undefined-term", "R3")]))
        db.commit()
        qs = [c for c in build_candidates(db, tid) if c["category"] == "question"]
        assert len(qs) == 1
        assert qs[0]["detail"] == "The performance bond amount is TBD by the COMPANY."
        assert qs[0]["page"] == "4" and qs[0]["source_document"] == "RFP.pdf"
        assert "internal" not in qs[0]["detail"]
    finally:
        db.close()


def test_email_skips_internal_review_lists():
    from app.api.routes import _EMAIL_SKIP
    assert {"unclassified-requirement", "evidence-missing", "ineligible"} <= _EMAIL_SKIP
