"""Medium-severity hardening from the 30 Sep review (and Codex's review of it).

(a) Uploads were read into temporary storage before authentication ran.
(b) Open, unverified sign-up plus no storage quota could fill the shared /data volume.
(c) A tender whose owner had no capability profile was judged by the env admin's.
(d) The Docker image trusted X-Forwarded-For from anyone, so the client chose its own address.
"""
import base64
import json
import re
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
ADMIN_EMAIL = "admin@tm.test"
ADMIN_PASSWORD = "Admin2026x"


@pytest.fixture()
def app_auth_on(monkeypatch):
    monkeypatch.setenv("TENDERMIND_AUTH_ENABLED", "1")
    monkeypatch.setenv("TENDERMIND_SIGNUP_ENABLED", "1")
    monkeypatch.setenv("TENDERMIND_AUTH_EMAIL", ADMIN_EMAIL)
    monkeypatch.setenv("TENDERMIND_AUTH_PASSWORD", ADMIN_PASSWORD)
    for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "MICROSOFT_CLIENT_ID", "MICROSOFT_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    from app import auth
    auth._login_failures.clear()
    from app.main import app
    yield app


def _client(app):
    c = TestClient(app, base_url="https://testserver")
    c.__enter__()
    return c


def _signup(app):
    c = _client(app)
    email = f"u-{uuid.uuid4().hex[:8]}@tm.test"
    assert c.post("/api/auth/signup", json={"email": email, "password": "Tender2026"}).status_code == 200
    return c, email


def _admin(app):
    c = _client(app)
    assert c.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).status_code == 200
    return c


def _tender(c):
    tid = f"T15-{uuid.uuid4().hex[:8]}"
    assert c.post("/api/tenders", json={"id": tid, "title": "Quota"}).status_code == 200
    return tid


def _files(*items):
    return [("files", (name, data, "text/plain")) for name, data in items]


# ------------------------------------------------------------------ (a)
class _CountsBodyBytes:
    """Wraps the app and counts the request-body bytes it actually read."""
    def __init__(self, app):
        self.app, self.read = app, 0

    async def __call__(self, scope, receive, send):
        async def counting_receive():
            message = await receive()
            if message.get("type") == "http.request":
                self.read += len(message.get("body", b""))
            return message
        await self.app(scope, counting_receive, send)


def test_anonymous_upload_is_refused_before_its_body_is_read(app_auth_on):
    probe = _CountsBodyBytes(app_auth_on)
    anon = TestClient(probe, base_url="https://testserver")
    anon.__enter__()
    body = b"x" * 300_000
    for path in ("/api/tenders/ANY/documents", "/api/company-documents", "/api/price-lists"):
        probe.read = 0
        r = anon.post(path, files={"files": ("big.pdf", body, "application/pdf")})
        assert r.status_code == 401 and probe.read == 0, (path, r.status_code, probe.read)
    # Control: a signed-in upload goes through the same wrapper and is read in full.
    user = TestClient(probe, base_url="https://testserver")
    user.__enter__()
    assert user.post("/api/auth/signup", json={"email": f"u-{uuid.uuid4().hex[:8]}@tm.test",
                                              "password": "Tender2026"}).status_code == 200
    tid = _tender(user)
    probe.read = 0
    r = user.post(f"/api/tenders/{tid}/documents", files={"files": ("ok.txt", b"hello tender", "text/plain")})
    assert r.status_code == 200 and probe.read > 0


def _forged_cookie(session):
    import itsdangerous
    from app.auth import _session_secret
    data = base64.b64encode(json.dumps(session).encode("utf-8"))
    return itsdangerous.TimestampSigner(_session_secret()).sign(data).decode("utf-8")


