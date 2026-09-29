"""Stage 7 — certificates / approvals demanded, and from whom (decision pack, first section)."""
from app.certifications import find, summary
from app.pipeline.contracts import SourceText


def _src(*pages):
    return [SourceText(source_document="ITB.pdf", page_number=i + 1, text=t) for i, t in enumerate(pages)]


def _by(items):
    return {(i["name"], i["who"]): i for i in items}


def test_bidder_prequalification_and_subcontract_rule():
    items = find(_src(
        "Only firms or joint ventures prequalified and invited by the COMPANY may submit bids.",
        "Where a contractor is not pre-qualified for portion of works, then such a contractor must sub-contract "
        "such portion to a pre-qualified contractor."), {"registrations": []}, {})
    names = {(i["name"], i["who"], i["status"]) for i in items}
    assert ("Prequalification (invited / approved bidders)", "bidder", "CHECK") in names
    assert ("Pre-qualified subcontractor for the parts you are not pre-qualified in", "partner", "PARTNER_NEEDED") in names
    held = find(_src("Only firms prequalified and invited by the COMPANY may submit bids."),
                {"registrations": ["SEC prequalified contractor"]}, {})
    assert held[0]["status"] == "HELD"


def test_manufacturer_demands_need_a_partner_with_suggestions():
    sup = {"Primary electrical (GIS / transformers)": [{"contractor": "Hyosung", "selected": 2}]}
    items = find(_src("Equipment from the COMPANY list of pre-qualified manufacturers.",
                      "Certified Type (Design) Test Reports shall be submitted."), {}, sup)
    for i in items:
        assert i["who"] == "partner" and i["status"] == "PARTNER_NEEDED"
    assert any(i["suggested"] and i["suggested"][0]["contractor"] == "Hyosung" for i in items)
    assert summary(items)["needs_partner"] is True


def test_iso_on_bidder_is_compared_and_test_standards_ignored():
    items = find(_src("The Bidder shall be certified to ISO 9001 and ISO 45001.",
                      "Viscosity per ISO 3104. Paint tested per ISO 12944."),
                 {"certifications": ["ISO 9001"]}, {})
    st = {i["name"]: i["status"] for i in items}
    assert st == {"ISO 45001": "MISSING", "ISO 9001": "HELD"}
    assert items[0]["name"] == "ISO 45001"  # missing first


def test_staff_certificates_and_optional_flag():
    items = find(_src("All Welders shall possess a valid Certificate of Competency.",
                      "Certificate of small and medium local establishment (SME) issued by Monshaat (if any). "
                      "Local content certificate"), {}, {})
    b = {i["name"]: i for i in items}
    assert b["Certificates of competency for staff (welders, jointers, operators)"]["who"] == "staff"
    assert "Local content certificates of suppliers" in b


def test_no_demands_no_items():
    assert find(_src("The contractor shall install the GIS."), {}, {}) == []
