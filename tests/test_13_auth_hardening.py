"""Auth hardening: the three account holes found in the 30 Sep review.

V1  /api/demo-requests showed every website lead to any signed-up account.
V2  Microsoft sign-in (unverified email claim) could open a session for the
    env-admin address, which had no users row to protect it.
V3  A password account registered by someone else kept its password after the
    real owner claimed it with Google, and sessions could not be revoked.
"""
import base64
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

ADMIN_EMAIL = "admin@tm.test"
ADMIN_PASSWORD = "Admin2026x"


@pytest.fixture()
def app_auth_on(monkeypatch):
    monkeypatch.setenv("TENDERMIND_AUTH_ENABLED", "1")
    monkeypatch.setenv("TENDERMIND_SIGNUP_ENABLED", "1")
    monkeypatch.setenv("TENDERMIND_AUTH_EMAIL", ADMIN_EMAIL)
    monkeypatch.setenv("TENDERMIND_AUTH_PASSWORD", ADMIN_PASSWORD)
    for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET",
              "TENDERMIND_PUBLIC_URL"):
        monkeypatch.delenv(k, raising=False)
    from app import auth
    auth._login_failures.clear()
    auth._demo_hits.clear()
    from app.main import app
    yield app
    auth._login_failures.clear()
    auth._demo_hits.clear()


def _client(app):
    c = TestClient(app, base_url="https://testserver")
    c.__enter__()
    return c


def _signup(app, email=None, password="Tender2026"):
    c = _client(app)
    email = email or f"u-{uuid.uuid4().hex[:8]}@tm.test"
    assert c.post("/api/auth/signup", json={"email": email, "password": password}).status_code == 200
    return c, email


def _admin(app):
    c = _client(app)
    r = c.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200 and r.json()["is_admin"] is True
    return c


def _id_token(claims):
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'RS256'})}.{enc(claims)}.sig"


def _oauth(client, monkeypatch, provider, **claims):
    """Run one sign-in through the real callback with a faked token endpoint."""
    if provider == "google":
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "gid.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "gsecret")
        base = {"aud": "gid.apps.googleusercontent.com", "iss": "https://accounts.google.com"}
    else:
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "ms-app-id")
        monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "ms-secret")
        base = {"aud": "ms-app-id", "iss": "https://login.microsoftonline.com/attacker-tenant/v2.0"}
    r = client.get(f"/api/auth/oauth/{provider}/start", params={"next": "/dashboard"}, follow_redirects=False)
    q = parse_qs(urlparse(r.headers["location"]).query)
    token = _id_token({**base, "exp": time.time() + 300, "nonce": q["nonce"][0], **claims})

    class R:
        def raise_for_status(self): pass
        def json(self): return {"id_token": token}
    monkeypatch.setattr("requests.post", lambda *a, **k: R())
    r = client.get(f"/api/auth/oauth/{provider}/callback", params={"code": "c", "state": q["state"][0]},
                   follow_redirects=False)
    return r.headers["location"]


def _forged_cookie(session: dict) -> str:
    """A cookie exactly as SessionMiddleware writes it, signed with the server secret."""
    import itsdangerous
    from app.auth import _session_secret
    data = base64.b64encode(json.dumps(session).encode("utf-8"))
    return itsdangerous.TimestampSigner(_session_secret()).sign(data).decode("utf-8")


def _users_row(email):
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


# ------------------------------------------------------------------ V1
def test_demo_requests_are_for_the_server_admin_only(app_auth_on):
    public = _client(app_auth_on)
    lead = {"name": "Sara Ali", "email": f"lead-{uuid.uuid4().hex[:6]}@delta.test", "topic": "plan:growth"}
    assert public.post("/api/auth/demo-requests", json=lead).json() == {"ok": True}

    customer, _ = _signup(app_auth_on)
    assert customer.get("/api/auth/me").json()["is_admin"] is False
    assert customer.get("/api/demo-requests").status_code == 404

    admin = _admin(app_auth_on)
    assert admin.get("/api/auth/me").json()["is_admin"] is True
    rows = admin.get("/api/demo-requests").json()
    assert any(r["email"] == lead["email"] for r in rows)


