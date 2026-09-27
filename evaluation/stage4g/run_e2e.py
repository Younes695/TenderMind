"""Stage 4G — fresh-tender live E2E (real server, real pipeline, real LLM).

Flow: create tender -> upload fixture files -> process -> poll -> analysis ->
validate every section -> record timings/artifacts. Run against a uvicorn
server started with isolated DB/storage env + TENDERMIND_TWO_STAGE_LLM=1.

Usage (from repo root, server already running on :8000):
  python evaluation/stage4g/run_e2e.py
Writes: fresh_tender_e2e.json, stage_timings.json, ai_call_budget.json,
        provenance_validation.json, structured_validation.json
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

BASE = "http://localhost:8000"
SRC = Path(r"C:\Users\EgyTech\Desktop\03- 6th October Northern Extensions Substations")
FILES = ["Clarification 1.pdf", "Power Transformer Specs.pdf", "Addendum.zip"]
OUT = Path(__file__).parent
T0 = time.time()
stamps = {}


def stamp(name):
    stamps[name] = round(time.time() - T0, 1)


def sha1(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main():
    rec = {"tender_id": "OCT-6-FRESH-4H2", "steps": []}

    def step(name, fn):
        t = time.time()
        out = fn()
        dt = round(time.time() - t, 1)
        rec["steps"].append({"step": name, "wall_s": dt})
        print(f"[{dt:6.1f}s] {name}")
        return out

    manifest = {"tender": "03- 6th October Northern Extensions Substations (fresh, non-Mobile/Sarai)",
                "files": []}
    for fn in FILES:
        p = SRC / fn
        manifest["files"].append({"filename": fn, "bytes": p.stat().st_size,
                                  "sha16": sha1(p)})
    (OUT / "fresh_tender_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    r = step("create tender", lambda: requests.post(
        f"{BASE}/api/tenders", json={"id": rec["tender_id"], "title": "6th October Pilot",
                                     "client": "EETC", "location": "6th October"})).json()
    assert r["id"] == rec["tender_id"], r
    stamp("created")

    for fn in FILES:
        p = SRC / fn
        with open(p, "rb") as f:
            rr = step(f"upload {fn}", lambda: requests.post(
                f"{BASE}/api/tenders/{rec['tender_id']}/documents",
                files={"files": (fn, f, "application/octet-stream")})).json()
        assert "documents" in rr or "document" in rr or rr.get("count", 1) >= 1, rr
    stamp("uploaded")

    docs = step("list documents", lambda: requests.get(
        f"{BASE}/api/tenders/{rec['tender_id']}/documents").json())
    rec["documents"] = docs
    assert docs["count"] == 3, docs

    # idempotency probe: second process call while active must 409 (checked after start)
    job = step("start process", lambda: requests.post(
        f"{BASE}/api/tenders/{rec['tender_id']}/process").json())
    rec["job_id"] = job["job_id"]
    stamp("processing_started")

    dup = requests.post(f"{BASE}/api/tenders/{rec['tender_id']}/process")
    rec["duplicate_process_status"] = dup.status_code
    print(f"duplicate POST /process -> {dup.status_code} (expect 409 while active)")

    t_poll = time.time()
    terminal = None
    while time.time() - t_poll < 2400:
        terminal = requests.get(f"{BASE}/api/processing-jobs/{rec['job_id']}").json()
        if terminal["status"] not in ("QUEUED", "PROCESSING"):
            break
        time.sleep(10)
    rec["job_terminal"] = terminal
    rec["poll_wall_s"] = round(time.time() - t_poll, 1)
    stamp("terminal")
    print(f"terminal: {terminal['status']} stage={terminal['current_stage']} "
          f"docs={terminal['documents_processed']}/{terminal['documents_total']} "
          f"failed={terminal['documents_failed']} unsupported={terminal['documents_unsupported']}")
    print(f"stage_history: {[(h['stage'], h['status']) for h in terminal.get('stage_history', [])]}")

    analysis = step("get analysis", lambda: requests.get(
        f"{BASE}/api/tenders/{rec['tender_id']}/analysis").json())
    # refresh/reopen: second retrieval must be identical (persisted, not in-memory)
    analysis2 = step("get analysis again (persistence)", lambda: requests.get(
        f"{BASE}/api/tenders/{rec['tender_id']}/analysis").json())
    rec["persistence_identical"] = (json.dumps(analysis, sort_keys=True, default=str)
                                    == json.dumps(analysis2, sort_keys=True, default=str))
    print("persistence identical:", rec["persistence_identical"])

    reqs, evs = analysis.get("requirements", []), analysis.get("evidence", [])
    df = analysis.get("derived_features", {}) or {}
    rec["counts"] = {"requirements": len(reqs), "evidence": len(evs),
                     "documents": len(analysis.get("documents", [])),
                     "deadlines": len(analysis.get("deadlines", [])),
                     "gaps": len(df.get("gaps", [])), "ambiguities": len(df.get("ambiguities", [])),
                     "conflicts": len(df.get("conflicts", [])),
                     "risk_signals": len(df.get("risk_signals", [])),
                     "clarifications": len(df.get("clarifications", [])),
                     "addenda": len(df.get("addenda", [])),
                     "synthesis": bool(df.get("synthesis"))}
    from collections import Counter
    rec["categories"] = dict(Counter(r.get("category") for r in reqs))
    rec["commercial"] = {k: (df.get("commercial_facts", {}) or {}).get(k) for k in
                         ("currency", "payment_terms", "bid_security", "validity")}
    rec["schedule_count"] = len(df.get("schedule_facts", []))
    print("counts:", json.dumps(rec["counts"], indent=1))
    print("categories:", rec["categories"])

    # provenance validation: every req has doc/page/text; every ev links same doc/page
    prov_ok, prov_bad = 0, []
    rids = {r.get("requirement_id") for r in reqs}
    for r in reqs:
        if r.get("source_document") and r.get("page_number") and r.get("source_text"):
            prov_ok += 1
        else:
            prov_bad.append(r.get("requirement_id"))
    ev_ok = 0
    for e in evs:
        rq = next((r for r in reqs if r.get("requirement_id") == e.get("requirement_id")), None)
        if rq and e.get("source_document") == rq.get("source_document") and \
                e.get("page_number") == rq.get("page_number"):
            ev_ok += 1
        else:
            prov_bad.append(e.get("evidence_id"))
    rec["provenance"] = {"req_valid": prov_ok, "req_total": len(reqs),
                         "ev_valid": ev_ok, "ev_total": len(evs), "violations": prov_bad}
    (OUT / "provenance_validation.json").write_text(
        json.dumps(rec["provenance"], indent=2), encoding="utf-8")

    # no Mobile/Sarai fixture leakage: "mobile substations" as equipment words is
    # legitimate here (6th October IS a mobile-substations tender); leakage means
    # development-fixture paths/identifiers from other tenders.
    blob = json.dumps(analysis, ensure_ascii=False).lower()
    rec["leakage"] = {m: (m in blob) for m in
                      ("02- mobile", "01- sarai", "sa-2018", "form d.xls",
                       "tender price schedule", "motawreen")}
    print("provenance:", rec["provenance"], "leakage:", rec["leakage"])

    # AI budget from persisted intelligence telemetry (preferred) or processing block
    _tel = ((analysis.get("derived_features", {}) or {}).get("telemetry") or {})
    proc = analysis.get("processing", {}) or {}
    src = _tel if _tel.get("model_call_count") is not None else proc
    rec["ai_budget"] = {k: src.get(k) for k in
                        ("candidates_generated", "candidates_compressed",
                         "candidates_structured_covered", "candidates_sent_to_ai",
                         "model_call_count", "success_count", "failure_count",
                         "requirements_final", "evidence_final", "pipeline_version", "model")}
    rec["ai_budget"]["pipeline_version"] = (analysis.get("pipeline_version")
                                            or proc.get("pipeline_version"))
    rec["ai_budget"]["model"] = analysis.get("model") or proc.get("model")
    (OUT / "ai_call_budget.json").write_text(json.dumps(rec["ai_budget"], indent=2), encoding="utf-8")
    (OUT / "stage_timings.json").write_text(
        json.dumps({"step_walls": rec["steps"], "stamps": stamps,
                    "stage_history": terminal.get("stage_history", [])}, indent=2), encoding="utf-8")
    (OUT / "structured_validation.json").write_text(json.dumps(
        {"note": "6th October fixture has no XLSX (honest absence); structured path validated "
                 "via generic unit tests (4E/4F) + Mobile BOQ experiment (4F: 128 line items)",
         "fixture_xlsx": False, "unsupported_present": True}, indent=2), encoding="utf-8")
    (OUT / "fresh_tender_e2e.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("E2E complete. Total wall:", round(time.time() - T0, 1), "s")


if __name__ == "__main__":
    main()
