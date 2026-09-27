"""
Stage 3 — Mobile E2E Runner
Creates Mobile-Stage3 tender, uploads subset of real Mobile files, processes, retrieves analysis.
Subset: Commercial forms.txt, Price schedules xlsx, Drawings.pdf, and Vol I first 20 pages as separate PDF to keep time reasonable.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding='utf-8')

import time
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, get_storage_root, init_db
from app.models import TenderDocument, TenderAnalysis
import fitz

# Setup
MOBILE_ROOT = Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations")
# Choose subset
SUBSET_FILES = [
    MOBILE_ROOT / "Commercial forms.txt",
    MOBILE_ROOT / "Price schedules of 6th October northern Extention 22-22-22 KV GIS SS.xlsx",
    MOBILE_ROOT / "Drawings.pdf",
    MOBILE_ROOT / "Tender Price Schedule- التوسعات الشمالية.pdf",
]

# Also create a 20-page subset of Vol I to avoid 172 pages full
VOL1 = MOBILE_ROOT / "Vol I - Tender Document.pdf"
SUBSET_VOL1 = None
if VOL1.exists():
    # Create temp subset
    tmp_vol1 = Path(tempfile.gettempdir()) / "Vol I subset 20pages.pdf"
    doc = fitz.open(str(VOL1))
    new = fitz.open()
    for i in range(min(20, len(doc))):
        new.insert_pdf(doc, from_page=i, to_page=i)
    new.save(str(tmp_vol1))
    new.close()
    doc.close()
    SUBSET_FILES.append(tmp_vol1)
    SUBSET_VOL1 = tmp_vol1
    print(f"Created subset Vol I 20 pages: {tmp_vol1} ({tmp_vol1.stat().st_size/1024:.1f} KB)")

print(f"Subset files: {len(SUBSET_FILES)}")
for f in SUBSET_FILES:
    print(f"  {f.name} — {f.stat().st_size/1024:.1f} KB — exists {f.exists()}")

# Setup temp storage
tmp_storage = Path(tempfile.mkdtemp(prefix="stage3_mobile_"))
os.environ["TENDERMIND_STORAGE_ROOT"] = str(tmp_storage)
if "TENDER_SARAI_PATH" in os.environ:
    del os.environ["TENDER_SARAI_PATH"]
Base.metadata.drop_all(bind=engine)
init_db()
client = TestClient(app)

tender_id = "Mobile-Stage3-001"
print(f"\n=== Creating tender {tender_id} ===")
resp = client.post("/api/tenders", json={"id": tender_id, "title": "Mobile Stage3 Validation — 6 October Northern Extensions", "client": "NUCA", "location": "6th October City"})
print(f"Create: {resp.status_code} {resp.json()}")
assert resp.status_code == 200

print(f"\n=== Uploading {len(SUBSET_FILES)} files ===")
files = []
for p in SUBSET_FILES:
    # Determine mime
    ext = p.suffix.lower()
    mime = "application/octet-stream"
    if ext == ".pdf": mime = "application/pdf"
    elif ext == ".txt": mime = "text/plain"
    elif ext == ".xlsx": mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    files.append(("files", (p.name, p.read_bytes(), mime)))

resp2 = client.post(f"/api/tenders/{tender_id}/documents", files=files)
print(f"Upload: {resp2.status_code}")
if resp2.status_code != 200:
    print(resp2.text)
    sys.exit(1)
data2 = resp2.json()
print(f"Uploaded {data2['count']} docs")
for d in data2["documents"]:
    print(f"  {d['filename']} — {d['doc_type']} — {d['size']} bytes — {d['path']}")

# Verify storage
storage_root = get_storage_root()
print(f"\nStorage root: {storage_root}")
for d in data2["documents"]:
    p = Path(d["path"])
    print(f"  Exists {p.exists()} — {p}")

# Verify DB
from app.database import SessionLocal
db = SessionLocal()
docs = db.query(TenderDocument).filter(TenderDocument.tender_id == tender_id).all()
print(f"\nTenderDocument in DB: {len(docs)}")
for d in docs:
    print(f"  {d.id} — {d.title} — {d.doc_type} — source_path {d.source_path} exists {Path(d.source_path).exists() if d.source_path else False}")
db.close()

# Process
print(f"\n=== Starting processing ===")
t0 = time.time()
resp3 = client.post(f"/api/tenders/{tender_id}/process")
print(f"Process start: {resp3.status_code} {resp3.json()}")
job_id = resp3.json()["job_id"]

# Poll
job = None
for i in range(60):
    time.sleep(1.0)
    r = client.get(f"/api/processing-jobs/{job_id}")
    job = r.json()
    print(f"Poll {i}: {job['status']} progress {job['progress']} stage {job['current_stage']} docs {job['documents_total']}/{job['documents_processed']} unsupported {job['documents_unsupported']} failed {job['documents_failed']}")
    if job["status"] in ("COMPLETED", "PARTIAL", "FAILED"):
        break
else:
    print("Timeout")
    sys.exit(1)

duration = time.time() - t0
print(f"\nJob terminal: {job['status']} in {duration:.1f}s")
print(f"Documents: total {job['documents_total']} processed {job['documents_processed']} failed {job['documents_failed']} unsupported {job['documents_unsupported']}")
print(f"Progress {job['progress']} stage {job['current_stage']}")
if job.get("last_error"):
    print(f"Last error: {job['last_error']}")

# Analysis
print(f"\n=== Fetching analysis ===")
resp4 = client.get(f"/api/tenders/{tender_id}/analysis")
print(f"Analysis status: {resp4.status_code}")
analysis = resp4.json()
# Check if it's job status vs analysis
if "requirements" not in analysis:
    print("Analysis not ready or failed:", analysis)
    sys.exit(1)
print(f"Analysis: tender {analysis.get('tender')}")
print(f"Documents in analysis: {len(analysis.get('documents', []))}")
for d in analysis.get("documents", []):
    print(f"  {d.get('filename')} — pages {d.get('page_count')} — text_len {d.get('text_length')} — status {d.get('extraction_status')} — method {d.get('extraction_method')} — ocr {d.get('ocr_applied')}")
print(f"Requirements: {len(analysis.get('requirements', []))}")
for r in analysis.get("requirements", [])[:5]:
    print(f"  {r.get('requirement_id')} — {r.get('category')} — {r.get('summary')[:60]} — conf {r.get('confidence')} — src {r.get('source_document')}:{r.get('page_number')}")
print(f"Deadlines: {len(analysis.get('deadlines', []))} — {analysis.get('deadlines')[:2]}")
print(f"Commercial: {analysis.get('commercial')}")
print(f"Risks: {len(analysis.get('risks', []))}")
print(f"Derived: {analysis.get('derived_features')}")
print(f"Processing: {analysis.get('processing')}")

# Verify DB analysis
db = SessionLocal()
analyses = db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id).all()
print(f"\nTenderAnalysis in DB: {len(analyses)}")
if analyses:
    latest = analyses[0]
    print(f"  Latest: {latest.id} — status {latest.status} — reqs {len(latest.requirements or [])}")
db.close()

# Cleanup subset vol1
if SUBSET_VOL1 and SUBSET_VOL1.exists():
    try:
        SUBSET_VOL1.unlink()
    except: pass

# Keep tmp_storage for manual inspection? Cleanup
import shutil
# Don't delete yet, keep for report
print(f"\nStorage kept at {tmp_storage} for inspection")
# Save analysis to file for evaluation
out_path = Path(__file__).parent / "mobile_stage3_analysis.json"
import json
out_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Analysis saved to {out_path}")

# Also save job
job_path = Path(__file__).parent / "mobile_stage3_job.json"
job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Job saved to {job_path}")

print("\n=== E2E DONE ===")