# ------------------------------------------------------------------ V2
@pytest.mark.parametrize("provider,claims", [
    ("microsoft", {"email": ADMIN_EMAIL, "xms_edov": True, "sub": "ms-evil"}),
    ("google", {"email": ADMIN_EMAIL, "email_verified": True, "hd": "tm.test", "sub": "g-evil"}),
])
def test_no_provider_can_sign_in_as_the_admin_address(app_auth_on, monkeypatch, provider, claims):
    c = _client(app_auth_on)
    assert _oauth(c, monkeypatch, provider, **claims) == "/login?auth_error=account_exists"
    assert _users_row(ADMIN_EMAIL) is None
    assert c.get("/api/auth/me").status_code == 401
    assert c.get("/api/company/OUR_COMPANY").status_code == 401   # all accounts' evaluation evidence


def test_microsoft_needs_a_domain_verified_email(app_auth_on, monkeypatch):
    email = f"m-{uuid.uuid4().hex[:8]}@contoso.test"
    c = _client(app_auth_on)
    # Any tenant admin can set these, so neither is proof of the address.
    assert _oauth(c, monkeypatch, "microsoft", email=email, sub="ms-1") == \
        "/login?auth_error=microsoft_email_unverified"
    assert _oauth(c, monkeypatch, "microsoft", email=email, xms_edov=False, sub="ms-1") == \
        "/login?auth_error=microsoft_email_unverified"
    assert _oauth(c, monkeypatch, "microsoft", preferred_username=email, xms_edov=True, sub="ms-1") == \
        "/login?auth_error=no_email"
    assert _users_row(email) is None
    # Domain verified by Microsoft for that tenant: accepted (string spelling too).
    assert _oauth(c, monkeypatch, "microsoft", email=email, xms_edov="true", sub="ms-1") == "/dashboard"
    assert c.get("/api/auth/me").json()["email"] == email


def test_a_session_cookie_without_a_version_is_refused(app_auth_on):
    """Pre-upgrade cookies name only an email; for the admin address they cannot be
    told apart from one minted through the Microsoft hole, so none is honoured."""
    from app.auth import _admin_session_version
    c = _client(app_auth_on)
    c.cookies.set("tendermind_session", _forged_cookie({"email": ADMIN_EMAIL}))
    assert c.get("/api/demo-requests").status_code == 401
    assert c.get("/api/tenders").status_code == 401
    # Control: the same forging produces a working admin cookie once it carries
    # the admin version, so the 401 above is the version check, not a bad cookie.
    ok = _client(app_auth_on)
    ok.cookies.set("tendermind_session", _forged_cookie(
        {"email": ADMIN_EMAIL, "kind": "admin", "sv": _admin_session_version()}))
    assert ok.get("/api/demo-requests").status_code == 200

    user, email = _signup(app_auth_on)
    row = _users_row(email)
    legacy = _client(app_auth_on)
    legacy.cookies.set("tendermind_session", _forged_cookie({"email": email, "kind": "user", "uid": row.id}))
    assert legacy.get("/api/tenders").status_code == 401


def test_a_users_row_for_the_admin_address_grants_nothing(app_auth_on):
    """A row created for the admin address before it was reserved must neither
    shadow the env password nor act as the admin."""
    from app.auth import hash_password
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    uid = f"USR-{uuid.uuid4().hex[:12].upper()}"
    db.add(User(id=uid, email=ADMIN_EMAIL, provider="microsoft", provider_subject="ms-evil",
                password_hash=hash_password("Mallory2026"), session_version=0))
    db.commit()
    db.close()
    try:
        c = _client(app_auth_on)
        assert c.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "Mallory2026"}).status_code == 401
        squat = _client(app_auth_on)
        squat.cookies.set("tendermind_session", _forged_cookie(
            {"email": ADMIN_EMAIL, "kind": "user", "uid": uid, "sv": 0}))
        assert squat.get("/api/demo-requests").status_code == 401
        assert _admin(app_auth_on).get("/api/demo-requests").status_code == 200
    finally:
        db = SessionLocal()
        db.query(User).filter(User.id == uid).delete()
        db.commit()
        db.close()


