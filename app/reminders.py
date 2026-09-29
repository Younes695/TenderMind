"""Stage 8 — reminders computed live (never stale): submission deadlines, task due dates, and
checklist items still open close to the deadline. Templates + vars for both languages."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

CLOSED_STAGES = {"SUBMITTED", "CLOSED"}


def _days(d: Optional[datetime], today: date) -> Optional[int]:
    return (d.date() - today).days if d else None


def for_tenders(db, tenders, today: Optional[date] = None) -> List[Dict[str, Any]]:
    from app.models import SubmissionItem, TenderTask
    today = today or datetime.utcnow().date()
    out: List[Dict[str, Any]] = []
    for t in tenders:
        if (t.stage in CLOSED_STAGES) or t.outcome in ("WON", "LOST", "NOT_SUBMITTED"):
            continue
        left = _days(t.submission_deadline, today)
        if left is not None:
            if left < 0:
                out.append({"kind": "deadline-passed", "tender_id": t.id, "tender_title": t.title, "priority": "HIGH",
                            "key": "Submission deadline passed {n} day(s) ago", "vars": {"n": -left},
                            "due": t.submission_deadline.date().isoformat()})
            elif left <= 7:
                out.append({"kind": "deadline-soon", "tender_id": t.id, "tender_title": t.title,
                            "priority": "HIGH" if left <= 2 else "MEDIUM",
                            "key": "Submission deadline in {n} day(s)" if left else "Submission deadline is today",
                            "vars": {"n": left}, "due": t.submission_deadline.date().isoformat()})
                try:
                    from app.api.routes import _checklist_items
                    todo = sum(1 for i in _checklist_items(db, t.id) if i.get("status") == "TODO")
                except Exception:
                    todo = 0
                if todo:
                    out.append({"kind": "checklist-open", "tender_id": t.id, "tender_title": t.title, "priority": "HIGH",
                                "key": "{n} submission item(s) not ready yet", "vars": {"n": todo},
                                "due": t.submission_deadline.date().isoformat()})
        for task in db.query(TenderTask).filter(TenderTask.tender_id == t.id, TenderTask.status == "OPEN",
                                                TenderTask.due_date.isnot(None)).all():
            d = _days(task.due_date, today)
            if d < 0:
                out.append({"kind": "task-overdue", "tender_id": t.id, "tender_title": t.title, "priority": "HIGH",
                            "key": "Task overdue by {n} day(s): {task}", "vars": {"n": -d, "task": task.title},
                            "assignee": task.assignee, "due": task.due_date.date().isoformat()})
            elif d <= 3:
                out.append({"kind": "task-due", "tender_id": t.id, "tender_title": t.title, "priority": "MEDIUM",
                            "key": "Task due in {n} day(s): {task}" if d else "Task due today: {task}",
                            "vars": {"n": d, "task": task.title}, "assignee": task.assignee,
                            "due": task.due_date.date().isoformat()})
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    out.sort(key=lambda r: (order[r["priority"]], r["due"] or ""))
    return out
