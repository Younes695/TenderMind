from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse


# ------------------------------------------------------------------ settings
def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def auth_enabled() -> bool:
    explicit = os.getenv("TENDERMIND_AUTH_ENABLED")
    if explicit is not None:
        return _env_bool("TENDERMIND_AUTH_ENABLED")
    env = os.getenv("TENDERMIND_ENV", "development").strip().lower()
    return env in {"prod", "production"}


def signup_enabled() -> bool:
    return _env_bool("TENDERMIND_SIGNUP_ENABLED", True)


def _configured_email() -> str:
    return os.getenv("TENDERMIND_AUTH_EMAIL", "").strip().lower()


def _configured_password() -> str:
    return os.getenv("TENDERMIND_AUTH_PASSWORD", "")


def _is_reserved(email: str) -> bool:
    """The env admin's address is never a users row: no sign-up, no Google or
    Microsoft sign-in, only the env password (see _principal)."""
    admin = _configured_email()
    return bool(admin) and email == admin


def _session_secret() -> str:
    secret = os.getenv("TENDERMIND_SESSION_SECRET", "").strip()
    env = os.getenv("TENDERMIND_ENV", "development").strip().lower()
    if env in {"prod", "production"} and not secret:
        raise RuntimeError("TENDERMIND_SESSION_SECRET must be configured in production")
    return secret or "tendermind-dev-only-session-secret-change-me"


def cookie_secure() -> bool:
    return _env_bool("TENDERMIND_COOKIE_SECURE", auth_enabled())


def validate_auth_config() -> None:
    """Accounts now live in the users table (sign-up / Google / Microsoft).
    The env admin (TENDERMIND_AUTH_EMAIL + PASSWORD) is optional, but must be
    complete if used."""
    if not auth_enabled():
        return
    if bool(_configured_email()) != bool(_configured_password()):
        raise RuntimeError("Set both TENDERMIND_AUTH_EMAIL and TENDERMIND_AUTH_PASSWORD, or neither")
    pw = _configured_password()
    env = os.getenv("TENDERMIND_ENV", "development").strip().lower()
    if pw and env in {"prod", "production"} and (
            password_problem(pw) or len(pw) < 12 or "change-me" in pw.lower()):
        raise RuntimeError("TENDERMIND_AUTH_PASSWORD is weak or a placeholder: use 12+ characters "
                           "with letters and numbers")
    _session_secret()  # validates production secret


