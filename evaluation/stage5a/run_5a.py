"""Stage 5A — prompt x model benchmark for requirement normalization.

Same scoring rules as Stage 4B so numbers are directly comparable:
- primary   = 16 Stage 3I candidates (human gold)
- secondary = 41 Stage 3K-A candidates, scored on the 33 English non-MULTI rows
- sarai     = 21 Sarai gold requirements (different tender; holdout — never
              used to write the prompt's rules or wording)

Usage:
  python evaluation/stage5a/run_5a.py <model> <prompt:v1|v2> [sets=primary,secondary,sarai]
Writes evaluation/stage5a/<model>_<prompt>_<set>.jsonl (resumable) and prints accuracy.
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

from evaluation.stage3h.single_req_tasks import parse_single_requirement  # noqa: E402
from evaluation.stage3j.minimal_contract_prompt import MINIMAL_CONTRACT_SYSTEM  # noqa: E402
from app.pipeline.prompts import REQUIREMENT_NORMALIZATION_SYSTEM  # noqa: E402

OUT = Path(__file__).parent
PROMPTS = {"v1": MINIMAL_CONTRACT_SYSTEM, "v2": REQUIREMENT_NORMALIZATION_SYSTEM}
BASE = "http://localhost:11434"


def _is_arabic(t):
    return bool(re.search(r"[؀-ۿ]", t))


def load_set(name):
    if name == "primary":
        raw = json.loads((REPO / "evaluation/stage3i/generated_candidates.json").read_text(encoding="utf-8"))
        return [(c["candidate_id"], c["source_text"], c["category_gold"]) for c in raw]
    if name == "secondary":
        raw = json.loads((REPO / "evaluation/stage3k/representative_candidates_3k.json").read_text(encoding="utf-8"))
        return [(c["candidate_id"], c["source_text"], c["category_gold"]) for c in raw
                if not c["category_gold"].startswith("MULTI") and not _is_arabic(c["source_text"])]
    if name == "sarai":
        raw = json.loads((REPO / "evaluation/sarai_gold_dataset.json").read_text(encoding="utf-8"))
        return [(r["requirement_id"], r["requirement"], r["category"]) for r in raw["gold_requirements"]]
    raise ValueError(name)


def call(model, system, text, timeout=180):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Requirement text:\n\"\"\"{text}\"\"\"\nReturn the normalized requirement."},
        ],
        "stream": False, "format": "json", "options": {"temperature": 0},
    }
    if model.startswith("qwen3"):
        payload["think"] = False
    t0 = time.time()
    try:
        r = requests.post(f"{BASE}/api/chat", json=payload, timeout=timeout)
        raw = (r.json().get("message") or {}).get("content", "") if r.status_code == 200 else None
        req, status = parse_single_requirement(raw) if raw is not None else (None, f"http_{r.status_code}")
    except Exception as e:
        req, status, raw = None, f"error_{type(e).__name__}", None
    return req, status, time.time() - t0, raw


def run(model, prompt, sets):
    summary = {}
    for s in sets:
        rows = load_set(s)
        path = OUT / f"{model.replace(':', '-')}_{prompt}_{s}.jsonl"
        done = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    done[r["id"]] = r
        with open(path, "a", encoding="utf-8") as f:
            for cid, text, gold in rows:
                if cid in done:
                    continue
                req, status, lat, raw = call(model, PROMPTS[prompt], text)
                rec = {"id": cid, "gold": gold, "pred": (req or {}).get("category"), "status": status,
                       "latency": round(lat, 2), "text": text, "raw": raw}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                done[cid] = rec
        recs = [done[c] for c, _, _ in rows]
        ok = sum(r["pred"] == r["gold"] for r in recs)
        lat = sum(r["latency"] for r in recs) / len(recs)
        summary[s] = {"correct": ok, "total": len(recs), "acc": round(ok / len(recs), 3),
                      "avg_latency_s": round(lat, 1),
                      "errors": sum(r["status"] != "ok" for r in recs)}
        print(f"{model} {prompt} {s}: {ok}/{len(recs)} = {ok/len(recs):.3f}  avg {lat:.1f}s  "
              f"non-ok={summary[s]['errors']}", flush=True)
    return summary


if __name__ == "__main__":
    model, prompt = sys.argv[1], sys.argv[2]
    sets = sys.argv[3].split(",") if len(sys.argv) > 3 else ["primary", "secondary", "sarai"]
    res = run(model, prompt, sets)
    (OUT / f"summary_{model.replace(':', '-')}_{prompt}.json").write_text(json.dumps(res, indent=1))
