"""Stage 6 — Go/No-Go score out of 100.

Four factors, each 0-100, weighted (default 40/20/15/25, editable per account):
  fit       — company match: mandatory requirements met with evidence; before the
              tender is evaluated, the share of eligibility checks passed
  history   — similar past tenders of the same work type: won / (won + lost)
  partners  — technical parts of this RFP that a past supplier/subcontractor covers
  votes     — department votes: approve / (approve + reject)
A factor without data is not counted and the other weights are rescaled; the
result says which. Bands: GO >= 70, REVIEW 50-69, NO_GO < 50. A mandatory
requirement the company fails (hard gate) or an eligibility block that was not
overridden forces NO_GO whatever the score.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_WEIGHTS = {"fit": 40, "history": 20, "partners": 15, "votes": 25}
LABELS = {"fit": "Company fit", "history": "Similar past tenders", "partners": "Past partners",
          "votes": "Department votes"}
GO, REVIEW = 70, 50
NON_TECHNICAL = {"Commercial", "Legal / contract terms", "HSE", "Quality", "General"}


def clean_weights(w: Optional[Dict[str, Any]]) -> Dict[str, float]:
    out = {}
    for k, d in DEFAULT_WEIGHTS.items():
        try:
            v = float((w or {}).get(k, d))
        except (TypeError, ValueError):
            v = d
        out[k] = min(max(v, 0.0), 100.0)
    return out if sum(out.values()) > 0 else dict(DEFAULT_WEIGHTS)


def band(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    score = round(score)  # the band always matches the number shown
    return "GO" if score >= GO else "REVIEW" if score >= REVIEW else "NO_GO"


def compute(factors: Dict[str, Dict[str, Any]], weights: Dict[str, float], hard_fail: Optional[str] = None
            ) -> Dict[str, Any]:
    """factors: {key: {"value": 0-100 | None, "reason": str}}."""
    rows, total_w, acc = [], 0.0, 0.0
    for k in DEFAULT_WEIGHTS:
        f = factors.get(k) or {}
        v = f.get("value")
        counted = v is not None and weights.get(k, 0) > 0
        rows.append({"key": k, "label": LABELS[k], "value": None if v is None else round(float(v)),
                     "weight": weights.get(k, 0), "counted": counted, "reason": f.get("reason")})
        if counted:
            total_w += weights[k]
            acc += weights[k] * float(v)
    score = round(acc / total_w) if total_w else None
    for r in rows:
        r["effective_weight"] = round(100 * r["weight"] / total_w) if r["counted"] and total_w else 0
    b = band(score)
    if hard_fail:
        b = "NO_GO"
    return {"score": score, "band": b, "hard_fail": hard_fail, "factors": rows,
            "not_counted": [r["label"] for r in rows if not r["counted"]]}


# ---- factor builders (each returns {"value", "reason"})
def fit_factor(match_percent: Optional[float], eligibility_checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if match_percent is not None:
        return {"value": match_percent, "reason": "Mandatory requirements met with evidence."}
    decided = [c for c in eligibility_checks or [] if c.get("result") in ("PASS", "FAIL")]
    if decided:
        ok = sum(1 for c in decided if c["result"] == "PASS")
        return {"value": 100 * ok / len(decided),
                "reason": f"Not evaluated yet — {ok} of {len(decided)} eligibility checks passed."}
    return {"value": None, "reason": "No evaluation or eligibility check yet."}


def history_factor(kind: Optional[str], past: List[Dict[str, Any]]) -> Dict[str, Any]:
    """past: [{"kind", "outcome"}] of the account's other tenders."""
    same = [p for p in past if kind and p.get("kind") == kind and p.get("outcome") in ("WON", "LOST")]
    if not same:
        return {"value": None, "reason": "No won/lost tenders of the same type recorded yet."
                if kind else "Tender type not recognised."}
    won = sum(1 for p in same if p["outcome"] == "WON")
    return {"value": 100 * won / len(same), "reason": f"Won {won} of {len(same)} past {kind} tenders."}


def partners_factor(disciplines: List[str], suppliers: Dict[str, List[Any]]) -> Dict[str, Any]:
    tech = sorted({d for d in disciplines if d not in NON_TECHNICAL})
    if not tech:
        return {"value": None, "reason": "No technical parts identified in the RFP yet."}
    if not suppliers:
        return {"value": None, "reason": "No past quotations recorded yet."}
    covered = [d for d in tech if suppliers.get(d)]
    missing = [d for d in tech if d not in covered]
    return {"value": 100 * len(covered) / len(tech),
            "reason": f"{len(covered)} of {len(tech)} technical parts have a past supplier"
                      + (f"; none yet for: {', '.join(missing)}." if missing else ".")}


def votes_factor(summary: Dict[str, Any]) -> Dict[str, Any]:
    o = (summary or {}).get("overall") or {}
    if o.get("approve_pct") is None:
        return {"value": None, "reason": "No department votes yet."}
    return {"value": o["approve_pct"],
            "reason": f"{o['approve']} approve, {o['reject']} reject, {o['abstain']} abstain."}


def tender_score(db, tender, user, match_percent: Optional[float], hard_fail_count: int = 0) -> Dict[str, Any]:
    """Collects the four factors for one tender of the account and computes the score."""
    from app.access import owner_filter
    from app.models import DepartmentVote, EligibilityResult, ScoreSettings, Tender
    from app.sections import suppliers_by_discipline, tender_sections
    from app.team import vote_summary
    from app.tender_facts import classify_kind

    el = db.query(EligibilityResult).filter(EligibilityResult.tender_id == tender.id).first()
    checks = (el.checks or []) if el else []
    kind = classify_kind(f"{tender.title or ''} {tender.id}")
    q = db.query(Tender).filter(Tender.id != tender.id)
    f = owner_filter(Tender.owner_email, user)
    if f is not None:
        q = q.filter(f)
    others = q.all()
    past = [{"kind": classify_kind(f"{t.title or ''} {t.id}"), "outcome": t.outcome} for t in others]
    try:
        disciplines = [s["discipline"] for s in tender_sections(tender.id)]
    except Exception:
        disciplines = []
    suppliers = suppliers_by_discipline(db, [t.id for t in others])
    votes = [{"department": v.department, "vote": v.vote}
             for v in db.query(DepartmentVote).filter(DepartmentVote.tender_id == tender.id).all()]
    key = user.get("email") if not user.get("auth_disabled") else "local"
    st = db.query(ScoreSettings).filter(ScoreSettings.id == key).first()
    hard = None
    if hard_fail_count:
        hard = f"{hard_fail_count} mandatory requirement(s) contradicted by your documents."
    elif el is not None and el.status == "INELIGIBLE" and not el.override_by:
        hard = "Blocked by the eligibility check."
    return compute({"fit": fit_factor(match_percent, checks), "history": history_factor(kind, past),
                    "partners": partners_factor(disciplines, suppliers), "votes": votes_factor(vote_summary(votes))},
                   clean_weights(st.weights if st else None), hard)