def test_early_401_drops_a_stale_cookie_and_keeps_cors(app_auth_on):
    c = _client(app_auth_on)
    c.cookies.set("tendermind_session", _forged_cookie({"email": "old@tm.test"}))   # pre-upgrade, no version
    r = c.get("/api/tenders", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 401
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    cookie = r.headers.get("set-cookie", "")
    assert cookie.startswith("tendermind_session=null;") and "expires=Thu, 01 Jan 1970" in cookie


def test_session_revoked_while_the_body_arrives_is_refused(app_auth_on, monkeypatch):
    """The early check passed; by the time the handler runs the session is gone."""
    import app.auth as auth
    c, _ = _signup(app_auth_on)
    tid = _tender(c)
    monkeypatch.setattr(auth, "_principal", lambda request: None)   # require_auth's check, after the body
    r = c.post(f"/api/tenders/{tid}/documents", files={"files": ("ok.txt", b"late", "text/plain")})
    assert r.status_code == 401


def test_public_auth_endpoints_still_work_without_a_session(app_auth_on):
    anon = _client(app_auth_on)
    assert anon.get("/api/auth/providers").status_code == 200
    assert anon.options("/api/tenders", headers={"Origin": "http://localhost:5173",
                                                 "Access-Control-Request-Method": "GET"}).status_code == 200


# ------------------------------------------------------------------ (b)
def test_account_storage_quota_covers_tender_and_company_uploads(app_auth_on, monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes, "_account_quota_bytes", lambda: 2500)
    c, _ = _signup(app_auth_on)
    tid = _tender(c)
    up = lambda name, n: c.post(f"/api/tenders/{tid}/documents", files={"files": (name, b"a" * n, "text/plain")})
    assert up("one.txt", 1000).status_code == 200
    assert up("two.txt", 1000).status_code == 200
    r = up("three.txt", 1000)                           # 3000 > 2500
    assert r.status_code == 413 and "Account storage is full" in r.json()["detail"]
    r = c.post("/api/company-documents", files={"files": ("profile.txt", b"b" * 600, "text/plain")})
    assert r.status_code == 413                         # company documents share the same quota
    docs = c.get(f"/api/tenders/{tid}/documents").json()["documents"]
    assert c.delete(f"/api/tenders/{tid}/documents/{docs[0]['id']}").status_code == 200
    assert up("three.txt", 1000).status_code == 200     # deleting frees room
    # Another account has its own room; the env admin runs the server and has none.
    other, _ = _signup(app_auth_on)
    t2 = _tender(other)
    assert other.post(f"/api/tenders/{t2}/documents", files={"files": ("x.txt", b"c" * 2000, "text/plain")}).status_code == 200
    admin = _admin(app_auth_on)
    t3 = _tender(admin)
    assert admin.post(f"/api/tenders/{t3}/documents", files={"files": ("x.txt", b"d" * 4000, "text/plain")}).status_code == 200


def test_a_failed_batch_leaves_no_files_behind(app_auth_on):
    from app.database import get_storage_root
    c, _ = _signup(app_auth_on)
    company = get_storage_root() / "_company"
    before = set(company.glob("*")) if company.exists() else set()
    r = c.post("/api/company-documents", files=_files(("good.txt", b"g" * 500), ("bad.exe", b"x" * 10)))
    assert r.status_code == 400
    assert set(company.glob("*")) - before == set()     # good.txt was written, then removed
    tid = _tender(c)
    tender_dir = get_storage_root() / tid
    r = c.post(f"/api/tenders/{tid}/documents", files=_files(("ok.txt", b"o" * 500), ("empty.txt", b"")))
    assert r.status_code == 400
    assert not any(p.is_file() for p in tender_dir.glob("*"))
    assert c.get(f"/api/tenders/{tid}/documents").json()["documents"] == []


def test_two_concurrent_uploads_cannot_spend_the_same_room(app_auth_on, monkeypatch):
    import app.api.routes as routes
    monkeypatch.setattr(routes, "_account_quota_bytes", lambda: 2500)
    real_room = routes._account_room_bytes

    def slow_room(db, user):          # widen the check-then-write window
        room = real_room(db, user)
        time.sleep(0.3)
        return room
    monkeypatch.setattr(routes, "_account_room_bytes", slow_room)
    c, _ = _signup(app_auth_on)
    tid = _tender(c)
    codes = []

    def upload(i):
        codes.append(c.post(f"/api/tenders/{tid}/documents",
                            files={"files": (f"f{i}.txt", b"z" * 2000, "text/plain")}).status_code)
    threads = [threading.Thread(target=upload, args=(i,)) for i in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(codes) == [200, 413]


def test_per_file_cap_fits_through_the_proxy(monkeypatch):
    import app.api.routes as routes
    monkeypatch.delenv("TENDERMIND_MAX_UPLOAD_MB", raising=False)
    per_file = routes._max_upload_bytes()
    assert per_file == 2 * 1024 ** 3
    m = re.search(r"max_size\s+(\d+)\s*(MiB|MB|GiB|GB)\b", (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8"))
    unit = {"MB": 10 ** 6, "MiB": 1024 ** 2, "GB": 10 ** 9, "GiB": 1024 ** 3}[m.group(2)]  # Caddy: MB is decimal
    assert int(m.group(1)) * unit >= per_file + 20 * 1024 ** 2   # room for the multipart envelope


def test_sign_up_is_limited_per_address(app_auth_on):
    c = _client(app_auth_on)
    new = lambda: c.post("/api/auth/signup", json={"email": f"s-{uuid.uuid4().hex[:8]}@tm.test",
                                                   "password": "Tender2026"}).status_code
    # Failed attempts use up nothing and leave nothing in memory.
    from app import auth
    keys = len(auth._signup_hits)
    assert c.post("/api/auth/signup", json={"email": "bad", "password": "Tender2026"}).status_code == 400
    assert len(auth._signup_hits) == keys
    taken = f"t-{uuid.uuid4().hex[:8]}@tm.test"
    assert c.post("/api/auth/signup", json={"email": taken, "password": "Tender2026"}).status_code == 200
    assert c.post("/api/auth/signup", json={"email": taken, "password": "Tender2026"}).status_code == 409
    assert [new() for _ in range(4)] == [200] * 4          # the 409 gave its slot back
    assert new() == 429


def test_concurrent_sign_ups_cannot_exceed_the_allowance(app_auth_on, monkeypatch):
    import app.auth as auth
    real_hash = auth.hash_password
    monkeypatch.setattr(auth, "hash_password", lambda pw: (time.sleep(0.2), real_hash(pw))[1])
    codes = []

    def signup():
        c = _client(app_auth_on)
        codes.append(c.post("/api/auth/signup", json={"email": f"c-{uuid.uuid4().hex[:8]}@tm.test",
                                                      "password": "Tender2026"}).status_code)
    threads = [threading.Thread(target=signup) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert codes.count(200) == 5 and codes.count(429) == 3


def test_signup_allowance_memory_is_bounded_without_resetting_live_limits(monkeypatch):
    import app.auth as auth
    monkeypatch.setattr(auth, "_SIGNUP_MAX_KEYS", 50)
    auth._signup_hits.clear()
    for _ in range(5):
        assert auth._reserve_signup("203.0.113.1") is not None        # this address used its allowance
    for i in range(200):
        auth._reserve_signup(f"10.9.0.{i}")
    assert len(auth._signup_hits) <= 50
    assert auth._reserve_signup("203.0.113.1") is None                 # still limited: not evicted
    # Expired entries make room again.
    for k in list(auth._signup_hits):
        auth._signup_hits[k] = [time.time() - 7200]
    assert auth._reserve_signup("198.51.100.9") is not None


def _google_new_account(client, monkeypatch, email):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "gid.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "gsecret")
    r = client.get("/api/auth/oauth/google/start", params={"next": "/dashboard"}, follow_redirects=False)
    q = parse_qs(urlparse(r.headers["location"]).query)
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    token = f"{enc({'alg': 'RS256'})}.{enc({'aud': 'gid.apps.googleusercontent.com', 'iss': 'https://accounts.google.com', 'exp': time.time() + 300, 'nonce': q['nonce'][0], 'email': email, 'email_verified': True, 'sub': uuid.uuid4().hex})}.sig"

    class R:
        def raise_for_status(self): pass
        def json(self): return {"id_token": token}
    monkeypatch.setattr("requests.post", lambda *a, **k: R())
    return client.get("/api/auth/oauth/google/callback", params={"code": "c", "state": q["state"][0]},
                      follow_redirects=False).headers["location"]


def test_a_new_account_through_google_counts_too(app_auth_on, monkeypatch):
    c = _client(app_auth_on)
    for _ in range(5):
        assert c.post("/api/auth/signup", json={"email": f"s-{uuid.uuid4().hex[:8]}@tm.test",
                                                "password": "Tender2026"}).status_code == 200
    loc = _google_new_account(_client(app_auth_on), monkeypatch, f"g-{uuid.uuid4().hex[:8]}@gmail.com")
    assert loc == "/login?auth_error=too_many_signups"


def test_a_name_clash_never_destroys_an_existing_company_file(app_auth_on, monkeypatch):
    import app.api.routes as routes
    from app.database import SessionLocal
    from app.models import CompanyDocument

    class Fixed:
        hex = "c1a5" * 8
    first, _ = _signup(app_auth_on)
    second, _ = _signup(app_auth_on)
    monkeypatch.setattr(routes.uuid, "uuid4", lambda: Fixed())      # both uploads get the same generated name
    assert first.post("/api/company-documents", files={"files": ("mine.txt", b"original" * 10, "text/plain")}).status_code == 200
    r = second.post("/api/company-documents", files={"files": ("theirs.txt", b"attacker", "text/plain")})
    assert r.status_code == 409
    db = SessionLocal()
    doc = db.get(CompanyDocument, "CDOC-" + ("c1a5" * 8).upper())
    db.close()
    assert Path(doc.source_path).read_bytes() == b"original" * 10


def test_rollback_failure_still_removes_the_batch_files(app_auth_on, monkeypatch):
    from sqlalchemy.orm import Session
    from app.database import get_storage_root
    import app.api.routes as routes
    c, _ = _signup(app_auth_on)
    tid = _tender(c)

    def boom(self):
        raise RuntimeError("database gone")
    monkeypatch.setattr(Session, "commit", boom)
    monkeypatch.setattr(Session, "rollback", boom)
    with pytest.raises(RuntimeError):
        c.post(f"/api/tenders/{tid}/documents", files={"files": ("ok.txt", b"o" * 500, "text/plain")})
    monkeypatch.undo()
    assert not any(p.is_file() for p in (get_storage_root() / tid).glob("*"))
    assert routes._ACCOUNT_LOCKS == {}                     # the account lock was released and dropped


def test_account_locks_do_not_pile_up(app_auth_on):
    import app.api.routes as routes
    for _ in range(3):
        c, _ = _signup(app_auth_on)
        tid = _tender(c)
        c.post(f"/api/tenders/{tid}/documents", files={"files": ("x.txt", b"x", "text/plain")})
    assert routes._ACCOUNT_LOCKS == {}


def test_derived_data_counts_against_the_quota(app_auth_on, monkeypatch):
    import app.api.routes as routes
    from app.pipeline.checkpoint import cache_dir
    monkeypatch.setattr(routes, "_account_quota_bytes", lambda: 2500)
    c, _ = _signup(app_auth_on)
    tid = _tender(c)
    assert c.post(f"/api/tenders/{tid}/documents", files={"files": ("a.txt", b"a" * 500, "text/plain")}).status_code == 200
    cache_dir(tid).mkdir(parents=True, exist_ok=True)
    (cache_dir(tid) / "ai-v1-model.jsonl").write_bytes(b"{}" * 700)       # 1400 bytes of AI answers
    r = c.post(f"/api/tenders/{tid}/documents", files={"files": ("b.txt", b"b" * 700, "text/plain")})
    assert r.status_code == 413                                          # 500 + 1400 + 700 > 2500


def test_a_failed_database_gives_the_sign_up_slot_back(app_auth_on, monkeypatch):
    import app.auth as auth

    def no_db():
        raise RuntimeError("database gone")
    monkeypatch.setattr(auth, "_db", no_db)
    c = _client(app_auth_on)
    with pytest.raises(RuntimeError):
        c.post("/api/auth/signup", json={"email": f"d-{uuid.uuid4().hex[:8]}@tm.test", "password": "Tender2026"})
    assert auth._signup_hits.get("testclient", []) == []


def test_deleting_documents_removes_their_extracted_text(app_auth_on):
    from app.pipeline.checkpoint import _extraction_path, cache_dir, file_digest
    from app.database import SessionLocal
    from app.models import TenderDocument
    c, _ = _signup(app_auth_on)
    tid = _tender(c)
    ids = [c.post(f"/api/tenders/{tid}/documents", files={"files": (n, n.encode() * 50, "text/plain")}).json()["documents"][0]["id"]
           for n in ("a.txt", "b.txt")]
    db = SessionLocal()
    paths = {d.id: Path(d.source_path) for d in db.query(TenderDocument).filter(TenderDocument.tender_id == tid)}
    db.close()
    cache_dir(tid).mkdir(parents=True, exist_ok=True)
    caches = {i: _extraction_path(tid, file_digest(paths[i])) for i in ids}
    for p in caches.values():
        p.write_text("{}", encoding="utf-8")
    (cache_dir(tid) / "ai-v1-x.jsonl").write_text("{}", encoding="utf-8")
    assert c.delete(f"/api/tenders/{tid}/documents/{ids[0]}").status_code == 200
    assert not caches[ids[0]].exists() and caches[ids[1]].exists()
    assert c.delete(f"/api/tenders/{tid}/documents").status_code == 200
    assert not cache_dir(tid).exists()                     # nothing left to use the AI cache either


# ------------------------------------------------------------------ (c)
def test_an_owned_tender_is_never_judged_by_the_admins_capabilities(monkeypatch):
    monkeypatch.setenv("TENDERMIND_AUTH_EMAIL", ADMIN_EMAIL)
    from app.database import SessionLocal, init_db
    from app.eligibility import capability_for
    from app.models import CompanyCapability, Tender
    init_db()
    db = SessionLocal()
    try:
        if not db.get(CompanyCapability, ADMIN_EMAIL):
            db.add(CompanyCapability(id=ADMIN_EMAIL, countries=["Admin-Land"], work_types=["substation"]))
        owned = Tender(id=f"T15-{uuid.uuid4().hex[:8]}", title="Owned", owner_email=f"o-{uuid.uuid4().hex[:6]}@tm.test")
        legacy = Tender(id=f"T15-{uuid.uuid4().hex[:8]}", title="Before accounts", owner_email=None)
        db.add_all([owned, legacy])
        db.commit()
        assert capability_for(db, owned) is None                       # its owner has no profile yet
        assert capability_for(db, legacy).id == ADMIN_EMAIL             # pre-account data stays the admin's
    finally:
        db.close()


def test_saved_results_that_quote_another_accounts_capabilities_are_cleared():
    from app.database import SessionLocal, init_db
    from app.eligibility import clear_foreign_capability_results
    from app.models import CompanyCapability, EligibilityResult, Tender
    init_db()
    db = SessionLocal()
    try:
        leaked = Tender(id=f"T15-{uuid.uuid4().hex[:8]}", title="L", owner_email=f"n-{uuid.uuid4().hex[:6]}@tm.test")
        own_email = f"p-{uuid.uuid4().hex[:6]}@tm.test"
        own = Tender(id=f"T15-{uuid.uuid4().hex[:8]}", title="O", owner_email=own_email)
        db.add_all([leaked, own, CompanyCapability(id=own_email, countries=["Egypt"])])
        admin_check = [{"key": "country", "status": "FAIL", "detail": "Company works in: Admin-Land"}]
        db.add(EligibilityResult(tender_id=leaked.id, status="INELIGIBLE", checks=admin_check,
                                 override_by="boss@tm.test", override_reason="continue"))
        db.add(EligibilityResult(tender_id=own.id, status="ELIGIBLE", checks=[{"key": "country", "status": "PASS"}],
                                 capability_source=own_email))
        # Leaked before the fix, and the owner created a profile afterwards: provenance unknown.
        late_email = f"q-{uuid.uuid4().hex[:6]}@tm.test"
        late = Tender(id=f"T15-{uuid.uuid4().hex[:8]}", title="Late", owner_email=late_email)
        db.add_all([late, CompanyCapability(id=late_email, countries=["Egypt"])])
        db.add(EligibilityResult(tender_id=late.id, status="INELIGIBLE", checks=admin_check))
        db.commit()
        changed = clear_foreign_capability_results(db)
        assert leaked.id in changed and late.id in changed and own.id not in changed
        a, b = db.get(EligibilityResult, leaked.id), db.get(EligibilityResult, own.id)
        assert (a.status, a.checks, a.override_by) == ("SKIPPED", [], "boss@tm.test")
        assert b.status == "ELIGIBLE" and b.checks                      # computed from its owner's own profile
        assert db.get(EligibilityResult, late.id).checks == []
        assert not {leaked.id, late.id, own.id} & set(clear_foreign_capability_results(db))   # once
    finally:
        db.close()


# ------------------------------------------------------------------ (d)
def _client_seen(trusted: str, peer: str, xff: str) -> str:
    """Run uvicorn's proxy-header middleware as the Docker image configures it."""
    import asyncio
    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
    seen = {}

    async def app(scope, receive, send):
        seen["client"] = scope["client"][0]
    mw = ProxyHeadersMiddleware(app, trusted_hosts=trusted)
    scope = {"type": "http", "client": (peer, 5000), "scheme": "http",
             "headers": [(b"x-forwarded-for", xff.encode())]}
    asyncio.run(mw(scope, None, None))
    return seen["client"]


def test_a_client_cannot_choose_its_own_address_behind_the_proxy():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    trusted = re.search(r"FORWARDED_ALLOW_IPS=(\S+)", dockerfile).group(1)
    assert "--forwarded-allow-ips" not in dockerfile                   # the env value is what uvicorn uses
    subnet = re.search(r"subnet:\s*(\S+)", (ROOT / "docker-compose.yml").read_text(encoding="utf-8")).group(1)
    assert subnet in trusted.split(",")                                # the pinned proxy network is the trusted one
    caddy = subnet.rsplit(".", 1)[0] + ".5"
    forged = "6.6.6.6, 203.0.113.7"                                    # appending proxy: forged value first
    assert _client_seen(trusted, caddy, forged) == "203.0.113.7"       # the address the proxy saw
    assert _client_seen("*", caddy, forged) == "6.6.6.6"               # control: what "*" did
    assert _client_seen(trusted, caddy, "203.0.113.7") == "203.0.113.7"  # Caddy overwrites the header
    # A LAN machine talking to the app directly (or through an appending proxy)
    # is not a trusted proxy, so its forged header is ignored.
    assert _client_seen(trusted, "192.168.1.20", "6.6.6.6") == "192.168.1.20"
    assert _client_seen(trusted, caddy, "6.6.6.6, 192.168.1.20") == "192.168.1.20"
