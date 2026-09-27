"""Per-account data isolation.

Every tender and company document belongs to the account that created it
(`owner_email`). Other accounts get 404 — existence is not revealed.

- Auth disabled (local development): single user, everything is visible.
- The seeded demo tender is readable by every signed-in account; only the
  env admin (TENDERMIND_AUTH_EMAIL) may change it.
- Rows created before ownership existed (owner_email NULL) belong to the env
  admin only, so an upgrade never exposes old data to new sign-ups.
"""
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth import _configured_email, require_auth
from app.database import get_db

DEMO_TENDER_ID = "SA-2018-HV2"
DEMO_COMPANY_ID = "HYOSUNG_GIZA"
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def owner_for_new_rows(user: dict) -> Optional[str]:
    """owner_email stamped on new rows (None when auth is off)."""
    if user.get("auth_disabled"):
        return None
    return user["email"]


def is_admin(user: dict) -> bool:
    admin = _configured_email()
    return bool(admin) and user.get("email") == admin


def owns(owner_email: Optional[str], user: dict) -> bool:
    if user.get("auth_disabled"):
        return True
    if owner_email is None:
        return is_admin(user)
    return owner_email == user.get("email")


def can_read_tender(tender, user: dict) -> bool:
    return tender.id == DEMO_TENDER_ID or owns(tender.owner_email, user)


def can_write_tender(tender, user: dict) -> bool:
    return owns(tender.owner_email, user)


def owner_filter(column, user: dict):
    """SQLAlchemy filter for rows this account owns (None = no filter)."""
    if user.get("auth_disabled"):
        return None
    if is_admin(user):
        return (column == user["email"]) | column.is_(None)
    return column == user["email"]


def enforce_tender_access(request: Request, user: dict = Depends(require_auth),
                          db: Session = Depends(get_db)) -> None:
    """Router-level guard for every route with a {tender_id} path parameter.

    A missing tender is left to the route (its own 404); a tender the account
    cannot see is reported as the same 404.
    """
    tender_id = request.path_params.get("tender_id")
    if tender_id is None:
        return
    from app.models import Tender
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None:
        return
    if not can_read_tender(tender, user):
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    if request.method in _WRITE_METHODS and not can_write_tender(tender, user):
        raise HTTPException(status_code=403, detail="The demo tender is read-only for your account")


def tender_owner_or_404(db: Session, tender_id: str, user: dict):
    from app.models import Tender
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if tender is None or not can_read_tender(tender, user):
        raise HTTPException(status_code=404, detail=f"Tender {tender_id} not found")
    return tender

