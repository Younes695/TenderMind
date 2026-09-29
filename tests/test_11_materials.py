"""Materials: BOQ lines from the tender's tables, prices only from uploaded supplier lists,
estimated cost, and the same material across active tenders (bulk opportunity)."""
import io
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.pipeline.contracts import SourceText

BOQ_A = ("BILL OF QUANTITIES | | | |\nItem | Description | Unit | Qty | Rate\n"
         "1 | XLPE/SWA/PVC Cu cable 4x16 mm2 0.6/1 kV | m | 12,000 | \n"
         "2 | MCCB 3P 250A 36kA | No | 4 | \n"
         "3 | Excavation for cable trench | m3 | 300 | \n"
         "4 | Cable 4x16 mm2 copper 1 kV | m | 500 | ")
BOQ_B = ("م | البيان | الوحدة | الكمية\n1 | كابل نحاس 4×16 مم2 معزول XLPE مسلح جهد 0.6/1 ك.ف | م.ط | 8000\n"
         "2 | كابل نحاس 4×25 مم2 XLPE | م.ط | 100")


def test_material_keys_merge_only_identical_specs():
    from app.materials import material_attrs, material_key
    k = lambda d, u="m": material_key(material_attrs(d), u)
    assert k("XLPE/SWA/PVC Cu cable 4x16 mm2, 0.6/1 kV") == k("كابل نحاس 4×16 مم2 معزول XLPE مسلح جهد 0.6/1 ك.ف")
    assert k("XLPE Cu cable 4x16 mm2 1kV") != k("XLPE Cu cable 4x25 mm2 1kV")
    assert k("XLPE Cu cable 4x16 mm2 1kV", "m") != k("XLPE Cu cable 4x16 mm2 1kV", "pcs")
    assert k("Excavation for cable trench") is None           # works, not a material
    assert k("Cable, size as per drawings") is None             # main size unknown -> never merged


def test_boq_lines_keep_source_and_normalise_units():
    from app.materials import boq_lines
    lines = boq_lines([SourceText("BOQ.xlsx", 2, BOQ_A), SourceText("جدول الكميات.xlsx", 1, BOQ_B)])
    first = lines[0]
    assert (first["document"], first["page"], first["row"], first["quantity"], first["unit"]) == ("BOQ.xlsx", 2, 3, 12000, "m")
    ar = [l for l in lines if l["document"].startswith("جدول")]
    assert ar[0]["unit"] == "m" and ar[0]["quantity"] == 8000 and ar[0]["key"] == first["key"]
    assert any(l["key"] is None and "Excavation" in l["description"] for l in lines)


def _idx(items):
    from app.materials import price_index
    base = {"supplier": "Nile Cables", "list_id": "L1", "price_date": datetime(2026, 9, 1), "filename": "p.xlsx"}
    return price_index([dict(base, **i) for i in items])


def test_cost_uses_only_listed_prices():
    from app.materials import boq_lines, cost_view, material_attrs, material_key
    key = material_key(material_attrs("Cu XLPE armoured cable 4x16 mm2 1kV"), "m")
    view = cost_view(boq_lines([SourceText("BOQ.xlsx", 1, BOQ_A)]),
                     _idx([{"key": key, "price": 150.0, "currency": "EGP", "unit": "m", "min_qty": 0}]), None)
    priced = [l for l in view["lines"] if l["status"] == "PRICED"]
    assert len(priced) == 1 and priced[0]["cost"] == 1_800_000 and priced[0]["price"]["supplier"] == "Nile Cables"
    assert view["unavailable"] == len(view["lines"]) - 1 and view["totals"] == [{"currency": "EGP", "amount": 1_800_000}]
    assert view["label"] == "ESTIMATE"


def test_aggregate_bulk_and_review():
    from app.materials import aggregate, boq_lines, material_attrs, material_key
    a = boq_lines([SourceText("A.xlsx", 1, BOQ_A)])
    b = boq_lines([SourceText("B.xlsx", 1, BOQ_B)])
    key = material_key(material_attrs("Cu XLPE armoured cable 4x16 mm2 1kV"), "m")
    idx = _idx([{"key": key, "price": 150.0, "currency": "EGP", "unit": "m", "min_qty": 0},
                {"key": key, "price": 140.0, "currency": "EGP", "unit": "m", "min_qty": 15000}])
    res = aggregate({"TA": a, "TB": b}, {"TA": "Tender A", "TB": "Tender B"}, idx)
    bulk = res["bulk"][0]
    assert bulk["total_quantity"] == 20000 and len(bulk["tenders"]) == 2
    assert bulk["estimated_cost"] == 3_000_000
    sc = bulk["bulk_scenario"]
    assert sc["estimated_cost"] == 2_800_000 and sc["difference"] == 200_000 and sc["label"] == "ESTIMATED_SCENARIO"
    # 4x16 without armour/XLPE in tender A vs armoured XLPE in B: same size, different details -> review
    assert any(r["status"] == "REQUIRES_REVIEW" for r in res["review"])
    no_break = aggregate({"TA": a, "TB": b}, {}, _idx([{"key": key, "price": 150.0, "currency": "EGP", "unit": "m", "min_qty": 0}]))
    assert "bulk_scenario" not in no_break["bulk"][0]        # no price break in the list -> no scenario


