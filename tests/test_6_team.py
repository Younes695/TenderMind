"""Stage 6 Task 5 — shared-login team, tasks with similar-task groups, department votes, outcome."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.team import similar_groups, vote_summary


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


def _t(tid, title, status="OPEN"):
    return {"tender_id": tid, "title": title, "status": status, "due_date": None}


def test_similar_tasks_group_across_tenders():
    groups = similar_groups([
        _t("A", "Request HVAC quotation"), _t("B", "Request quotations for HVAC"),
        _t("C", "HVAC quotation"), _t("A", "Prepare bid bond"), _t("B", "Site visit"),
        _t("C", "Request HVAC quotation", status="DONE"),
    ])
    assert len(groups) == 1
    g = groups[0]
    assert g["count"] == 3 and g["tenders"] == ["A", "B", "C"]
    assert similar_groups([_t("A", "Prepare bid bond")]) == []


def test_vote_summary_percentages():
    s = vote_summary([{"department": "Finance", "vote": "APPROVE"}, {"department": "Finance", "vote": "REJECT"},
                      {"department": "Engineering", "vote": "APPROVE"}, {"department": "Legal", "vote": "ABSTAIN"}])
    assert s["overall"] == {"approve": 2, "reject": 1, "abstain": 1, "total": 4, "approve_pct": 67}
    legal = next(d for d in s["by_department"] if d["department"] == "Legal")
    assert legal["approve_pct"] is None  # nobody decided
    assert vote_summary([])["overall"]["approve_pct"] is None


def test_team_tasks_votes_outcome_endpoints():
    from app.main import app
    c = TestClient(app)
    m = c.post("/api/team", json={"name": "Omar Hassan", "department": "Engineering", "role": "Tender manager"}).json()
    assert c.post("/api/team", json={"name": " "}).status_code == 422
    assert any(x["id"] == m["id"] for x in c.get("/api/team").json())
    assert c.put(f"/api/team/{m['id']}", json={"department": "Projects"}).json()["department"] == "Projects"

    tid = f"TM-{uuid.uuid4().hex[:6]}"
    c.post("/api/tenders", json={"id": tid, "title": "x"})
    t = c.post(f"/api/tenders/{tid}/tasks", json={"title": "Request HVAC quotation", "assignee": "Omar Hassan",
                                                  "due_date": "2026-10-15"}).json()
    assert t["status"] == "OPEN" and t["due_date"] == "2026-10-15"
    assert c.post(f"/api/tenders/{tid}/tasks", json={"title": "x", "due_date": "15/10"}).status_code == 422
    assert c.put(f"/api/tenders/{tid}/tasks/{t['id']}", json={"status": "done"}).json()["status"] == "DONE"
    assert c.put(f"/api/tenders/{tid}/tasks/{t['id']}", json={"status": "later"}).status_code == 422

    r = c.put(f"/api/tenders/{tid}/votes", json={"member_name": "Omar Hassan", "department": "Engineering",
                                                 "vote": "approve"}).json()
    r = c.put(f"/api/tenders/{tid}/votes", json={"member_name": "Sara", "department": "Finance",
                                                 "vote": "REJECT", "comment": "cash flow"}).json()
    assert r["summary"]["overall"]["approve_pct"] == 50
    r = c.put(f"/api/tenders/{tid}/votes", json={"member_name": "Sara", "department": "Finance",
                                                 "vote": "APPROVE"}).json()  # changed mind: update, not a 2nd vote
    assert r["summary"]["overall"] == {"approve": 2, "reject": 0, "abstain": 0, "total": 2, "approve_pct": 100}
    assert c.put(f"/api/tenders/{tid}/votes", json={"member_name": "X", "department": "Y",
                                                    "vote": "maybe"}).status_code == 422

    assert c.put(f"/api/tenders/{tid}/outcome", json={"outcome": "won"}).json()["outcome"] == "WON"
    assert c.put(f"/api/tenders/{tid}/outcome", json={"outcome": "great"}).status_code == 422
    assert c.delete(f"/api/team/{m['id']}").status_code == 200


def test_task_groups_endpoint():
    from app.main import app
    c = TestClient(app)
    a, b = f"TG-{uuid.uuid4().hex[:6]}", f"TG-{uuid.uuid4().hex[:6]}"
    for tid in (a, b):
        c.post("/api/tenders", json={"id": tid, "title": "x"})
    c.post(f"/api/tenders/{a}/tasks", json={"title": "Collect SEC vendor certificate zz91"})
    c.post(f"/api/tenders/{b}/tasks", json={"title": "Collect SEC vendor certificates zz91"})
    g = [x for x in c.get("/api/tasks/groups").json() if "zz91" in x["title"]]
    assert len(g) == 1 and set(g[0]["tenders"]) == {a, b}


@pytest.fixture()
def app_auth_on(monkeypatch):
    monkeypatch.setenv("TENDERMIND_AUTH_ENABLED", "1")
    monkeypatch.setenv("TENDERMIND_SIGNUP_ENABLED", "1")
    monkeypatch.setenv("TENDERMIND_AUTH_EMAIL", "admin@tm.test")
    monkeypatch.setenv("TENDERMIND_AUTH_PASSWORD", "Admin2026x")
    from app.main import app
    return app


def _account(app):
    c = TestClient(app, base_url="https://testserver")
    c.__enter__()
    email = f"u-{uuid.uuid4().hex[:8]}@tm.test"
    assert c.post("/api/auth/signup", json={"email": email, "password": "Tender2026"}).status_code == 200
    return c


def test_other_account_cannot_reach_team_tasks_votes_or_capabilities(app_auth_on):
    alice, bob = _account(app_auth_on), _account(app_auth_on)
    tid = f"T-{uuid.uuid4().hex[:8]}"
    assert alice.post("/api/tenders", json={"id": tid, "title": "Private"}).status_code == 200
    m = alice.post("/api/team", json={"name": "Alice PM"}).json()
    task = alice.post(f"/api/tenders/{tid}/tasks", json={"title": "secret"}).json()
    alice.put("/api/company-capability", json={"max_kv": 132})
    assert all(x["id"] != m["id"] for x in bob.get("/api/team").json())
    assert bob.put(f"/api/team/{m['id']}", json={"name": "hijack"}).status_code == 404
    assert bob.delete(f"/api/team/{m['id']}").status_code == 404
    for path in (f"/api/tenders/{tid}/tasks", f"/api/tenders/{tid}/votes", f"/api/tenders/{tid}/sections",
                 f"/api/tenders/{tid}/eligibility"):
        assert bob.get(path).status_code == 404, path
    assert bob.put(f"/api/tenders/{tid}/tasks/{task['id']}", json={"status": "DONE"}).status_code == 404
    assert bob.put(f"/api/tenders/{tid}/votes", json={"member_name": "x", "department": "y",
                                                      "vote": "APPROVE"}).status_code == 404
    assert bob.put(f"/api/tenders/{tid}/outcome", json={"outcome": "LOST"}).status_code == 404
    assert bob.get("/api/company-capability").json()["max_kv"] is None
    assert all(tid not in g["tenders"] for g in bob.get("/api/tasks/groups").json())
