"""Stage 5B — run a real tender folder through the live API and summarize.

Usage:
  python evaluation/stage5b/run_real_tender.py <base_url> <tender_id> <folder> [file1,file2,...]
Uploads every file in <folder> (or only the listed ones), starts processing,
polls to a terminal state, then prints and saves a JSON summary to
evaluation/stage5b/<tender_id>_summary.json. Talks to the API only.
"""
import collections
import json
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = Path(__file__).parent


def main(base, tid, folder, only=None, email=None, password=None, max_wait_s=6 * 3600):
    s = requests.Session()
    if email:
        s.post(f"{base}/api/auth/login", json={"email": email, "password": password}).raise_for_status()
    r = s.post(f"{base}/api/tenders", json={"id": tid, "title": f"{Path(folder).name}", "client": "real-tender-test", "location": "Egypt"})
    print("create", r.status_code)
    files = sorted(p for p in Path(folder).iterdir() if p.is_file())
    if only:
        files = [p for p in files if p.name in only]
    t_up = time.time()
    upload = []
    for p in files:  # one request per file: a failed file must not block the rest
        with open(p, "rb") as fh:
            r = s.post(f"{base}/api/tenders/{tid}/documents", files=[("files", (p.name, fh))], timeout=900)
        doc = (r.json().get("documents") or [{}])[0] if r.status_code == 200 else {}
        upload.append({"file": p.name, "mb": round(p.stat().st_size / 1048576, 1), "http": r.status_code,
                       "doc_type": doc.get("doc_type"), "error": None if r.status_code == 200 else r.text[:200]})
        print(f"  upload {r.status_code} {doc.get('doc_type', '-'):12s} {p.name}")
    upload_s = time.time() - t_up
    t0 = time.time()
    r = s.post(f"{base}/api/tenders/{tid}/process")
    jid = r.json()["job_id"]
    last = None
    while True:
        j = s.get(f"{base}/api/processing-jobs/{jid}").json()
        stage = (j.get("status"), j.get("current_stage"))
        if stage != last:
            print(f"  [{time.time() - t0:6.0f}s] {stage[0]} {stage[1]}", flush=True)
            last = stage
        if j.get("status") in ("COMPLETED", "FAILED", "PARTIAL") or time.time() - t0 > max_wait_s:
            break
        time.sleep(10)
    wall = time.time() - t0
    a = s.get(f"{base}/api/tenders/{tid}/analysis").json()
    df = a.get("derived_features") or {}
    reqs = a.get("requirements") or []
    summary = {
        "tender_id": tid, "folder": str(folder), "job_status": j.get("status"),
        "last_error": (j.get("last_error") or "")[:500], "upload_s": round(upload_s),
        "processing_s": round(wall), "model": j.get("model"), "prompt_version": j.get("prompt_version"),
        "upload": upload,
        "documents": [{k: d.get(k) for k in ("filename", "extraction_status", "page_count", "text_length", "error")}
                      for d in a.get("documents") or []],
        "requirements": len(reqs), "evidence": len(a.get("evidence") or []),
        "categories": collections.Counter(r.get("category") for r in reqs).most_common(),
        "with_provenance": sum(1 for r in reqs if r.get("source_document") and r.get("page_number")),
        "deadlines": len(a.get("deadlines") or []), "commercial_terms": bool(a.get("commercial") or a.get("commercial_terms")),
        "risks": len(a.get("risks") or []),
        "gaps": len(df.get("gaps") or []), "ambiguities": len(df.get("ambiguities") or []),
        "telemetry": {k: (df.get("telemetry") or {}).get(k) for k in
                      ("model_call_count", "success_count", "failure_count", "timeout_count",
                       "avg_latency_s", "total_wall_s", "max_workers", "candidates_sent_to_ai")},
        "sample_requirements": [{k: r.get(k) for k in ("requirement_id", "category", "summary", "requirement",
                                                         "source_document", "page_number")} for r in reqs[:8]],
    }
    (OUT / f"{tid}_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("upload", "documents", "sample_requirements")},
                     ensure_ascii=False, indent=1))
    return summary


if __name__ == "__main__":
    only = sys.argv[4].split(",") if len(sys.argv) > 4 and sys.argv[4] else None
    main(sys.argv[1], sys.argv[2], sys.argv[3], only)
