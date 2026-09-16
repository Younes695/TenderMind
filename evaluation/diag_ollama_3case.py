"""
Temporary diagnostic — Ollama 3-case trace (read-only, no production change).
Runs ONLY first 3 unlabeled pairs through CURRENT OllamaMatcher production path.
Prints per-case: req/ev IDs, hard-rule fired, HTTP called, raw JSON, parsed output,
derived IDs, final MatcherOutput, latency. Gold compared ONLY AFTER all 3 predictions.
Localhost only, no OpenAI/Azure, $0.
"""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.matcher_benchmark import build_unlabeled_pairs
from app.matchers.ollama_matcher import OllamaMatcher, get_ollama_model
from app.matchers.base import MatcherInput
import requests as _req

print("=== DIAG Ollama 3-case trace — production path, no behavior change ===", flush=True)
print(f"Model: {get_ollama_model()} (current OllamaMatcher)", flush=True)

pairs = build_unlabeled_pairs()
first3 = pairs[:3]
print(f"First 3 unlabeled pairs (order as built):", flush=True)
for i, p in enumerate(first3):
    print(f"  [{i}] {p['requirement_id']} x {p['evidence_id']} — {p['source_document']} {p['page_or_section']}", flush=True)
    assert "gold_expected_status" not in p and "gold_evidence_supported" not in p, "gold leaked into input!"

matcher = OllamaMatcher()
print(f"Matcher: {matcher.name} v{matcher.version}, timeout={matcher.timeout}s", flush=True)

# Wrap requests.post/get to count + capture raw response (still calls through, localhost only)
orig_post = _req.post
orig_get = _req.get
calls = []
raws = []

def counting_post(*a, **k):
    import time as _t
    t0 = _t.time()
    r = orig_post(*a, **k)
    dt = _t.time() - t0
    url = a[0] if a else k.get("url", "")
    try:
        body = r.text if hasattr(r, "text") else ""
    except Exception:
        body = ""
    calls.append({"method": "POST", "url": str(url)[:120], "status": getattr(r, "status_code", "?"), "elapsed": round(dt, 2), "resp_len": len(body)})
    raws.append(body)
    return r

def counting_get(*a, **k):
    import time as _t
    t0 = _t.time()
    r = orig_get(*a, **k)
    dt = _t.time() - t0
    url = a[0] if a else k.get("url", "")
    # Only count Ollama endpoint calls (avoid counting other)
    if "11434" in str(url):
        calls.append({"method": "GET", "url": str(url)[:120], "status": getattr(r, "status_code", "?"), "elapsed": round(dt, 2), "resp_len": len(getattr(r, "text", "") or "")})
    return r

import requests as reqmod
reqmod.post = counting_post
reqmod.get = counting_get

predictions = []
try:
    for idx, p in enumerate(first3):
        print(f"\n--- CASE {idx} BEFORE ---", flush=True)
        print(f"1. Requirement ID: {p['requirement_id']}", flush=True)
        print(f"2. Evidence ID supplied: {p['evidence_id']}", flush=True)
        before = len(calls)
        t0 = time.time()
        inp = MatcherInput(
            requirement_id=p["requirement_id"], requirement_text=p["requirement_text"],
            requirement_category=p["requirement_category"], requirement_type=p["requirement_type"],
            mandatory=p["mandatory"], applicable_entity=p["applicable_entity"],
            evidence_id=p["evidence_id"], evidence_fact=p["evidence_fact"],
            evidence_type=p["evidence_type"], evidence_applicable_entity=p["evidence_applicable_entity"],
            evidence_valid_until=p["evidence_valid_until"], evidence_reusable=p["evidence_reusable"],
            evidence_tender_source=p["evidence_tender_source"], current_tender_id=p["current_tender_id"],
            source_document=p["source_document"], page_or_section=p["page_or_section"],
        )
        out = matcher.safe_match(inp)
        el = time.time() - t0
        new_calls = calls[before:]
        http_called = len(new_calls) > 0
        # Determine hard rule fired: if no HTTP calls for this case, hard rule fired before HTTP
        print(f"3. Hard rule fired BEFORE HTTP: {not http_called} (HTTP calls this case: {len(new_calls)})", flush=True)
        print(f"4. Ollama HTTP actually called: {http_called} — {new_calls if new_calls else '[]'}", flush=True)
        # Raw JSON: last raw body for this case (if POST was made)
        raw = raws[-1] if new_calls and any(c["method"] == "POST" for c in new_calls) else "(no HTTP, no raw response)"
        if raw != "(no HTTP, no raw response)":
            print(f"5. Exact HTTP response JSON (truncated 800): {raw[:800]!r}", flush=True)
        else:
            print(f"5. Exact HTTP response JSON: (none — hard rule, no HTTP)", flush=True)
        print(f"6. Parsed applicability: {out.applicability}", flush=True)
        print(f"7. Parsed confidence: {out.confidence}", flush=True)
        # Derived matched IDs: from output supporting facts / applicability
        derived = []
        if out.applicability == "PASS":
            derived = [p["evidence_id"]]
        print(f"8. Deterministically derived matched evidence IDs: {derived}", flush=True)
        print(f"9. Final MatcherOutput: {out.model_dump()}", flush=True)
        print(f"11. Per-case latency: {el:.2f}s", flush=True)
        predictions.append({"input": p, "output": out.model_dump(), "elapsed": round(el, 2), "http_calls": new_calls})
finally:
    reqmod.post = orig_post
    reqmod.get = orig_get

# 10. Gold ONLY AFTER all 3 predictions
import json as js
BASE = Path(__file__).resolve().parents[1]
with open(BASE / "evaluation" / "sarai_gold_dataset.json", encoding="utf-8") as f:
    gold = js.load(f)
gmap = {}
for req in gold["gold_requirements"]:
    for ev in gold["gold_evidences"]:
        gmap[(req["requirement_id"], ev["evidence_id"])] = (
            req["expected_status"] if ev["requirement_supported"] == req["requirement_id"] else "MISSING"
        )
print("\n=== Gold comparison AFTER predictions (not visible to matcher) ===", flush=True)
for i, pr in enumerate(predictions):
    req_id = pr["input"]["requirement_id"]; ev_id = pr["input"]["evidence_id"]
    print(f"10. Case {i}: pred={pr['output']['applicability']} gold={gmap.get((req_id, ev_id), 'MISSING')} "
          f"(req {req_id} x ev {ev_id})", flush=True)

print(f"\nTotal HTTP calls (all 3 cases): {len(calls)} — {calls}", flush=True)
print("DIAG complete — no production behavior changed, no 84-case run, localhost only", flush=True)