# ------------------------------------------------------------------ V3
def test_google_owner_takes_the_account_back_from_a_squatter(app_auth_on, monkeypatch):
    victim_email = f"v-{uuid.uuid4().hex[:8]}@gmail.com"
    squatter, _ = _signup(app_auth_on, victim_email, password="Squat2026")
    tid = f"T-{uuid.uuid4().hex[:8]}"
    assert squatter.post("/api/tenders", json={"id": tid, "title": "Squatter"}).status_code == 200

    owner = _client(app_auth_on)
    assert _oauth(owner, monkeypatch, "google", email=victim_email, email_verified=True, sub="g-owner") == "/dashboard"

    # The squatter's open session and the password it chose both stop working.
    assert squatter.get("/api/tenders").status_code == 401
    r = _client(app_auth_on).post("/api/auth/login", json={"email": victim_email, "password": "Squat2026"})
    assert r.status_code == 401 and "Google or Microsoft" in r.json()["detail"]
    # The owner is in and may set a password of their own.
    assert owner.get("/api/auth/me").json()["email"] == victim_email
    assert owner.post("/api/auth/change-password", json={"new_password": "Owner2026"}).status_code == 200
    assert _client(app_auth_on).post("/api/auth/login",
                                     json={"email": victim_email, "password": "Owner2026"}).status_code == 200


def test_google_claims_only_addresses_it_is_authoritative_for(app_auth_on, monkeypatch):
    c, email = _signup(app_auth_on, f"p-{uuid.uuid4().hex[:8]}@company.test")
    other = _client(app_auth_on)
    # company.test is not a Gmail / Google Workspace address: email_verified may be stale.
    assert _oauth(other, monkeypatch, "google", email=email, email_verified=True, sub="g-1") == \
        "/login?auth_error=account_exists"
    assert c.get("/api/tenders").status_code == 200
    assert _client(app_auth_on).post("/api/auth/login",
                                     json={"email": email, "password": "Tender2026"}).status_code == 200
    # A Workspace of ANOTHER domain vouches for nothing about this address.
    assert _oauth(other, monkeypatch, "google", email=email, email_verified=True, hd="other.test",
                  sub="g-1") == "/login?auth_error=account_exists"
    assert c.get("/api/tenders").status_code == 200
    # Workspace-hosted domain (hd matches): Google is authoritative, so the owner may claim it.
    assert _oauth(other, monkeypatch, "google", email=email, email_verified=True, hd="company.test",
                  sub="g-1") == "/dashboard"
    assert c.get("/api/tenders").status_code == 401


def test_google_never_claims_a_provider_row_without_a_subject(app_auth_on, monkeypatch):
    """A Microsoft row left without a subject must not be rebound to Google while
    still marked Microsoft (it would lock out both identities)."""
    from app.database import SessionLocal
    from app.models import User
    email = f"ms-{uuid.uuid4().hex[:8]}@gmail.com"
    db = SessionLocal()
    db.add(User(id=f"USR-{uuid.uuid4().hex[:12].upper()}", email=email, provider="microsoft",
                provider_subject=None, session_version=0))
    db.commit()
    db.close()
    c = _client(app_auth_on)
    assert _oauth(c, monkeypatch, "google", email=email, email_verified=True, sub="g-x") == \
        "/login?auth_error=account_exists"
    row = _users_row(email)
    assert row.provider == "microsoft" and not row.provider_subject


