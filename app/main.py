from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import init_db
from app.api.routes import router
import os

app = FastAPI(title="TenderMind Test001 - Sarai 220/22kV GIS Substation", version="0.1.0")

@app.on_event("startup")
def startup():
    init_db()
    # ensure seed exists — if no tender, run seed
    from app.database import SessionLocal
    from app.models import Tender
    db = SessionLocal()
    try:
        if not db.query(Tender).filter(Tender.id == "SA/2018/HV2").first():
            from app.seed import seed
            seed()
    finally:
        db.close()

app.include_router(router, prefix="/api")

# Serve frontend static
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

@app.get("/")
def root():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "TenderMind Test001 API", "docs": "/docs", "tender": "SA/2018/HV2"}

@app.get("/health")
def health():
    return {"status": "ok", "tender": "SA/2018/HV2"}
