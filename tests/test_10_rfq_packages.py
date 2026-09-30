"""RFQ packages — one RFQ per equipment package, with the tender's own pages cut out per folder."""
import io
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.pipeline.contracts import SourceText

HEADER = "NATIONAL GRID SA\nTHIS DOCUMENT IS NOT TO BE USED FOR CONSTRUCTION\nPTS-99EN0001\n"
SOW = "PTS SOW.pdf"


def _pages():
    body = {
        1: "1.02 PROJECT BRIEF DESCRIPTION\nNew 132/13.8kV substation for the client.",
        2: "4.02 GIS SWITCHGEAR\nThe 132kV GIS with circuit breakers, disconnectors and earthing switches per 32-TMSS-02 and 32-TMSS-01.",
        3: "The GIS busbar and SF6 monitoring. Circuit breakers shall be tested (32-TMSS-01).",
        4: "4.03 POWER TRANSFORMERS\nTwo 67 MVA power transformers with on-load tap changer per 53-TMSS-01.",
        5: "The power transformer windings and bushings; transformer losses guaranteed.",
        6: "4.05 PROTECTION AND SAS\nProtection relays, IEDs and substation automation system (SAS), bay control.",
        7: "Protection panels and relays, interlock and annunciation per 38-TMSS-05.",
        8: "5.03 CIVIL DESIGN REQUIREMENTS\nConcrete foundations, excavation, fence and drainage.",
        9: "32-TMSS-02, Rev. 02\n6.0 DATA SCHEDULE\nGAS INSULATED SWITCHGEAR 69 kV THROUGH 380 kV\nRated current",
        10: "32-TMSS-02, Rev. 02\n6.0 DATA SCHEDULE\nCircuit breakers ratings",
        11: "32-TMSS-01, Rev. 03\n6.0 DATA SCHEDULE\nMETAL-ENCLOSED AIR INSULATED SWITCHGEAR 11 kV through 34.5 kV\nswitchgear",
        13: "4.04 13.8KV SWITCHGEAR\nMetal-clad 13.8 kV switchgear with vacuum circuit breakers.",
        14: "Civil works include concrete foundations for the GIS building and the fence.",
        12: "Commercial terms and payment. Price schedule and bond.",
    }
    return [SourceText(SOW, n, HEADER + t) for n, t in body.items()] + [
        SourceText("Bid Form - all.doc", 1, "GIS transformer protection bid form price"),
        SourceText("Annex XVI Transformer Losses.xlsx", 1, "Power transformer losses no-load load losses MVA")]


def test_packages_split_by_equipment_with_folders():
    from app.rfq_packages import build
    pk = {p["key"]: p for p in build(_pages())}
    assert {"hv_switchgear", "power_transformer", "protection_sas"} <= set(pk)
    gis = pk["hv_switchgear"]
    assert gis["name"] == "132kV GIS / circuit breakers"
    assert gis["parts"]["scope"][0]["ranges"] == [[2, 3]]
    assert gis["parts"]["schedules"][0]["ranges"] == [[9, 10]]      # the spec's own data schedule
    assert "32-TMSS-02" in gis["specs"]
    # the spec title decides: 32-TMSS-01 is MV air-insulated switchgear, not the GIS
    assert "32-TMSS-01" not in gis["specs"]
    assert pk["mv_switchgear"]["parts"]["schedules"][0]["ranges"] == [[11, 11]]
    tr = pk["power_transformer"]
    assert any(p["document"].endswith(".xlsx") for p in tr["parts"]["schedules"])  # sheets are to be filled
    assert pk["civil"]["parts"]["design"][0]["ranges"] == [[8, 8]]
    docs = {p["document"] for x in pk.values() for part in x["parts"].values() for p in part}
    assert "Bid Form - all.doc" not in docs                          # bidder paperwork is not a supplier scope
    assert gis["brief"] == [{"document": SOW, "page": 1}]


def test_repeated_header_lines_do_not_classify_pages():
    from app.rfq_packages import build
    pages = [SourceText("X.pdf", n, "132kV GIS SUBSTATION PROJECT\nGeneral text about meetings and reports.")
             for n in range(1, 8)]
    assert build(pages) == []


def test_zip_cuts_pdf_pages_into_package_folders(tmp_path):
    import fitz
    from app.rfq_packages import build, build_zip
    pdf = tmp_path / "sow.pdf"
    d = fitz.open()
    for n in range(1, 13):
        d.new_page().insert_text((72, 72), f"page {n}")
    d.save(pdf)
    sheet = tmp_path / "losses.xlsx"
    sheet.write_bytes(b"xlsx")
    pk = [p for p in build(_pages()) if p["key"] in ("hv_switchgear", "power_transformer")]
    data = build_zip(pk, {SOW: str(pdf), "Annex XVI Transformer Losses.xlsx": str(sheet)},
                     {"id": "T1", "title": "Test substation", "client": "SEC"}, [], {"name": "Delta Grid"}, "2026-11-01")
    z = zipfile.ZipFile(io.BytesIO(data))
    names = z.namelist()
    assert "01- 132kV GIS _ circuit breakers/1. Project Brief Description/Project brief and RFQ.docx" in names
    scope = z.read("01- 132kV GIS _ circuit breakers/2. Scope of Work/Pages from PTS SOW.pdf")
    cut = fitz.open(stream=scope, filetype="pdf")
    assert [p.get_text().strip() for p in cut] == ["page 2", "page 3"]
    assert "02- Power transformers/5. Data Schedules (to be filled)/Annex XVI Transformer Losses.xlsx" in names


@pytest.fixture(scope="module")
def client():
    from app.database import init_db
    from app.main import app
    init_db()
    return TestClient(app)


def test_endpoints_register_rfqs_once(client, monkeypatch):
    import app.rfq_packages as rp
    monkeypatch.setattr(rp, "tender_packages", lambda tid: rp.build(_pages()))
    tid = f"S10-{uuid.uuid4().hex[:6]}"
    client.post("/api/tenders", json={"id": tid, "title": "Test 132kV", "client": "SEC"})
    pk = client.get(f"/api/tenders/{tid}/rfq-packages").json()["packages"]
    assert pk and all(p["rfq_id"] is None for p in pk)
    r = client.post(f"/api/tenders/{tid}/rfq-packages", json={"keys": ["hv_switchgear"], "closes_at": "2026-11-01"})
    assert r.status_code == 200 and r.json()["created"] == 1
    again = client.post(f"/api/tenders/{tid}/rfq-packages", json={"keys": ["hv_switchgear"]}).json()
    assert again["created"] == 0
    rfqs = client.get("/api/rfqs", params={"tender_id": tid}).json()["rfqs"]
    assert len(rfqs) == 1 and rfqs[0]["package_name"] == "132kV GIS / circuit breakers"
    assert "32-TMSS-02" in rfqs[0]["scope"] and rfqs[0]["closes_at"].startswith("2026-11-01")
    assert client.post(f"/api/tenders/{tid}/rfq-packages", json={"closes_at": "soon"}).status_code == 400
    assert client.get("/api/tenders/NOPE-XYZ/rfq-packages").status_code == 404
