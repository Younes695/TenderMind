from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

import tempfile
# Use temp dir to avoid space/path issues on Windows
_db_dir = os.path.join(tempfile.gettempdir(), "opencode", "tendermind")
os.makedirs(_db_dir, exist_ok=True)
DB_PATH = os.path.join(_db_dir, "tendermind.db")
DB_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app import models  # noqa
    Base.metadata.create_all(bind=engine)
