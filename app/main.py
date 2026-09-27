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
        _fail_interrupted_jobs(db)
    finally:
        db.close()


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


app = FastAPI(
    title="TenderMind",
    version="0.2.0",
    lifespan=lifespan,
)

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
    return {"status": "ok", "tender": "SA/2018/HV2"}

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
