"""Stage 7 — audit trail of team actions on a tender (best-effort: never breaks the action)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


def log(db, tender_id: str, action: str, detail: Optional[Dict[str, Any]] = None, user: Optional[dict] = None,
        name: Optional[str] = None) -> None:
    from app.models import AuditEvent
    try:
        actor = (user or {}).get("email") if user and not user.get("auth_disabled") else "local"
        db.add(AuditEvent(id=f"AE-{uuid.uuid4().hex[:10].upper()}", tender_id=tender_id, action=action,
                          detail=detail or {}, actor=actor, actor_name=(name or None), at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()


def events(db, tender_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    from app.models import AuditEvent, DecisionAudit
    rows = (db.query(AuditEvent).filter(AuditEvent.tender_id == tender_id)
            .order_by(AuditEvent.at.desc()).limit(limit).all())
    out = [{"action": e.action, "detail": e.detail or {}, "actor": e.actor, "actor_name": e.actor_name,
            "at": e.at.isoformat() if e.at else None} for e in rows]
    try:  # decision overrides live in DecisionAudit (linked through the decision)
        from app.models import Decision
        rows = (db.query(DecisionAudit, Decision).join(Decision, DecisionAudit.decision_id == Decision.id)
                .filter(Decision.tender_id == tender_id).all())
        for d, _dec in rows:
            out.append({"action": "decision_override",
                        "detail": {"previous": d.previous_decision, "new": d.new_decision, "reason": d.reason},
                        "actor": d.reviewer, "actor_name": None,
                        "at": d.timestamp.isoformat() if d.timestamp else None})
    except Exception:
        db.rollback()
    out.sort(key=lambda e: e["at"] or "", reverse=True)
    return out