@pytest.fixture(scope="module")
def client():
    from app.database import init_db
    from app.main import app
    init_db()
    return TestClient(app)


def _xlsx(rows):
    from openpyxl import Workbook
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_price_list_upload_and_tender_endpoints(client, monkeypatch):
    import app.materials as mat
    from app.materials import boq_lines
    monkeypatch.setattr(mat, "tender_boq", lambda tid: boq_lines([SourceText("BOQ.xlsx", 1, BOQ_A if tid.endswith("a") else BOQ_B)]))
    sheet = _xlsx([["Nile Cables price list"], ["Description", "Unit", "Unit Price", "Min Qty"],
                   ["XLPE/SWA Cu cable 4x16 mm2 0.6/1kV", "m", 150, None], ["XLPE/SWA Cu cable 4x16 mm2 0.6/1kV", "m", 140, 15000],
                   ["Note: prices valid 30 days", None, None, None]])
    sup = f"Test Supplier {uuid.uuid4().hex[:4]}"   # the newest list wins, so other lists in the DB don't interfere
    r = client.post("/api/price-lists", data={"supplier": sup, "currency": "egp", "price_date": "2099-01-01"},
                    files={"file": ("nile.xlsx", sheet)})
    assert r.status_code == 200 and r.json()["items"] == 2 and r.json()["recognised"] == 2
    lid = r.json()["id"]
    assert client.post("/api/price-lists", data={"supplier": "X", "currency": "EGP", "price_date": "yesterday"},
                       files={"file": ("x.xlsx", sheet)}).status_code == 400
    assert client.post("/api/price-lists", data={"supplier": "X", "currency": "EGP", "price_date": "2026-09-01"},
                       files={"file": ("x.pdf", b"%PDF")}).status_code == 400
    ta, tb = f"S11-{uuid.uuid4().hex[:5]}a", f"S11-{uuid.uuid4().hex[:5]}b"
    for tid in (ta, tb):
        client.post("/api/tenders", json={"id": tid, "title": f"Demo {tid}"})
    m = client.get(f"/api/tenders/{ta}/materials").json()
    cable = next(l for l in m["lines"] if l["status"] == "PRICED")
    assert cable["price"]["supplier"] == sup and cable["price"]["price_date"] == "2099-01-01"
    agg = client.get("/api/portfolio/materials").json()
    row = next(b for b in agg["bulk"] if {t["tender_id"] for t in b["tenders"]} >= {ta, tb})
    qty = {t["tender_id"]: t["quantity"] for t in row["tenders"]}
    assert qty[ta] == 12000 and qty[tb] == 8000
    assert row["bulk_scenario"]["difference"] == row["total_quantity"] * 10
    assert client.delete(f"/api/price-lists/{lid}").status_code == 200
    m = client.get(f"/api/tenders/{ta}/materials").json()
    assert not any(l["price"] and l["price"]["supplier"] == sup for l in m["lines"])  # list removed -> not used
    for tid in (ta, tb):
        client.delete(f"/api/tenders/{tid}")


def test_radar_match_is_explained_and_never_guessed():
    from datetime import datetime
    from app.radar import match
    cap = {"work_types": ["substation"], "max_kv": 220, "countries": ["Egypt", "Saudi Arabia"]}
    now = datetime(2026, 10, 1)
    item = {"title": "Construction of 132 kV GIS substation", "country": "Saudi Arabia", "deadline_at": "2026-11-01T00:00:00"}
    r = match(item, cap, now)
    assert r["match"] == 100 and r["status"] == "STRONG" and {f["factor"] for f in r["factors"]} == {"work_type", "voltage", "country", "deadline"}
    hv = match(dict(item, title="500 kV substation"), cap, now)
    assert hv["status"] == "WEAK" and any(f["factor"] == "voltage" and f["status"] == "NOT_MET" for f in hv["factors"])
    assert match(item, None, now)["status"] == "INSUFFICIENT_DATA"
    assert match({"title": "Consulting services", "deadline_at": "2026-11-01"}, cap, now)["match"] is None
    close = match(dict(item, deadline_at="2026-10-05T00:00:00"), cap, now)
    assert close["match"] == 88 and any(f["status"] == "PARTIAL" for f in close["factors"])


def test_eligibility_percent_counts_missing_information_as_not_met():
    from app.eligibility import score
    checks = [{"result": "PASS"}, {"result": "PASS"}, {"result": "PASS"}, {"result": "UNCLEAR"}]
    assert score(checks) == {"percent": 75, "met": 3, "failed": 0, "unclear": 1, "total": 4}
    assert score([]) is None
