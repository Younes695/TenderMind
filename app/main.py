import os as _os

# Load .env (next to the project root) before anything reads configuration:
# app.database reads DATABASE_URL at import time. Real environment variables
# always win (override=False). Tests opt out so a developer's .env (e.g.
# TENDERMIND_ENV=production) can never change test behaviour.
if not _os.environ.get("TENDERMIND_SKIP_DOTENV"):
    from pathlib import Path as _Path
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_Path(__file__).resolve().parents[1] / ".env", override=False)

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.database import init_db
from app.api.routes import router
from app.auth import (
    auth_router,
    validate_auth_config,
    _session_secret,
    cookie_secure,
)

import os
from pathlib import Path

def _ensure_seed():
    init_db()
    # ensure Sarai seed exists — only if SA-2018-HV2 missing (hyphen, not slash)
    # Stage 1B: never destructive; seed() is now idempotent and preserves user tenders
    from app.database import SessionLocal
    from app.models import Tender
    db = SessionLocal()
    try:
        if not db.query(Tender).filter(Tender.id == "SA-2018-HV2").first():
            from app.seed import seed
            seed()
    finally:
        db.close()
    # Stage 5H: a job cut off by a restart continues by itself (files and AI
    # answers already done come back from checkpoints), and a watchdog resumes
    # any job whose worker dies without recording a result.
    from app.processing import resume_interrupted, start_watchdog
    resume_interrupted(reason="the server stopped")
    if _os.environ.get("TENDERMIND_WATCHDOG", "1").strip() != "0":
        start_watchdog()
    if _os.environ.get("TENDERMIND_NEWS_ENABLED", "1").strip() != "0":
        from app.news import start_refresher
        start_refresher()


def _fail_interrupted_jobs(db) -> int:
    """Jobs run inside this process, so any job still QUEUED/PROCESSING at startup
    died with the previous process (crash, restart). Without this they stay
    'PROCESSING' forever and block reprocessing and file removal."""
    from datetime import datetime
    from app.models import ProcessingJob
    stuck = db.query(ProcessingJob).filter(ProcessingJob.status.in_(["QUEUED", "PROCESSING"])).all()
    for job in stuck:
        job.status = "FAILED"
        job.last_error = "Interrupted: the server stopped while this job was running. Start processing again."
        job.completed_at = datetime.utcnow()
    if stuck:
        db.commit()
    return len(stuck)


@asynccontextmanager
async def lifespan(_app):
    _ensure_seed()
    yield


_PRODUCTION = os.environ.get("TENDERMIND_ENV", "development").strip().lower() in {"prod", "production"}

# Interactive API docs list every endpoint; off in production unless asked for.
_docs = (not _PRODUCTION) or os.environ.get("TENDERMIND_API_DOCS", "").strip().lower() in {"1", "true", "yes"}

app = FastAPI(
    title="TenderMind",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

# Browser hardening headers on every response. The CSP allows the built SPA
# (same-origin scripts/styles, inline styles used by React, images incl. data:
# URIs); OAuth sign-in is a full-page redirect so no third-party frames/scripts.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' "
                                "https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; "
                                "img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; "
                                "base-uri 'self'; form-action 'self'"),
}


@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    for k, v in _SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if _PRODUCTION:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

# CORS — defaults cover local Vite dev; production origins come from
# TENDERMIND_CORS_ORIGINS (comma-separated, e.g. "https://tendermind.example.com").
# Only matters when frontend and backend are on different origins; when the
# backend serves the built frontend itself (see below) requests are same-origin
# and CORS is not on the critical path.
_default_cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_extra_cors_origins = [
    o.strip() for o in os.environ.get("TENDERMIND_CORS_ORIGINS", "").split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_cors_origins + _extra_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

validate_auth_config()

app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret(),
    session_cookie="tendermind_session",
    max_age=8 * 60 * 60,
    same_site="lax",
    https_only=cookie_secure(),
)

app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api")

# Serve the built React app (frontend/dist — output of `npm run build`).
# IMPORTANT: this must be the *built* bundle, not frontend/index.html — that
# file only works via the Vite dev server (it imports raw /src/main.jsx,
# which a browser cannot resolve on its own). Run `npm run build` in
# frontend/ before starting this app in production; frontend/dist/ must exist.
_frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
_dist_index = os.path.join(_frontend_dist, "index.html")

if os.path.isdir(_frontend_dist):
    # Vite's build references hashed files as /assets/... — serve them directly.
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_frontend_dist, "assets")),
        name="frontend-assets",
    )

@app.get("/health")
def health():
    """Liveness + readiness: the database answers a query."""
    from sqlalchemy import text
    from app.database import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse({"status": "error", "database": "unavailable"}, status_code=503)
    return {"status": "ok", "database": "ok", "tender": "SA/2018/HV2"}

# SPA fallback: any path that isn't /api/*, /docs, /openapi.json, /health or a
# built asset returns index.html so React Router can handle client-side
# routes (e.g. /dashboard, /tenders/SA-2018-HV2) on a hard refresh or direct
# link. Registered last so it never shadows the routers above.
@app.get("/{full_path:path}")
def spa(full_path: str):
    # Unknown API paths must stay a JSON 404, not silently return the HTML shell.
    if full_path == "api" or full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    if os.path.exists(_dist_index):
        # index.html must never be cached: it names the current hashed bundle.
        # Without this, browsers kept serving the previous build after every
        # deploy (new pages/buttons "missing" until a hard refresh).
        return FileResponse(_dist_index, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
    return {
        "message": "Frontend build not found — run `npm run build` in frontend/",
        "docs": "/docs",
    }
