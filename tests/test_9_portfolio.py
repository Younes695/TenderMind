"""Stage 9 — decision board, approvals + final decision, work packages, documents, analytics."""
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


def test_final_decision_flow_and_portfolio_pages():
    from app.main import app
    c = TestClient(app)
    tid = f"S9-{uuid.uuid4().hex[:6]}"
    c.post("/api/tenders", json={"id": tid, "title": "Riyadh 132kV Substation", "client": "SEC"})
    c.put(f"/api/tenders/{tid}/votes", json={"member_name": "Sara", "department": "Finance", "vote": "APPROVE"})
    assert any(r["id"] == tid for r in c.get("/api/portfolio/approvals").json()["waiting"])
    assert c.put(f"/api/tenders/{tid}/final-decision", json={"decision": "GO"}).status_code == 422   # reason required
    assert c.put(f"/api/tenders/{tid}/final-decision", json={"decision": "maybe", "reason": "x"}).status_code == 422
    r = c.put(f"/api/tenders/{tid}/final-decision", json={"decision": "go", "reason": "strategic client", "by": "Omar"}).json()
    assert r["final_decision"] == "GO" and r["stage"] == "PRICING"
    ap = c.get("/api/portfolio/approvals").json()
    assert any(x["id"] == tid and x["final_by"] == "Omar" for x in ap["decided"])
    r = c.put(f"/api/tenders/{tid}/final-decision", json={"decision": "NO_GO", "reason": "no partner"}).json()
    assert r["stage"] == "CLOSED" and r["outcome"] == "NOT_SUBMITTED"
    row = next(x for x in c.get("/api/portfolio/board").json() if x["id"] == tid)
    assert row["final_decision"] == "NO_GO" and row["votes"]["approve"] == 1 and row["client"]
    a = c.get("/api/portfolio/analytics").json()
    assert a["final_decisions"].get("NO_GO", 0) >= 1 and "win_rate" in a
    assert isinstance(c.get("/api/portfolio/work-packages").json(), list)
    d = c.get("/api/portfolio/documents", params={"q": "zzqq-not-there"}).json()
    assert d["hits"] == [] and isinstance(d["files"], list)
    audit = c.get(f"/api/tenders/{tid}/decision-pack").json()["audit"]
    assert sum(1 for e in audit if e["action"] == "final_decision") == 2


def test_ewa_bahrain_table_parsing():
    from app.news import fetch_ewa
    html = ("<h2>Published Domestic Tenders</h2><table><tr><th>Tender Reference No.</th><th>Title</th><th>Description</th>"
            "<th>Directorate</th><th>Published Date</th><th>Closing Date</th></tr>"
            "<tr><td>2026-139-DM-EPD</td><td>Gas Turbine Air Intake Pipes Replacement</td><td>Replace pipes</td>"
            "<td>Electricity Transmission Directorate</td><td>09/09/2026</td><td>27 /09/2026</td></tr></table>"
            "<h2>Tender Opening Results</h2><table><tr><td>2026-077</td><td>Old</td><td>x</td><td>y</td><td>1</td><td>2</td></tr></table>")
    items = fetch_ewa(html_text=html)
    assert len(items) == 1 and items[0]["external_id"] == "2026-139-DM-EPD" and items[0]["country"] == "Bahrain"
    assert items[0]["deadline_at"].strftime("%Y-%m-%d") == "2026-09-27"
