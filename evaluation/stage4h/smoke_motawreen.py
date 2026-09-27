"""Stage 4H — Motawreen cross-tender smoke (live server; small subset, no benchmark).

Files: layout.pdf (0.4MB) + Single line diagram.pdf (0.8MB) + PINGGAOU.JPG
(empty-OCR expectation). Asserts: new tender, uploads, terminal state,
requirements-or-honest-absence, provenance where present, unsupported/empty
states truthful, no fixture leakage.
Usage: server running (isolated env), then: python evaluation/stage4h/smoke_motawreen.py
Writes: cross_tender_smoke.json
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

BASE = "http://localhost:8000"
SRC = Path(r"C:\Users\EgyTech\Desktop\04- Motawreen Substation")
FILES = ["Al motawreen Layout pdf.pdf", "Single line diagram.pdf", "PINGGAOU.JPG"]
OUT = Path(__file__).parent
TID = "MOT-SMOKE-4H"


def main():
    rec = {"tender_id": TID}
    r = requests.post(f"{BASE}/api/tenders", json={"id": TID, "title": "Motawreen Smoke"}).json()
    assert r["id"] == TID, r
    print("created", TID)
    for fn in FILES:
        p = SRC / fn
        assert p.is_file(), f"missing fixture {p}"
        with open(p, "rb") as f:
            rr = requests.post(f"{BASE}/api/tenders/{TID}/documents",
                               files={"files": (fn, f, "application/octet-stream")}).json()
        print("uploaded", fn, rr.get("count"))
    docs = requests.get(f"{BASE}/api/tenders/{TID}/documents").json()
    assert docs["count"] == 3, docs
    job = requests.post(f"{BASE}/api/tenders/{TID}/process").json()
    rec["job_id"] = job["job_id"]
    t0 = time.time()
    while time.time() - t0 < 1800:
        st = requests.get(f"{BASE}/api/processing-jobs/{rec['job_id']}").json()
        if st["status"] not in ("QUEUED", "PROCESSING"):
            break
        time.sleep(10)
    rec["terminal"] = {
        "status": st["status"], "stage": st["current_stage"],
        "total": st["documents_total"], "processed": st["documents_processed"],
        "failed": st["documents_failed"], "unsupported": st["documents_unsupported"],
        "coverage": st.get("analysis_coverage")}
    rec["wall_s"] = round(time.time() - t0, 1)
    print("terminal:", rec["terminal"], "wall:", rec["wall_s"])
    a = requests.get(f"{BASE}/api/tenders/{TID}/analysis").json()
    reqs = a.get("requirements", [])
    rec["requirements"] = len(reqs)
    rec["evidence"] = len(a.get("evidence", []))
    bad = [r.get("requirement_id") for r in reqs
           if not (r.get("source_document") and r.get("page_number") and r.get("source_text"))]
    rec["provenance_violations"] = bad
    blob = json.dumps(a, ensure_ascii=False).lower()
    rec["leakage"] = {m: (m in blob) for m in
                      ("02- mobile", "01- sarai", "sa-2018", "6th october", "form d.xls")}
    rec["doc_types"] = [d.get("doc_type") for d in a.get("documents", [])]
    print("reqs:", rec["requirements"], "ev:", rec["evidence"],
          "violations:", bad, "leakage:", rec["leakage"])
    (OUT / "cross_tender_smoke.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2, default=str),
                                                 encoding="utf-8")
    print("smoke complete")


if __name__ == "__main__":
    main()