# ------------------------------------------------------------------ passwords
_PBKDF2_ITERATIONS = 310_000
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, stored: Optional[str]) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = (stored or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                     base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(digest, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def password_problem(password: str) -> Optional[str]:
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if len(password) > 256:
        return "Password is too long"
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain letters and numbers"
    return None


def normalize_email(raw) -> str:
    return str(raw or "").strip().lower()[:254]


# ------------------------------------------------------------ rate limiting
# In-process sliding window (the app runs one worker — see run_prod.sh).
_LOGIN_WINDOW_S = 15 * 60
_LOGIN_MAX_FAILURES = 10          # per IP+email
_LOGIN_MAX_FAILURES_PER_IP = 50
_login_failures: dict = {}
_login_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_rate(key: str) -> None:
    import time
    now = time.time()
    limit = _LOGIN_MAX_FAILURES_PER_IP if key.startswith("ip:") else _LOGIN_MAX_FAILURES
    with _login_lock:
        hits = [t for t in _login_failures.get(key, []) if now - t < _LOGIN_WINDOW_S]
        _login_failures[key] = hits
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail="Too many attempts — try again in 15 minutes")


def _record_failure(key: str) -> None:
    import time
    with _login_lock:
        _login_failures.setdefault(key, []).append(time.time())
        if len(_login_failures) > 10_000:  # bound memory under a spray
            for k in list(_login_failures)[:5_000]:
                _login_failures.pop(k, None)


# ------------------------------------------------------------------ sessions
# A session is only as good as the credential that opened it. The cookie is
# signed but stateless, so it carries the account id and the account's
# session_version (users table); a password change or an account takeover bumps
# the version and every cookie opened before it stops working on its next
# request. The env admin has no users row: its version is derived from the
# configured email and password, so rotating that password signs it out too.
# Cookies from before this scheme carry no version and are refused (one forced
# sign-in after the upgrade): an old cookie naming the admin email cannot be
# told apart from one minted through the Microsoft sign-in hole it closes.
def _admin_session_version() -> str:
    material = f"{_configured_email()}\n{_configured_password()}".encode("utf-8")
    return hmac.new(_session_secret().encode("utf-8"), material, hashlib.sha256).hexdigest()[:32]


def _principal(request: Request) -> Optional[dict]:
    """The signed-in account, re-checked against its credential on every request."""
    session = request.session
    if not auth_enabled():
        email = session.get("email") or "dev"
        return {"email": email, "auth_disabled": True,
                "is_admin": bool(_configured_email()) and email == _configured_email()}

    email, kind, version = session.get("email"), session.get("kind"), session.get("sv")
    if not email or version is None:
        return None
    admin = _configured_email()
    if kind == "admin":
        if admin and email == admin and hmac.compare_digest(str(version), _admin_session_version()):
            return {"email": email, "auth_disabled": False, "is_admin": True}
        return None
    if kind != "user" or email == admin:
        return None  # the admin address only ever signs in with the env password

    from app.models import User
    uid = session.get("uid")
    db = _db()
    try:
        row = db.query(User.email, User.session_version).filter(User.id == uid).first()
    finally:
        db.close()
    if row is None or row.email != email or row.session_version != version:
        return None
    return {"email": email, "auth_disabled": False, "is_admin": False, "uid": uid, "sv": version}


def require_auth(request: Request):
    # Checked again here even when app.main._AuthBeforeBody already did before the
    # body: a slow upload must not finish on a session revoked in the meantime.
    principal = _principal(request)
    if principal is None:
        if request.session:
            request.session.clear()  # a revoked or legacy cookie is dropped, not kept around
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def _start_session(request: Request, email: str, name: Optional[str] = None, *,
                   kind: str = "user", uid: Optional[str] = None, version=None) -> dict:
    """kind: 'user' (users row uid + its session_version), 'admin' (env admin) or 'dev'."""
    request.session.clear()  # new session on every login (no fixation)
    request.session["email"] = email
    request.session["kind"] = kind
    if uid is not None:
        request.session["uid"] = uid
    if version is not None:
        request.session["sv"] = version
    if name:
        request.session["name"] = name
    return {"authenticated": True, "email": email, "name": name, "auth_disabled": not auth_enabled(),
            "is_admin": kind == "admin"}


def _db():
    from app.database import SessionLocal
    return SessionLocal()


def _find_user(db, email: str):
    from app.models import User
    return db.query(User).filter(User.email == email).first()


auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.get("/providers")
def providers():
    """Which sign-in methods this server has configured (the UI adapts)."""
    return {"password": True, "signup": signup_enabled(),
            "google": _provider_config("google") is not None,
            "microsoft": _provider_config("microsoft") is not None}


# New accounts per address per hour: sign-up is open and unverified, and each
# account gets its own storage quota, so accounts must not be free to mint.
_SIGNUP_MAX_PER_IP = 5
_signup_hits: dict = {}


_SIGNUP_MAX_KEYS = 10_000


def _reserve_signup(ip: str) -> Optional[float]:
    """Atomically take one of this address's sign-up slots for the next hour
    (None = none left). Concurrent requests cannot all pass one check; a
    reservation is given back if the account is not created."""
    import time
    now = time.time()
    with _login_lock:
        if ip not in _signup_hits and len(_signup_hits) >= _SIGNUP_MAX_KEYS:
            # Bound memory by dropping only expired allowances; if every entry is
            # still live, refuse the new address rather than reset a live limit.
            for k in [k for k, v in _signup_hits.items() if not v or now - v[-1] >= 3600]:
                del _signup_hits[k]
            if len(_signup_hits) >= _SIGNUP_MAX_KEYS:
                return None
        hits = [t for t in _signup_hits.get(ip, []) if now - t < 3600]
        if len(hits) >= _SIGNUP_MAX_PER_IP:
            _signup_hits[ip] = hits
            return None
        hits.append(now)
        _signup_hits[ip] = hits
        return now


def _release_signup(ip: str, token: float) -> None:
    with _login_lock:
        hits = _signup_hits.get(ip)
        if hits and token in hits:
            hits.remove(token)
        if not hits:
            _signup_hits.pop(ip, None)


@auth_router.post("/signup")
def signup(payload: dict, request: Request):
    if not signup_enabled():
        raise HTTPException(status_code=403, detail="Sign-up is disabled on this server")
    from app.models import User
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password") or "")
    name = str(payload.get("name") or "").strip()[:120] or None
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    problem = password_problem(password)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    ip = _client_ip(request)
    slot = _reserve_signup(ip)
    if slot is None:
        raise HTTPException(status_code=429, detail="Too many new accounts from this address — try again later")
    created = False
    try:  # the reservation's whole lifetime: any failure (even opening/closing the DB) gives it back
        db = _db()
        try:
            existing = _find_user(db, email)
            if existing is not None or _is_reserved(email):
                raise HTTPException(status_code=409, detail="An account with this email already exists — log in instead")
            uid = f"USR-{uuid.uuid4().hex[:12].upper()}"
            db.add(User(id=uid, email=email, name=name, password_hash=hash_password(password),
                        provider="password", session_version=0, last_login_at=datetime.utcnow()))
            kind = str(payload.get("account_type") or "company").strip().lower()
            if kind in ("company", "individual"):
                from app.models import CompanyProfile
                db.merge(CompanyProfile(id=email, account_type=kind, name=name if kind == "individual" else None))
            db.commit()
            created = True
        finally:
            db.close()
    finally:
        if not created:
            _release_signup(ip, slot)  # only accounts actually created use up the allowance
    return _start_session(request, email, name, uid=uid, version=0)


@auth_router.post("/login")
def login(payload: dict, request: Request):
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password", ""))
    ip = _client_ip(request)
    # Per IP and per IP+email: a stranger cannot lock a victim out from elsewhere.
    keys = (f"ip:{ip}", f"ip-email:{ip}|{email}")
    for k in keys:
        _check_rate(k)
    try:
        return _login(email, password, request)
    except HTTPException as e:
        if e.status_code == 401:
            for k in keys:
                _record_failure(k)
        raise


def _login(email: str, password: str, request: Request):
    # The admin address skips the users table: a row someone created for it
    # (before it was reserved) must not shadow or stand in for the env password.
    if not _is_reserved(email):
        db = _db()
        try:
            user = _find_user(db, email) if email else None
            if user is not None:
                # A registered account always needs its own password (also in dev mode).
                if not user.password_hash or not verify_password(password, user.password_hash):
                    detail = ("This account uses Google or Microsoft sign-in"
                              if not user.password_hash else "Invalid email or password")
                    raise HTTPException(status_code=401, detail=detail)
                # The version read with the hash just verified: if the account is
                # taken over meanwhile, this session is already stale.
                uid, version, name = user.id, user.session_version, user.name
                user.last_login_at = datetime.utcnow()
                db.commit()
                return _start_session(request, email, name, uid=uid, version=version)
        finally:
            db.close()

    if not auth_enabled():
        # Dev mode: unknown emails are let in, but the typed email is kept so
        # the UI shows who is signed in instead of a placeholder.
        return _start_session(request, email or "dev", kind="dev")

    expected_email = _configured_email()
    expected_password = _configured_password()
    # Compare as bytes: compare_digest raises TypeError on non-ASCII str.
    if not (expected_email and
            hmac.compare_digest(email.encode("utf-8"), expected_email.encode("utf-8"))
            and hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8"))):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _start_session(request, expected_email, kind="admin", version=_admin_session_version())


def _me_payload(request: Request, principal: dict) -> dict:
    return {"authenticated": True, "email": principal["email"], "name": request.session.get("name"),
            "auth_disabled": principal["auth_disabled"], "is_admin": principal["is_admin"]}


@auth_router.get("/me")
def me(request: Request):
    principal = _principal(request)
    if principal is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _me_payload(request, principal)


@auth_router.post("/logout")
def logout(request: Request):
    request.session.clear()
    response = Response(content='{"authenticated":false}', media_type="application/json")
    response.delete_cookie("tendermind_session", path="/")
    return response


# ------------------------------------------------------- Google / Microsoft
# Authorization-code flow run by the server. The id_token is received directly
# from the provider's token endpoint over TLS, so per OpenID Connect Core
# 3.1.3.7 its signature check may rely on TLS; audience, issuer, expiry and
# nonce are still verified here.
def _provider_config(provider: str) -> Optional[dict]:
    if provider == "google":
        cid, secret = os.getenv("GOOGLE_CLIENT_ID", "").strip(), os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        if not (cid and secret):
            return None
        return {"client_id": cid, "client_secret": secret,
                "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
                "token": "https://oauth2.googleapis.com/token",
                "issuers": ("https://accounts.google.com", "accounts.google.com")}
    if provider == "microsoft":
        cid, secret = os.getenv("MICROSOFT_CLIENT_ID", "").strip(), os.getenv("MICROSOFT_CLIENT_SECRET", "").strip()
        if not (cid and secret):
            return None
        tenant = os.getenv("MICROSOFT_TENANT", "common").strip() or "common"
        base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
        return {"client_id": cid, "client_secret": secret,
                "authorize": f"{base}/authorize", "token": f"{base}/token",
                "issuers": None}  # multi-tenant issuer embeds the user's tenant id
    return None


def _safe_next(raw: Optional[str]) -> str:
    """Only same-site relative paths (no open redirect)."""
    nxt = str(raw or "")
    if nxt.startswith("/") and not nxt.startswith("//") and "\\" not in nxt:
        return nxt
    return "/dashboard"


def _redirect_uri(request: Request, provider: str) -> str:
    base = os.getenv("TENDERMIND_PUBLIC_URL", "").strip().rstrip("/") or str(request.base_url).rstrip("/")
    return f"{base}/api/auth/oauth/{provider}/callback"


def _login_error(code: str) -> RedirectResponse:
    return RedirectResponse(f"/login?auth_error={code}", status_code=302)


def _claim_true(value) -> bool:
    """Boolean claims arrive as JSON true; accept the string/int spellings, nothing else."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    return str(value or "").strip().lower() in {"true", "1"}


def _oauth_email(provider: str, claims: dict) -> tuple[Optional[str], Optional[str]]:
    """(email, None) when the provider vouches for the address, else (None, error code).

    Microsoft's email and preferred_username are editable by any tenant admin, so
    anyone with their own Entra tenant could claim any address. Only an email
    claim whose domain Microsoft has verified for that tenant (optional claim
    xms_edov, configured on the app registration) is accepted as an identity.
    """
    if provider == "google":
        if not _claim_true(claims.get("email_verified")):
            return None, "email_not_verified"
        return normalize_email(claims.get("email")), None
    if not _claim_true(claims.get("xms_edov")):
        return None, "microsoft_email_unverified"
    return normalize_email(claims.get("email")), None


def _google_is_authoritative(email: str, claims: dict) -> bool:
    """Google vouches for who owns an address today only for Gmail and for the
    Workspace domains it hosts (hd claim); elsewhere email_verified may date
    from a previous owner of the address."""
    domain = email.rsplit("@", 1)[-1]
    if domain in {"gmail.com", "googlemail.com"}:
        return True
    return str(claims.get("hd") or "").strip().lower() == domain


def _may_link(user, provider: str, subject: str, email: str, claims: dict) -> bool:
    """May this provider identity sign in to an existing account with the same email?

    - An account already bound to a provider identity only accepts that exact identity.
    - Microsoft never takes over an account created another way.
    - Google may claim a password account only where Google is authoritative for
      the address; the unverified password on it is then removed (oauth_callback).
      A provider row without a subject is never claimed across providers.
    """
    if user.provider_subject:
        # A password account can only have been linked by Google (rule below).
        linked = "google" if user.provider == "password" else user.provider
        return provider == linked and hmac.compare_digest(user.provider_subject, subject)
    if provider == "microsoft":
        return user.provider == "microsoft"
    return user.provider == "password" and _google_is_authoritative(email, claims)


def _decode_jwt_payload(token: str) -> dict:
    part = token.split(".")[1]
    part += "=" * (-len(part) % 4)
    return json.loads(base64.urlsafe_b64decode(part.encode()))


@auth_router.get("/oauth/{provider}/start")
def oauth_start(provider: str, request: Request, next: Optional[str] = None):
    cfg = _provider_config(provider)
    if cfg is None:
        return _login_error(f"{provider}_not_configured")
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    request.session["oauth"] = {"provider": provider, "state": state, "nonce": nonce,
                                "next": _safe_next(next)}
    params = {"client_id": cfg["client_id"], "response_type": "code", "scope": "openid email profile",
              "redirect_uri": _redirect_uri(request, provider), "state": state, "nonce": nonce,
              "prompt": "select_account"}
    return RedirectResponse(f"{cfg['authorize']}?{urlencode(params)}", status_code=302)


@auth_router.get("/oauth/{provider}/callback")
def oauth_callback(provider: str, request: Request, code: Optional[str] = None,
                   state: Optional[str] = None, error: Optional[str] = None):
    import time
    import requests as http
    cfg = _provider_config(provider)
    pending = request.session.pop("oauth", None) or {}
    if cfg is None:
        return _login_error(f"{provider}_not_configured")
    if error:
        return _login_error("cancelled")
    if not code or not state or pending.get("provider") != provider or \
            not hmac.compare_digest(str(state), str(pending.get("state", ""))):
        return _login_error("invalid_state")
    try:
        r = http.post(cfg["token"], timeout=15, data={
            "code": code, "client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
            "redirect_uri": _redirect_uri(request, provider), "grant_type": "authorization_code"})
        r.raise_for_status()
        claims = _decode_jwt_payload(r.json()["id_token"])
    except Exception:
        return _login_error("token_exchange_failed")

    aud = claims.get("aud")
    aud_ok = aud == cfg["client_id"] or (isinstance(aud, list) and cfg["client_id"] in aud)
    iss = str(claims.get("iss", ""))
    iss_ok = (iss in cfg["issuers"]) if cfg["issuers"] else \
        (iss.startswith("https://login.microsoftonline.com/") and iss.endswith("/v2.0"))
    if not (aud_ok and iss_ok and float(claims.get("exp", 0)) > time.time()
            and hmac.compare_digest(str(claims.get("nonce", "")), str(pending.get("nonce", "")))):
        return _login_error("invalid_token")

    email, problem = _oauth_email(provider, claims)
    if problem:
        return _login_error(problem)
    if not _EMAIL_RE.match(email):
        return _login_error("no_email")
    subject = str(claims.get("sub", "")).strip()
    if not subject:
        return _login_error("invalid_token")
    if _is_reserved(email):
        return _login_error("account_exists")

    from sqlalchemy import update
    from app.models import User
    ip, slot, committed = _client_ip(request), None, False
    db = _db()
    try:
        user = _find_user(db, email)
        if user is not None and not _may_link(user, provider, subject, email, claims):
            return _login_error("account_exists")
        now = datetime.utcnow()
        if user is None:
            if not signup_enabled():
                return _login_error("signup_disabled")
            slot = _reserve_signup(ip)  # a new account through a provider counts too
            if slot is None:
                return _login_error("too_many_signups")
            user = User(id=f"USR-{uuid.uuid4().hex[:12].upper()}", email=email,
                        name=(claims.get("name") or "")[:120] or None, provider=provider,
                        provider_subject=subject, session_version=0, last_login_at=now)
            db.add(user)
        elif not user.provider_subject:
            # The provider has just proven this address. The password on the row
            # was set by whoever typed the address at sign-up, which nobody
            # verified: it stops working and every session opened with it ends.
            # One statement, so a concurrent password change cannot survive it;
            # the owner may set a new password in Settings.
            claimed = db.execute(
                update(User)
                .where(User.id == user.id, (User.provider_subject.is_(None)) | (User.provider_subject == ""))
                .values(provider_subject=subject, password_hash=None,
                        session_version=User.session_version + 1, last_login_at=now)
                .execution_options(synchronize_session=False))
            if claimed.rowcount != 1:
                db.rollback()
                return _login_error("account_exists")
        else:
            user.last_login_at = now
        db.commit()
        committed = True
        db.refresh(user)
        uid, version, name = user.id, user.session_version, user.name
    finally:
        try:
            db.close()
        finally:  # a new account's reservation comes back whatever failed
            if slot is not None and not committed:
                _release_signup(ip, slot)
    _start_session(request, email, name, uid=uid, version=version)
    return RedirectResponse(pending.get("next") or "/dashboard", status_code=302)



# ------------------------------------------------------------ Stage 5I settings
@auth_router.patch("/me")
def update_me(payload: dict, request: Request):
    principal = _principal(request)
    if principal is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = principal["email"]
    name = str(payload.get("name") or "").strip()[:120]
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    db = _db()
    try:
        user = _find_user(db, email)
        if user is not None:
            user.name = name
            db.commit()
    finally:
        db.close()
    request.session["name"] = name
    return _me_payload(request, principal)


@auth_router.post("/change-password")
def change_password(payload: dict, request: Request):
    principal = _principal(request)
    if principal is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = principal["email"]
    current = str(payload.get("current_password") or "")
    new = str(payload.get("new_password") or "")
    problem = password_problem(new)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    key = f"ip-email:{_client_ip(request)}|{email}"
    _check_rate(key)
    from sqlalchemy import update
    from app.models import User
    db = _db()
    try:
        user = None if _is_reserved(email) else _find_user(db, email)
        if user is None:
            raise HTTPException(status_code=400, detail="This account's password is managed by the server administrator")
        if user.password_hash and not verify_password(current, user.password_hash):
            _record_failure(key)
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        # Only from the session version this request was authorised with: a
        # takeover or another password change in between makes this a no-op.
        version = principal.get("sv", user.session_version)
        changed = db.execute(
            update(User).where(User.id == user.id, User.session_version == version)
            .values(password_hash=hash_password(new), session_version=User.session_version + 1)
            .execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            db.rollback()
            request.session.clear()
            raise HTTPException(status_code=401, detail="Your session has ended — sign in again")
        db.commit()
        uid, name = user.id, request.session.get("name")
    finally:
        db.close()
    # Every other session of this account ends; this one continues on the new version.
    _start_session(request, email, name, uid=uid, version=version + 1)
    return {"changed": True}


# ------------------------------------------------------- public demo requests
_DEMO_MAX_PER_IP = 5          # per hour: the form is public, so it is rate-limited per address
_demo_hits: dict = {}


@auth_router.post("/demo-requests")
def create_demo_request(payload: dict, request: Request):
    """'Book a demo' / 'Talk to sales' from the public website. Stored for the team; nothing is emailed."""
    import time
    from app.models import DemoRequest
    ip = _client_ip(request)
    now = time.time()
    with _login_lock:
        hits = [t for t in _demo_hits.get(ip, []) if now - t < 3600]
        if len(hits) >= _DEMO_MAX_PER_IP:
            raise HTTPException(status_code=429, detail="Too many requests — try again later")
        hits.append(now)
        _demo_hits[ip] = hits
        if len(_demo_hits) > 10_000:
            _demo_hits.clear()
    clean = lambda k, n: " ".join(str(payload.get(k) or "").split())[:n] or None
    name, email = clean("name", 120), normalize_email(payload.get("email"))
    if not name:
        raise HTTPException(status_code=400, detail="Your name is required")
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    if payload.get("website"):  # honeypot field, invisible to people
        return {"ok": True}
    db = _db()
    try:
        db.add(DemoRequest(id=f"DR-{uuid.uuid4().hex[:10].upper()}", name=name, email=email,
                           company=clean("company", 200), country=clean("country", 60), topic=clean("topic", 60),
                           message=(str(payload.get("message") or "").strip()[:2000] or None)))
        db.commit()
    finally:
        db.close()
    return {"ok": True}