def test_password_change_loses_to_a_takeover_that_lands_first(app_auth_on, monkeypatch):
    """The session was valid when the request started; the account is taken over
    before the password is written. The write must not happen."""
    from app import auth
    from app.database import SessionLocal
    from app.models import User
    c, email = _signup(app_auth_on)
    real_hash = auth.hash_password

    def takeover_then_hash(pw):
        db = SessionLocal()
        db.query(User).filter(User.email == email).update({User.session_version: User.session_version + 1})
        db.commit()
        db.close()
        return real_hash(pw)
    monkeypatch.setattr(auth, "hash_password", takeover_then_hash)
    r = c.post("/api/auth/change-password", json={"current_password": "Tender2026", "new_password": "Late2026x"})
    monkeypatch.setattr(auth, "hash_password", real_hash)
    assert r.status_code == 401
    assert _client(app_auth_on).post("/api/auth/login", json={"email": email, "password": "Late2026x"}).status_code == 401
    assert _client(app_auth_on).post("/api/auth/login", json={"email": email, "password": "Tender2026"}).status_code == 200


def test_password_change_ends_every_other_session(app_auth_on):
    first, email = _signup(app_auth_on)
    second = _client(app_auth_on)
    assert second.post("/api/auth/login", json={"email": email, "password": "Tender2026"}).status_code == 200
    r = first.post("/api/auth/change-password", json={"current_password": "Tender2026", "new_password": "Fresh2026"})
    assert r.status_code == 200
    assert second.get("/api/tenders").status_code == 401
    assert first.get("/api/tenders").status_code == 200
    login = lambda pw: _client(app_auth_on).post("/api/auth/login", json={"email": email, "password": pw})
    assert login("Tender2026").status_code == 401
    assert login("Fresh2026").status_code == 200


def _old_users_table(conn):
    from sqlalchemy import text
    conn.execute(text("CREATE TABLE users (id VARCHAR PRIMARY KEY, email VARCHAR, name VARCHAR, "
                      "password_hash VARCHAR, provider VARCHAR, provider_subject VARCHAR, "
                      "created_at DATETIME, last_login_at DATETIME)"))
    conn.execute(text("INSERT INTO users (id, email, password_hash, provider, provider_subject) VALUES "
                      "('linked', 'a@x.test', 'h1', 'password', 'g-1'), "
                      "('plain', 'b@x.test', 'h2', 'password', NULL), "
                      "('google', 'c@x.test', NULL, 'google', 'g-2')"))
    conn.commit()


def test_migration_clears_passwords_that_google_linking_left_behind(tmp_path):
    from sqlalchemy import create_engine, text
    from app.database import migrate_users_session_version
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.connect() as conn:
        _old_users_table(conn)
        migrate_users_session_version(conn)
        rows = {r.id: r for r in conn.execute(text("SELECT id, password_hash, session_version FROM users"))}
        assert rows["linked"].password_hash is None and rows["linked"].session_version == 0
        assert rows["plain"].password_hash == "h2" and rows["plain"].session_version == 0
        assert rows["google"].password_hash is None and rows["google"].session_version == 0
        # Runs once: a password the owner sets afterwards is not cleared on the next start.
        conn.execute(text("UPDATE users SET password_hash = 'owner-set' WHERE id = 'linked'"))
        conn.commit()
        migrate_users_session_version(conn)
        assert conn.execute(text("SELECT password_hash FROM users WHERE id = 'linked'")).scalar() == "owner-set"


def test_migration_interrupted_midway_still_clears_on_the_next_start(tmp_path):
    """Startup dies between the two steps; the retry must not treat the table as done
    while an unverified password is still there."""
    from sqlalchemy import create_engine, event, text
    from app.database import migrate_users_session_version
    engine = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")

    def dies_on_alter(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith("ALTER TABLE"):
            raise RuntimeError("disk full")

    with engine.connect() as conn:
        _old_users_table(conn)
    event.listen(engine, "before_cursor_execute", dies_on_alter)
    with engine.connect() as conn:
        with pytest.raises(RuntimeError, match="disk full"):
            migrate_users_session_version(conn)
    event.remove(engine, "before_cursor_execute", dies_on_alter)
    with engine.connect() as conn:                      # next start
        migrate_users_session_version(conn)
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(users)"))]
        assert "session_version" in cols
        assert conn.execute(text("SELECT password_hash FROM users WHERE id = 'linked'")).scalar() is None
        assert conn.execute(text("SELECT password_hash FROM users WHERE id = 'plain'")).scalar() == "h2"
