from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from pathlib import Path

# --- DATABASE_URL configurable (portable project-relative) ---
# Default is project_root/tender.db via sqlite:///<project_root>/tender.db — portable, no developer/EgyTech/AppData literal
# DATABASE_URL env var overrides; literal string contains no developer path, path is dynamic via Path(__file__)
_project_root = Path(__file__).resolve().parents[1]
_default_db_path = _project_root / "tender.db"
_default_db_url = f"sqlite:///{_default_db_path.as_posix()}"

DATABASE_URL = os.environ.get("DATABASE_URL", _default_db_url)

# Derive DB_PATH for sqlite file URLs for backwards compat / debugging
DB_PATH = str(_default_db_path)
if DATABASE_URL.startswith("sqlite"):
    try:
        _sqlite_path = DATABASE_URL.split("sqlite:///")[-1].split("?")[0]
        if _sqlite_path and _sqlite_path != ":memory:":
            DB_PATH = _sqlite_path
    except Exception:
        pass

DB_URL = DATABASE_URL

_connect_args = {"check_same_thread": False}
if DB_URL.startswith("sqlite"):
    _connect_args["timeout"] = 30  # seconds to wait for a lock instead of failing at 5
engine = create_engine(DB_URL, connect_args=_connect_args)

if DB_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        """WAL lets pages read while a processing job writes progress. In the
        default rollback-journal mode every read failed with 'database is
        locked' during a commit, and one such failure killed a 1,500-page job."""
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.execute("PRAGMA synchronous=NORMAL")
        finally:
            cur.close()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- TENDERMIND_STORAGE_ROOT configurable (single source of truth) ---
# Default: ./uploads relative to project root (one level up from app/), or env override.
# All code (routes, processing) MUST use get_storage_root() — never hardcode path.
def get_storage_root() -> Path:
    """Single source of truth for uploaded document storage."""
    env_val = os.environ.get("TENDERMIND_STORAGE_ROOT")
    if env_val:
        return Path(env_val)
    # Default: project_root/uploads (sibling to app/)
    # app/database.py -> app/ -> project root
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "uploads"

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app import models  # noqa
    Base.metadata.create_all(bind=engine)
    # Stage 1B migration: add TenderDocument.source_path if missing (sqlite, no alembic)
    try:
        with engine.connect() as conn:
            # Check if column exists via PRAGMA
            result = conn.execute(text("PRAGMA table_info(tender_documents)"))
            cols = [row[1] for row in result.fetchall()]
            if "source_path" not in cols:
                conn.execute(text("ALTER TABLE tender_documents ADD COLUMN source_path VARCHAR"))
                conn.commit()
            if "file_size" not in cols:
                conn.execute(text("ALTER TABLE tender_documents ADD COLUMN file_size FLOAT"))
                conn.commit()
            if "original_filename" not in cols:
                conn.execute(text("ALTER TABLE tender_documents ADD COLUMN original_filename VARCHAR"))
                conn.commit()
            # Stage 5G: per-account ownership (app/access.py). Existing rows stay
            # NULL = owned by the env admin only.
            for table in ("tenders", "company_documents"):
                tcols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
                if "owner_email" not in tcols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN owner_email VARCHAR"))
                    conn.commit()
            # Stage 6: tender outcome (feeds the similar-past-tenders score factor)
            tcols = [row[1] for row in conn.execute(text("PRAGMA table_info(tenders)")).fetchall()]
            if "outcome" not in tcols:
                conn.execute(text("ALTER TABLE tenders ADD COLUMN outcome VARCHAR"))
                conn.commit()
            for col, typ in (("stage", "VARCHAR"), ("submission_deadline", "DATETIME"),  # Stage 8
                             ("final_decision", "VARCHAR"), ("final_reason", "TEXT"), ("final_by", "VARCHAR"),
                             ("final_at", "DATETIME")):  # Stage 9
                if col not in tcols:
                    conn.execute(text(f"ALTER TABLE tenders ADD COLUMN {col} {typ}"))
                    conn.commit()
            pcols = [row[1] for row in conn.execute(text("PRAGMA table_info(company_profiles)")).fetchall()]
            if pcols and "account_type" not in pcols:
                conn.execute(text("ALTER TABLE company_profiles ADD COLUMN account_type VARCHAR"))
                conn.commit()
            ecols = [row[1] for row in conn.execute(text("PRAGMA table_info(eligibility_results)")).fetchall()]
            if ecols and "override_name" not in ecols:
                conn.execute(text("ALTER TABLE eligibility_results ADD COLUMN override_name VARCHAR"))
                conn.commit()
    except Exception:
        # Non-sqlite or already applied — safe to ignore, create_all handles fresh DBs
        pass
