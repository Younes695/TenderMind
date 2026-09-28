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
def require_auth(request: Request):
    if not auth_enabled():
        return {"email": request.session.get("email") or "dev", "auth_disabled": True}

    email = request.session.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"email": email, "auth_disabled": False}


def _start_session(request: Request, email: str, name: Optional[str] = None) -> dict:
    request.session.clear()  # new session on every login (no fixation)
    request.session["email"] = email
    if name:
        request.session["name"] = name
    return {"authenticated": True, "email": email, "name": name, "auth_disabled": not auth_enabled()}


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
    db = _db()
    try:
        existing = _find_user(db, email)
        if existing is not None or email == _configured_email():
            raise HTTPException(status_code=409, detail="An account with this email already exists — log in instead")
        db.add(User(id=f"USR-{uuid.uuid4().hex[:12].upper()}", email=email, name=name,
                    password_hash=hash_password(password), provider="password",
                    last_login_at=datetime.utcnow()))
        db.commit()
    finally:
        db.close()
    return _start_session(request, email, name)


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
    db = _db()
    try:
        user = _find_user(db, email) if email else None
        if user is not None:
            # A registered account always needs its own password (also in dev mode).
            if not user.password_hash or not verify_password(password, user.password_hash):
                detail = ("This account uses Google or Microsoft sign-in"
                          if not user.password_hash else "Invalid email or password")
                raise HTTPException(status_code=401, detail=detail)
            user.last_login_at = datetime.utcnow()
            db.commit()
            return _start_session(request, user.email, user.name)
    finally:
        db.close()

    if not auth_enabled():
        # Dev mode: unknown emails are let in, but the typed email is kept so
        # the UI shows who is signed in instead of a placeholder.
        return _start_session(request, email or "dev")

    expected_email = _configured_email()
    expected_password = _configured_password()
    # Compare as bytes: compare_digest raises TypeError on non-ASCII str.
    if not (expected_email and
            hmac.compare_digest(email.encode("utf-8"), expected_email.encode("utf-8"))
            and hmac.compare_digest(password.encode("utf-8"), expected_password.encode("utf-8"))):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _start_session(request, expected_email)


@auth_router.get("/me")
def me(request: Request):
    email = request.session.get("email")
    if not auth_enabled():
        return {"authenticated": True, "email": email or "dev", "name": request.session.get("name"),
                "auth_disabled": True}
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"authenticated": True, "email": email, "name": request.session.get("name"), "auth_disabled": False}


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


def _may_link(user, provider: str, subject: str) -> bool:
    """May this provider identity sign in to an existing account with the same email?

    - An account already bound to a provider identity only accepts that exact identity.
    - Microsoft's email / preferred_username claims are not verified (any tenant
      admin can set them), so Microsoft never takes over an account created
      another way — otherwise anyone with their own Azure tenant could sign in
      as any user.
    - Google emails are verified (email_verified is required above), so Google
      may sign in to a password account with the same address.
    """
    if user.provider_subject:
        # A password account can only have been linked by Google (rule below).
        linked = "google" if user.provider == "password" else user.provider
        return provider == linked and hmac.compare_digest(user.provider_subject, subject)
    if provider == "microsoft":
        return user.provider == "microsoft"
    return True


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

    email = normalize_email(claims.get("email") or claims.get("preferred_username"))
    if provider == "google" and not claims.get("email_verified"):
        return _login_error("email_not_verified")
    if not _EMAIL_RE.match(email):
        return _login_error("no_email")

    from app.models import User
    subject = str(claims.get("sub", ""))
    db = _db()
    try:
        user = _find_user(db, email)
        if user is not None and not _may_link(user, provider, subject):
            return _login_error("account_exists")
        if user is None:
            if not signup_enabled():
                return _login_error("signup_disabled")
            user = User(id=f"USR-{uuid.uuid4().hex[:12].upper()}", email=email,
                        name=(claims.get("name") or "")[:120] or None, provider=provider,
                        provider_subject=subject)
            db.add(user)
        elif not user.provider_subject:
            user.provider_subject = subject
        user.last_login_at = datetime.utcnow()
        db.commit()
        name = user.name
    finally:
        db.close()
    _start_session(request, email, name)
    return RedirectResponse(pending.get("next") or "/dashboard", status_code=302)



# ------------------------------------------------------------ Stage 5I settings
@auth_router.patch("/me")
def update_me(payload: dict, request: Request):
    email = request.session.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")
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
    return {"authenticated": True, "email": email, "name": name, "auth_disabled": not auth_enabled()}


@auth_router.post("/change-password")
def change_password(payload: dict, request: Request):
    email = request.session.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    current = str(payload.get("current_password") or "")
    new = str(payload.get("new_password") or "")
    problem = password_problem(new)
    if problem:
        raise HTTPException(status_code=400, detail=problem)
    key = f"ip-email:{_client_ip(request)}|{email}"
    _check_rate(key)
    db = _db()
    try:
        user = _find_user(db, email)
        if user is None:
            raise HTTPException(status_code=400, detail="This account's password is managed by the server administrator")
        if user.password_hash and not verify_password(current, user.password_hash):
            _record_failure(key)
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        user.password_hash = hash_password(new)
        db.commit()
    finally:
        db.close()
    return {"changed": True}
