"""Stage 6 Task 6 — Go/No-Go score from four weighted factors."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.scoring import (DEFAULT_WEIGHTS, band, clean_weights, compute, fit_factor, history_factor,
                         partners_factor, votes_factor)


@pytest.fixture(autouse=True, scope="module")
def _db_ready():
    from app.database import init_db
    init_db()


F = lambda v: {"value": v, "reason": "r"}


def test_weighted_mean_of_all_factors():
    r = compute({"fit": F(80), "history": F(50), "partners": F(100), "votes": F(60)}, dict(DEFAULT_WEIGHTS))
    assert r["score"] == round((40 * 80 + 20 * 50 + 15 * 100 + 25 * 60) / 100)  # 72
    assert r["band"] == "GO" and r["not_counted"] == []


def test_missing_factor_is_not_counted_and_weights_rescale():
    r = compute({"fit": F(80), "history": F(None), "partners": F(None), "votes": F(40)}, dict(DEFAULT_WEIGHTS))
    assert r["score"] == round((40 * 80 + 25 * 40) / 65)  # 65
    assert r["band"] == "REVIEW"
    assert r["not_counted"] == ["Similar past tenders", "Past partners"]
    fit = next(f for f in r["factors"] if f["key"] == "fit")
    assert fit["effective_weight"] == 62


def test_no_data_gives_no_score_and_no_division_by_zero():
    r = compute({k: F(None) for k in DEFAULT_WEIGHTS}, dict(DEFAULT_WEIGHTS))
    assert r["score"] is None and r["band"] is None


def test_hard_fail_forces_no_go_even_with_high_score():
    r = compute({k: F(95) for k in DEFAULT_WEIGHTS}, dict(DEFAULT_WEIGHTS), hard_fail="1 mandatory requirement")
    assert r["score"] == 95 and r["band"] == "NO_GO"


def test_band_boundaries_and_weight_cleaning():
    assert (band(70), band(69.6), band(69), band(50), band(49)) == ("GO", "GO", "REVIEW", "REVIEW", "NO_GO")
    assert clean_weights({"fit": "x", "votes": 250, "history": -3}) == {"fit": 40, "history": 0, "partners": 15,
                                                                        "votes": 100}
    assert clean_weights({"fit": 0, "history": 0, "partners": 0, "votes": 0}) == DEFAULT_WEIGHTS


def test_factor_builders():
    assert fit_factor(64, [])["value"] == 64
    checks = [{"result": "PASS"}, {"result": "FAIL"}, {"result": "UNCLEAR"}, {"result": "PASS"}]
    assert round(fit_factor(None, checks)["value"]) == 67
    assert fit_factor(None, [{"result": "UNCLEAR"}])["value"] is None
    past = [{"kind": "substation", "outcome": "WON"}, {"kind": "substation", "outcome": "LOST"},
            {"kind": "substation", "outcome": "SUBMITTED"}, {"kind": "cable", "outcome": "WON"}]
    h = history_factor("substation", past)
    assert h["value"] == 50 and "1 of 2" in h["reason"]
    assert history_factor("overhead line", past)["value"] is None
    p = partners_factor(["HVAC", "Civil & structural", "Commercial", "HVAC"], {"HVAC": [{"contractor": "x"}]})
    assert p["value"] == 50 and "Civil & structural" in p["reason"]
    assert partners_factor(["Commercial"], {"HVAC": [1]})["value"] is None
    assert partners_factor(["HVAC"], {})["value"] is None
    assert votes_factor({"overall": {"approve": 3, "reject": 1, "abstain": 0, "approve_pct": 75}})["value"] == 75
    assert votes_factor({"overall": {"approve_pct": None}})["value"] is None


def test_score_and_weights_endpoints():
    from app.main import app
    c = TestClient(app)
    assert c.put("/api/score-weights", json={"fit": 50, "history": 10, "partners": 10, "votes": 30}).status_code == 200
    assert c.get("/api/score-weights").json()["fit"] == 50
    assert c.put("/api/score-weights", json={"luck": 5}).status_code == 422
    assert c.put("/api/score-weights", json={"fit": 0, "history": 0, "partners": 0, "votes": 0}).status_code == 422
    tid = f"SC-{uuid.uuid4().hex[:6]}"
    c.post("/api/tenders", json={"id": tid, "title": "Riyadh 132kV Substation"})
    c.put(f"/api/tenders/{tid}/votes", json={"member_name": "A", "department": "Finance", "vote": "APPROVE"})
    c.put(f"/api/tenders/{tid}/votes", json={"member_name": "B", "department": "Legal", "vote": "REJECT"})
    s = c.get(f"/api/tenders/{tid}/score").json()
    votes = next(f for f in s["factors"] if f["key"] == "votes")
    assert votes["value"] == 50 and votes["counted"]
    assert s["score"] is not None and s["band"] in ("GO", "REVIEW", "NO_GO")
    rec = c.get(f"/api/tenders/{tid}/recommendation").json()
    assert "score" in rec and rec["score"]["factors"]
    c.put("/api/score-weights", json=DEFAULT_WEIGHTS)
