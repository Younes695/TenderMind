"""Stage 8 — summary, similar tenders & client history, stage/deadline/notes, reminders, dashboard, assistant."""
import uuid
from collections import Counter
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.pipeline.contracts import SourceText


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


def _c():
    from app.main import app
    return TestClient(app)


def S(doc, page, text):
    return SourceText(source_document=doc, page_number=page, text=text)


def test_key_dates_day_first_and_client_detection():
    from app.summary import key_dates, to_iso
    from app.tender_facts import detect_client, normalise_client
    src = [S("Invite.pdf", 1, "The Job Explanation Meeting is scheduled as follows:\nDate  : 17.01.2024\n"
                              "All bids must be submitted to the Saudi Electricity Company, as follows:\nDate : 12.02.2024")]
    d = {x["label"]: x for x in key_dates(src)}
    assert d["Submission deadline"]["date"] == "2024-02-12" and d["Submission deadline"]["page"] == 1
    assert d["Pre-bid / job explanation meeting"]["date"] == "2024-01-17"
    assert to_iso("03.04.2025") == "2025-04-03" and to_iso("nonsense") is None
    name, ev = detect_client(src)
    assert name == "Saudi Electricity Company (SEC)" and ev["file"] == "Invite.pdf"
    assert detect_client(src, "Acme Power")[0] == "Acme Power"  # the team's entry wins
    assert normalise_client("SEC ") == normalise_client("Saudi Electricity Company")


def test_similarity_ranking_and_reasons():
    from app.similarity import rank
    base = {"client_key": "sec", "client": "SEC", "work_type": "substation", "kv": 132, "country": "Saudi Arabia",
            "terms": Counter({"gis": 5, "transformer": 3, "busbar": 2}), "analysed": True}
    near = dict(base, id="A", title="a", decision="REVIEW", outcome="WON", created_at=None)
    far = dict(base, id="B", title="b", client_key="x", client="X", work_type="cable", kv=11, country="Egypt",
               terms=Counter({"trench": 4}), decision=None, outcome=None, created_at=None)
    res = rank(dict(base, id="T"), [far, near])
    assert [r["id"] for r in res] == ["A"]
    assert res[0]["score"] >= 90
    assert {x["key"] for x in res[0]["reasons"]} >= {"Same client: {client}", "Same type of work: {kind}"}


def _tender(c, title, client=None, outcome=None):
    tid = f"S8-{uuid.uuid4().hex[:6]}"
    c.post("/api/tenders", json={"id": tid, "title": title, "client": client})
    if outcome:
        c.put(f"/api/tenders/{tid}/outcome", json={"outcome": outcome})
    return tid


def test_client_history_notification_and_history_factor():
    c = _c()
    old = _tender(c, "Riyadh 132kV Substation", "Saudi Electricity Company", "WON")
    new = _tender(c, "Jeddah 132kV Substation", "SEC")
    sim = c.get(f"/api/tenders/{new}/similar").json()
    assert sim["client"] == "Saudi Electricity Company (SEC)"
    assert any(h["id"] == old for h in sim["client_history"])
    notes = c.get("/api/notifications").json()["notifications"]
    assert any(n["tender_id"] == new and n["kind"] == "client-history" for n in notes)
    score = c.get(f"/api/tenders/{new}/score").json()
    hist = next(f for f in score["factors"] if f["key"] == "history")
    assert hist["counted"] and hist["reason_key"] == "Won {won} of {n} past tenders with {client}."


def test_plan_notes_audit_and_reminders():
    c = _c()
    tid = _tender(c, "Plan test substation")
    soon = (date.today() + timedelta(days=2)).isoformat()
    past = (date.today() - timedelta(days=1)).isoformat()
    r = c.put(f"/api/tenders/{tid}/plan", json={"stage": "pricing", "submission_deadline": soon}).json()
    assert r == {"stage": "PRICING", "submission_deadline": soon}
    assert c.put(f"/api/tenders/{tid}/plan", json={"stage": "dreaming"}).status_code == 422
    c.post(f"/api/tenders/{tid}/tasks", json={"title": "Get bond", "due_date": past, "assignee": "Sara"})
    n = c.post(f"/api/tenders/{tid}/notes", json={"author": "Omar", "text": "Client prefers GIS from list A"}).json()
    assert c.post(f"/api/tenders/{tid}/notes", json={"text": " "}).status_code == 422
    assert c.get(f"/api/tenders/{tid}/notes").json()[0]["text"].startswith("Client prefers")
    rem = [x for x in c.get("/api/reminders").json() if x["tender_id"] == tid]
    kinds = {x["kind"] for x in rem}
    assert {"deadline-soon", "task-overdue"} <= kinds
    assert next(x for x in rem if x["kind"] == "deadline-soon")["priority"] == "HIGH"
    c.put(f"/api/tenders/{tid}/plan", json={"stage": "SUBMITTED"})
    assert not [x for x in c.get("/api/reminders").json() if x["tender_id"] == tid]  # closed stages stay quiet
    assert c.delete(f"/api/tenders/{tid}/notes/{n['id']}").status_code == 200
    audit = c.get(f"/api/tenders/{tid}/decision-pack").json()["audit"]
    assert {"stage_set", "deadline_set", "note_added", "note_deleted"} <= {e["action"] for e in audit}


def test_dashboard_attention_shape():
    body = _c().get("/api/dashboard/attention").json()
    assert set(body) >= {"reminders", "awaiting_decision", "blocked", "client_history", "stages", "total"}


def test_assistant_intents_and_search():
    from app.assistant import intent_of
    assert intent_of("What tasks are overdue?") == "overdue"
    assert intent_of("ليه التوصية راجع؟") == "why"
    assert intent_of("هل المناقصة دي مناسبة لينا؟") == "suitable"
    assert intent_of("Did we work with this client before?") == "client"
    assert intent_of("محتاجين شريك؟") == "certificates"
    assert intent_of("Which active tenders require the same materials?") == "bulk"
    assert intent_of("what is the warranty period") == "search"
    c = _c()
    assert c.post("/api/assistant/ask", json={"question": ""}).status_code == 422
    r = c.post("/api/assistant/ask", json={"question": "What tasks are overdue?"}).json()
    assert r["intent"] == "overdue" and r["lines"]
    assert c.post("/api/assistant/ask", json={"question": "why", "tender_id": "NOPE-XYZ"}).status_code == 404


def test_review_fixes_intents_arabic_terms_demo_and_formula_cells():
    from app.assistant import _query_terms, intent_of
    assert intent_of("What is the penalty for late delivery?") == "search"   # not "overdue tasks"
    assert intent_of("What materials are required for the cable?") == "search"
    assert intent_of("Why is the recommendation No-Go?") == "why"
    words, _ = _query_terms("ما مدة الضمان؟")
    assert "الضمان" in words                                                  # Arabic questions are searchable
    from app.database import SessionLocal
    from app.models import Tender
    from app.similarity import client_history
    db = SessionLocal()
    try:
        demo = db.get(Tender, "SA-2018-HV2") or Tender(id="SA-2018-HV2", title="demo", client="MNHD")
        assert client_history(db, demo) == ([], None)                          # demo never lists anyone's tenders
    finally:
        db.close()
