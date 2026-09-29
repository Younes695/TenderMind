"""Stage 6 Task 4 — RFP sections with page ranges and past suppliers per discipline."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.pipeline.contracts import SourceText
from app.sections import _HEAD, discipline_of, split_sections


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


def _pages(doc, texts):
    return [SourceText(source_document=doc, page_number=i + 1, text=t) for i, t in enumerate(texts)]


def test_headings_split_with_page_ranges_and_toc_ignored():
    pages = _pages("SOW.pdf", [
        "CONTENTS\nSECTION 1 - GENERAL ........ 3\nSECTION 2 - GIS ........ 5",   # table of contents
        "Project introduction and scope.",
        "SECTION 1 - GENERAL\nThe works include the substation.",
        "More general text.",
        "SECTION 2 - GIS SWITCHGEAR\n132 kV GIS with circuit breaker and disconnector.",
        "APPENDIX-VII FOR CIVIL AND STRUCTURAL DESIGN CRITERIA\nconcrete foundation excavation",
    ])
    secs = split_sections(pages)
    assert [(s["title"][:12], s["page_from"], s["page_to"]) for s in secs] == [
        ("Front matter", 1, 2), ("SECTION 1 - ", 3, 4), ("SECTION 2 - ", 5, 5), ("APPENDIX-VII", 6, 6)]
    assert secs[2]["discipline"] == "Primary electrical (GIS / transformers)"
    assert secs[3]["discipline"] == "Civil & structural"


def test_table_headers_and_drawing_cuts_are_not_headings():
    for t in ("SECTION NO. DESCRIPTION 'A' 3 0", "Section modulus for two side rails", "SECTION C-C 2",
              "SECTIONS & DETAILS"):
        assert not _HEAD.match(t), t
    for t in ("SECTION 3 - GIS", "APPENDIX - II", "ATTACHMENT – II", "Schedule “A” – Appendix II"):
        assert _HEAD.match(t), t


def test_document_without_headings_is_one_section():
    secs = split_sections(_pages("Bid Form.doc", ["Prices and payment schedule", "bond"]))
    assert len(secs) == 1 and secs[0]["page_from"] == 1 and secs[0]["page_to"] == 2
    assert secs[0]["discipline"] == "Commercial"


def test_discipline_tagging():
    assert discipline_of("HVAC system for control building") == "HVAC"
    assert discipline_of("Fire alarm and detection") == "Fire protection"
    assert discipline_of("OPGW and SCADA interface") == "SCADA & telecom"
    assert discipline_of("Miscellaneous") == "General"


def test_suppliers_ranked_and_scoped_to_the_account():
    from app.database import SessionLocal
    from app.models import Quotation, Rfq, Tender
    from app.sections import suppliers_by_discipline
    db = SessionLocal()
    mine, other = f"S-{uuid.uuid4().hex[:6]}", f"S-{uuid.uuid4().hex[:6]}"
    try:
        db.add_all([Tender(id=mine, title="old"), Tender(id=other, title="someone else's")])
        r1 = Rfq(id=f"R-{uuid.uuid4().hex[:6]}", tender_id=mine, reference="RFQ-1", package_name="HVAC package",
                 discipline="HVAC")
        r2 = Rfq(id=f"R-{uuid.uuid4().hex[:6]}", tender_id=other, reference="RFQ-2", package_name="HVAC",
                 discipline="HVAC")
        db.add_all([r1, r2])
        q = lambda rfq, name, fit, sel: Quotation(id=f"Q-{uuid.uuid4().hex[:6]}", rfq_id=rfq.id, contractor=name,
                                                  price=1, duration_weeks=1, technical_fit=fit,
                                                  payment_terms_days=30, selected=sel)
        db.add_all([q(r1, "Cool Air Co", 70, False), q(r1, "Gulf HVAC", 90, False),
                    q(r1, "cool air co ", 80, True), q(r2, "Hidden Ltd", 99, True)])
        db.commit()
        res = suppliers_by_discipline(db, [mine])["HVAC"]
        assert [s["contractor"] for s in res] == ["Cool Air Co", "Gulf HVAC"]
        assert res[0]["selected"] == 1 and res[0]["quotes"] == 2 and res[0]["avg_fit"] == 75.0
        assert all(s["contractor"] != "Hidden Ltd" for s in res)
    finally:
        db.close()


def test_sections_endpoint(monkeypatch):
    from app import sections
    from app.main import app
    monkeypatch.setattr(sections, "sources_from_cache",
                        lambda tid: _pages("SOW.pdf", ["SECTION 1 - GENERAL\nhvac chiller", "x"]))
    c = TestClient(app)
    tid = f"S-{uuid.uuid4().hex[:6]}"
    c.post("/api/tenders", json={"id": tid, "title": "x"})
    body = c.get(f"/api/tenders/{tid}/sections").json()
    assert body["sections"][0]["page_to"] == 2 and body["disciplines"][0]["pages"] == 2
    assert c.get("/api/tenders/NOPE-XYZ/sections").status_code == 404
