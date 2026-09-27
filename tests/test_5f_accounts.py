"""Stage 5F — sign-up, password login, Google / Microsoft sign-in."""
import base64
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
              "TENDERMIND_SIGNUP_ENABLED", "TENDERMIND_PUBLIC_URL"):
        monkeypatch.delenv(k, raising=False)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _email():
    return f"user-{uuid.uuid4().hex[:8]}@company.test"


def test_password_hash_roundtrip_and_salt():
    from app.auth import hash_password, verify_password
    h1, h2 = hash_password("Secret123"), hash_password("Secret123")
    assert h1 != h2 and h1.startswith("pbkdf2_sha256$")  # salted
    assert verify_password("Secret123", h1) and not verify_password("secret123", h1)
    assert not verify_password("x", "garbage") and not verify_password("x", None)


def test_signup_then_login_and_me(client):
    email = _email()
    r = client.post("/api/auth/signup", json={"email": email.upper(), "password": "Tender2026", "name": "Sara"})
    assert r.status_code == 200 and r.json()["email"] == email
    assert client.get("/api/auth/me").json()["email"] == email  # signed in right away
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": email, "password": "Tender2026"}).status_code == 200
    assert client.get("/api/auth/me").json()["name"] == "Sara"


def test_signup_validation(client):
    assert client.post("/api/auth/signup", json={"email": "not-an-email", "password": "Tender2026"}).status_code == 400
    assert client.post("/api/auth/signup", json={"email": _email(), "password": "short1"}).status_code == 400
    assert client.post("/api/auth/signup", json={"email": _email(), "password": "onlyletters"}).status_code == 400
    email = _email()
    assert client.post("/api/auth/signup", json={"email": email, "password": "Tender2026"}).status_code == 200
    dup = client.post("/api/auth/signup", json={"email": email, "password": "Other2026"})
    assert dup.status_code == 409


def test_registered_account_needs_its_password_even_in_dev_mode(client):
    email = _email()
    client.post("/api/auth/signup", json={"email": email, "password": "Tender2026"})
    client.post("/api/auth/logout")
    r = client.post("/api/auth/login", json={"email": email, "password": "wrong-pass1"})
    assert r.status_code == 401


def test_password_is_never_stored_in_clear(client):
    email = _email()
    client.post("/api/auth/signup", json={"email": email, "password": "Tender2026"})
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        assert "Tender2026" not in (u.password_hash or "")
    finally:
        db.close()


def test_signup_can_be_disabled(client, monkeypatch):
    monkeypatch.setenv("TENDERMIND_SIGNUP_ENABLED", "0")
    assert client.post("/api/auth/signup", json={"email": _email(), "password": "Tender2026"}).status_code == 403


def test_providers_reflect_configuration(client, monkeypatch):
    assert client.get("/api/auth/providers").json() == {"password": True, "signup": True, "google": False, "microsoft": False}
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "gsecret")
    assert client.get("/api/auth/providers").json()["google"] is True


def test_oauth_start_unconfigured_returns_to_login(client):
    r = client.get("/api/auth/oauth/google/start", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/login?auth_error=google_not_configured"


def _id_token(claims):
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.sig"


def _start(client, provider, next_path="/tenders"):
    r = client.get(f"/api/auth/oauth/{provider}/start", params={"next": next_path}, follow_redirects=False)
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    return q["state"][0], q["nonce"][0], q


@pytest.fixture()
def google(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "gid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "gsecret")
    sent = {}

    def install(claims):
        class R:
            def raise_for_status(self): pass
            def json(self): return {"id_token": _id_token(claims)}

        def fake_post(url, data=None, timeout=None):
            sent.update({"url": url, **(data or {})})
            return R()
        monkeypatch.setattr("requests.post", fake_post)
    return install, sent


def test_google_sign_in_creates_account_and_session(client, google):
    install, sent = google
    state, nonce, q = _start(client, "google")
    assert q["redirect_uri"][0].endswith("/api/auth/oauth/google/callback")
    email = _email()
    install({"aud": "gid.apps.googleusercontent.com", "iss": "https://accounts.google.com", "exp": time.time() + 300,
             "nonce": nonce, "email": email, "email_verified": True, "name": "Omar", "sub": "123"})
    r = client.get("/api/auth/oauth/google/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/tenders"
    assert sent["client_secret"] == "gsecret" and sent["grant_type"] == "authorization_code"
    me = client.get("/api/auth/me").json()
    assert me["email"] == email and me["name"] == "Omar"


@pytest.mark.parametrize("bad", ["state", "nonce", "aud", "iss", "exp", "unverified"])
def test_google_callback_rejects_tampering(client, google, bad):
    install, _ = google
    state, nonce, _q = _start(client, "google")
    claims = {"aud": "gid.apps.googleusercontent.com", "iss": "https://accounts.google.com",
              "exp": time.time() + 300, "nonce": nonce, "email": _email(), "email_verified": True}
    if bad == "nonce": claims["nonce"] = "other"
    if bad == "aud": claims["aud"] = "someone-else"
    if bad == "iss": claims["iss"] = "https://evil.example"
    if bad == "exp": claims["exp"] = time.time() - 10
    if bad == "unverified": claims["email_verified"] = False
    install(claims)
    r = client.get("/api/auth/oauth/google/callback",
                   params={"code": "c", "state": "forged" if bad == "state" else state}, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"].startswith("/login?auth_error=")
    me = client.get("/api/auth/me").json()
    assert me["email"] in ("dev", None) or "@company.test" not in me["email"]


def test_microsoft_sign_in(client, monkeypatch):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "ms-app-id")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "ms-secret")
    state, nonce, q = _start(client, "microsoft", "/dashboard")
    email = _email()

    class R:
        def raise_for_status(self): pass
        def json(self):
            return {"id_token": _id_token({"aud": "ms-app-id", "exp": time.time() + 300, "nonce": nonce,
                                            "iss": "https://login.microsoftonline.com/tenant-guid/v2.0",
                                            "preferred_username": email, "name": "Mona", "sub": "ms-1"})}
    monkeypatch.setattr("requests.post", lambda *a, **k: R())
    r = client.get("/api/auth/oauth/microsoft/callback", params={"code": "c", "state": state}, follow_redirects=False)
    assert r.headers["location"] == "/dashboard"
    assert client.get("/api/auth/me").json()["email"] == email


def test_oauth_next_cannot_redirect_off_site(client, google):
    _install, _ = google
    from app.auth import _safe_next
    for evil in ("https://evil.example", "//evil.example", "/\\evil.example", None):
        assert _safe_next(evil) == "/dashboard"
    assert _safe_next("/tenders/T-1") == "/tenders/T-1"


def test_google_account_cannot_password_login(client, google):
    install, _ = google
    state, nonce, _q = _start(client, "google")
    email = _email()
    install({"aud": "gid.apps.googleusercontent.com", "iss": "accounts.google.com", "exp": time.time() + 300,
             "nonce": nonce, "email": email, "email_verified": True})
    client.get("/api/auth/oauth/google/callback", params={"code": "c", "state": state}, follow_redirects=False)
    client.post("/api/auth/logout")
    r = client.post("/api/auth/login", json={"email": email, "password": "anything1"})
    assert r.status_code == 401 and "Google or Microsoft" in r.json()["detail"]
