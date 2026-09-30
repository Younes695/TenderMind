"""Decision engine: mandatory requirements that are not hard gates.

Before: a mandatory QUALIFICATION requirement (COMMERCIAL / HSE / SUBCONTRACTOR
from uploads) that the company's own document contradicted (FAIL) was ignored,
so the tender could come out BID / HIGH; and a missing mandatory SUBCONTRACTOR,
LEGAL or SUBMISSION requirement was skipped by a category list.
Now: a contradiction gives REVIEW (never NO_BID - only bidder-capability gates
do), listed first among the blockers; every mandatory gap counts.
"""
import uuid

import pytest


@pytest.fixture()
def db():
    from app.database import SessionLocal, init_db
    init_db()
    s = SessionLocal()
    yield s
    s.close()


def _tender(db, reqs):
    """reqs: (category, requirement_type, mandatory, evidence_status or None)."""
    from app.models import Evidence, EvidenceMatch, Requirement, Tender
    tid = f"T14-{uuid.uuid4().hex[:8]}"
    db.add(Tender(id=tid, title="Decision rules"))
    for i, (cat, rtype, mandatory, status) in enumerate(reqs):
        rid = f"{tid}::REQ-{i:03d}"
        db.add(Requirement(id=rid, tender_id=tid, category=cat, requirement=f"{cat} requirement {i}",
                           mandatory=mandatory, requirement_type=rtype, applicable_entity="ANY",
                           evidence_required=[], evaluation_logic={}))   # as tender_bridge writes them
        if status:
            eid = f"E-{uuid.uuid4().hex[:10]}"
            db.add(Evidence(id=eid, company_id="OUR_COMPANY", requirement_id=rid, evidence_type="DOCUMENT",
                            fact="company document", status=status, source_document="company.pdf",
                            page_or_section="p.1", source_quote="quoted text", extraction_confidence="HIGH",
                            applicable_entity="ANY"))
            db.add(EvidenceMatch(id=f"M-{eid}", requirement_id=rid, evidence_id=eid, match_confidence="0.9"))
    db.commit()
    return tid


def _decide(db, reqs):
    from app.engines.decision import get_or_create_decision
    dec, _ = get_or_create_decision(db, _tender(db, reqs))
    return dec


GATES_PASS = [("LEGAL", "HARD_GATE", True, "PASS"), ("EXPERIENCE", "HARD_GATE", True, "PASS")]


def test_everything_mandatory_supported_is_bid(db):
    dec = _decide(db, GATES_PASS + [("COMMERCIAL", "QUALIFICATION", True, "PASS")])
    assert (dec.decision, dec.confidence, dec.rules_triggered) == ("BID", "HIGH", ["ALL_MANDATORY_PASS"])


@pytest.mark.parametrize("category", ["COMMERCIAL", "HSE", "SUBCONTRACTOR"])
def test_contradicted_mandatory_requirement_is_review_not_bid(db, category):
    dec = _decide(db, GATES_PASS + [(category, "QUALIFICATION", True, "FAIL")])
    assert dec.decision == "REVIEW" and dec.confidence == "LOW"
    assert dec.rules_triggered == ["MANDATORY_REQUIREMENT_CONTRADICTED"]
    assert dec.hard_fail_count == 0                       # never NO_BID from a non-gate requirement
    assert dec.top_blockers[0] == f"{category} requirement 2 [CONTRADICTED]"


def test_explanation_names_the_contradiction_not_evidence_gaps(db):
    from app.engines.decision import get_or_create_decision
    from app.engines.explanation import build_explanation
    tid = _tender(db, GATES_PASS + [("HSE", "QUALIFICATION", True, "FAIL")])
    dec, status = get_or_create_decision(db, tid)
    summary = build_explanation(db, tid, dec, status)["summary"]
    assert "contradicts a mandatory requirement" in summary and "HSE requirement 2 [CONTRADICTED]" in summary
    assert "evidence gaps" not in summary


def test_contradiction_outranks_gaps_and_is_listed_first(db):
    gaps = [("PERSONNEL", "QUALIFICATION", True, None) for _ in range(7)]
    dec = _decide(db, GATES_PASS + gaps + [("HSE", "QUALIFICATION", True, "FAIL")])
    assert (dec.decision, dec.confidence) == ("REVIEW", "LOW")
    assert dec.rules_triggered == ["MANDATORY_REQUIREMENT_CONTRADICTED"]
    assert dec.contradicted_count == 1
    assert dec.top_blockers[0].endswith("[CONTRADICTED]") and len(dec.top_blockers) == 6


@pytest.mark.parametrize("gap", [None, "REVIEW"])
@pytest.mark.parametrize("category", ["SUBCONTRACTOR", "LEGAL", "SUBMISSION"])
def test_every_mandatory_gap_counts(db, category, gap):
    dec = _decide(db, GATES_PASS + [(category, "QUALIFICATION", True, gap)])
    assert dec.decision == "REVIEW" and dec.rules_triggered == ["EXPERIENCE_EVIDENCE_MISSING"]


def test_hard_gate_fail_still_wins(db):
    dec = _decide(db, [("LEGAL", "HARD_GATE", True, "FAIL"), ("HSE", "QUALIFICATION", True, "FAIL")])
    assert (dec.decision, dec.rules_triggered) == ("NO_BID", ["HARD_GATE_FAIL"])


def test_optional_requirements_still_never_block(db):
    dec = _decide(db, GATES_PASS + [("HSE", "INFORMATIONAL", False, "FAIL"),
                                    ("SUBCONTRACTOR", "INFORMATIONAL", False, None)])
    assert dec.decision == "BID"


# ------------------------------------------------ consumers of the decision
CONTRADICTED = GATES_PASS + [("HSE", "QUALIFICATION", True, "PASS"), ("COMMERCIAL", "QUALIFICATION", True, "FAIL")]
SUPPORTED = GATES_PASS + [("HSE", "QUALIFICATION", True, "PASS"), ("COMMERCIAL", "QUALIFICATION", True, "PASS")]


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    c.__enter__()
    return c


def _override(c, tid, decision):
    # A person overrides seconds after the engine decided; in a test both can land in
    # the same Windows clock tick and tie on timestamp (see test_adversarial.py:311).
    from datetime import timedelta
    from app.database import SessionLocal
    from app.models import Decision
    s = SessionLocal()
    for d in s.query(Decision).filter(Decision.tender_id == tid).all():
        d.timestamp = d.timestamp - timedelta(seconds=1)
    s.commit()
    s.close()
    r = c.post(f"/api/tenders/{tid}/decision/override",
               json={"reviewer": "Eng", "new_decision": decision, "reason": "Reviewed with the commercial team"})
    assert r.status_code == 200


def test_go_no_go_score_is_not_go_while_a_mandatory_requirement_is_contradicted(db):
    from app.engines.decision import get_or_create_decision
    c = _client()
    ok = _tender(db, SUPPORTED)
    get_or_create_decision(db, ok)
    assert c.get(f"/api/tenders/{ok}/score").json()["band"] == "GO"          # control: same tender, all supported
    bad = _tender(db, CONTRADICTED)
    get_or_create_decision(db, bad)
    s = c.get(f"/api/tenders/{bad}/score").json()
    assert s["score"] >= 70 and s["band"] == "REVIEW"                          # 3/4 mandatory supported = 75
    assert s["review"].startswith("1 mandatory requirement(s) contradicted") and s["hard_fail"] is None


@pytest.mark.parametrize("override,band", [("REVIEW", "REVIEW"), ("NO_BID", "REVIEW"), ("BID", "GO")])
def test_only_a_bid_override_lifts_the_cap(db, override, band):
    """A person who reviewed it and decided BID is what the cap waits for; a REVIEW
    or NO_BID override keeps the tender off GO, and the summary keeps the action."""
    from app.engines.decision import get_or_create_decision
    c = _client()
    tid = _tender(db, CONTRADICTED)
    get_or_create_decision(db, tid)
    _override(c, tid, override)
    assert c.get(f"/api/tenders/{tid}/score").json()["band"] == band
    keys = [a["key"] for a in c.get(f"/api/tenders/{tid}/summary").json()["actions"]]
    has_action = any(k.startswith("Resolve {n} mandatory requirement(s)") for k in keys)
    assert has_action == (override != "BID")


def _board_row(db, tid):
    from app.models import Tender
    from app.portfolio import board
    return board(db, {"email": "dev", "auth_disabled": True}, [db.get(Tender, tid)])[0]


def _analysed_with_vote(db, tid):
    from app.models import DepartmentVote, TenderAnalysis
    db.add(TenderAnalysis(id=f"TA-{uuid.uuid4().hex[:8]}", tender_id=tid, requirements=[], documents=[]))
    db.add(DepartmentVote(id=f"V-{uuid.uuid4().hex[:8]}", tender_id=tid, member_name="Eng", department="Tech",
                          vote="APPROVE"))
    db.commit()


def test_decision_board_does_not_say_go_either(db):
    from app.api.routes import _LAST_SCORE
    from app.engines.decision import get_or_create_decision
    tid = _tender(db, CONTRADICTED)
    get_or_create_decision(db, tid)
    _analysed_with_vote(db, tid)
    _LAST_SCORE.pop(tid, None)                                  # cold: the board computes it
    row = _board_row(db, tid)
    assert row["score"] == 100 and row["band"] == "REVIEW"


def test_a_score_shown_before_the_decision_changed_is_not_reused(db):
    """Warm cache: GO was shown, then new evidence contradicts a mandatory requirement."""
    from app.engines.decision import get_or_create_decision
    from app.models import Evidence, Requirement
    c = _client()
    tid = _tender(db, SUPPORTED)
    get_or_create_decision(db, tid)
    _analysed_with_vote(db, tid)
    assert c.get(f"/api/tenders/{tid}/score").json()["band"] == "GO"      # cached for the board/dashboard
    assert _board_row(db, tid)["band"] == "GO"
    commercial = db.query(Requirement).filter(Requirement.tender_id == tid, Requirement.category == "COMMERCIAL").one()
    db.query(Evidence).filter(Evidence.requirement_id == commercial.id).update({Evidence.status: "FAIL"})
    db.commit()
    get_or_create_decision(db, tid)                              # Evaluate again
    assert _board_row(db, tid)["band"] == "REVIEW"


def _saved(db, tid, decision, override, when):
    from app.models import Decision
    db.add(Decision(id=f"DEC-{uuid.uuid4().hex[:8]}", tender_id=tid, decision=decision, confidence="HIGH",
                    timestamp=when, rules_triggered=["ALL_MANDATORY_PASS"], top_blockers=[],
                    is_override=override, engine_version=None))
    db.commit()


def test_decisions_from_the_old_engine_are_recomputed_once_overrides_kept(db):
    from datetime import datetime, timedelta
    from app.engines.decision import ENGINE_VERSION, latest_decision, recompute_stale_decisions
    yesterday = datetime.utcnow() - timedelta(days=1)
    old = _tender(db, CONTRADICTED)
    _saved(db, old, "BID", False, yesterday)                   # what the old rules said
    kept = _tender(db, CONTRADICTED)
    _saved(db, kept, "BID", True, yesterday)                   # a person decided BID
    redone, failed = recompute_stale_decisions(db)
    assert old in redone and kept not in redone and old not in failed
    now = latest_decision(db, old)
    assert now.decision == "REVIEW" and now.engine_version == ENGINE_VERSION and now.contradicted_count == 1
    assert latest_decision(db, kept).is_override and latest_decision(db, kept).decision == "BID"
    assert old not in recompute_stale_decisions(db)[0]         # once


def test_recompute_agrees_with_the_screens_on_timestamp_ties(db):
    """An old computed BID and an override saved in the same clock tick: whichever the
    screens call current, it must not stay an old-engine BID."""
    from datetime import datetime, timedelta
    from app.engines.decision import latest_decision, recompute_stale_decisions
    tid = _tender(db, CONTRADICTED)
    tick = datetime.utcnow() - timedelta(days=1)
    _saved(db, tid, "BID", False, tick)
    _saved(db, tid, "REVIEW", True, tick)
    recompute_stale_decisions(db)
    cur = latest_decision(db, tid)
    assert cur.is_override or cur.engine_version is not None


def test_one_broken_tender_does_not_stop_the_upgrade_of_the_others(db):
    from datetime import datetime, timedelta
    from app.engines.decision import latest_decision, recompute_stale_decisions
    from app.models import Requirement
    yesterday = datetime.utcnow() - timedelta(days=1)
    broken = _tender(db, CONTRADICTED)
    db.query(Requirement).filter(Requirement.tender_id == broken).update({Requirement.evaluation_logic: None})
    db.commit()                                                # status evaluation raises on this tender
    _saved(db, broken, "BID", False, yesterday)
    good = _tender(db, CONTRADICTED)
    _saved(db, good, "BID", False, yesterday)
    redone, failed = recompute_stale_decisions(db)
    assert broken in failed and good in redone
    assert latest_decision(db, good).decision == "REVIEW"


def test_contradiction_review_item_comes_and_goes_with_the_evidence(db):
    from app.engines.decision import get_or_create_decision
    from app.issues import sync_issues
    from app.models import Evidence, Requirement, TenderIssue
    tid = _tender(db, CONTRADICTED)
    get_or_create_decision(db, tid)
    sync_issues(db, tid)
    open_kinds = lambda: [i.kind for i in db.query(TenderIssue).filter(TenderIssue.tender_id == tid,
                                                                       TenderIssue.status == "OPEN").all()]
    assert open_kinds().count("evidence-contradicted") == 1 and "evidence-missing" not in open_kinds()
    actions = _client().get(f"/api/tenders/{tid}/summary").json()["actions"]
    assert any(a["key"].startswith("Resolve {n} mandatory requirement(s) your documents contradict")
               and a["vars"]["n"] == 1 for a in actions)
    # The company uploads the right document: evidence now supports it.
    commercial = db.query(Requirement).filter(Requirement.tender_id == tid, Requirement.category == "COMMERCIAL").one()
    db.query(Evidence).filter(Evidence.requirement_id == commercial.id).update({Evidence.status: "PASS"})
    db.commit()
    get_or_create_decision(db, tid)
    sync_issues(db, tid)
    assert "evidence-contradicted" not in open_kinds()


def test_a_bid_override_retires_the_contradiction_item(db):
    from app.engines.decision import get_or_create_decision
    from app.issues import sync_issues
    from app.models import TenderIssue
    c = _client()
    tid = _tender(db, CONTRADICTED)
    get_or_create_decision(db, tid)
    sync_issues(db, tid)
    _override(c, tid, "BID")
    sync_issues(db, tid)
    kinds = [i.kind for i in db.query(TenderIssue).filter(TenderIssue.tender_id == tid, TenderIssue.status == "OPEN")]
    assert "evidence-contradicted" not in kinds
