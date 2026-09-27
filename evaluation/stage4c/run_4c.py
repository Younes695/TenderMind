"""Stage 4C — routing validation + performance benchmark (evaluation-only).

Policies route on OBSERVABLE signals only. Gold labels are NEVER an input to
routing (function signatures take qwen records only); gold is used solely in
post-hoc scoring, clearly separated below.

- R0: qwen2.5:3b for all (reuses exact Stage 4B stored rows).
- R1: escalate to gemma3:12b on provider error | timeout | malformed |
      schema violation | invalid category | empty summary | UNKNOWN.
- R2: R1 + deterministic degenerate-summary heuristics (placeholder-like,
      token-repetition, blank). Documented below, no confidence invented.
- Escalations execute FRESH gemma calls on byte-identical text (hash-verified);
  stored 4B gemma rows kept as cross-check.
- Oracle upper bound: post-hoc diagnostic from stored rows, labeled as such.

Usage:
  python evaluation/stage4c/run_4c.py route      # R0/R1/R2 + fresh escalations
  python evaluation/stage4c/run_4c.py analyze    # metrics, disagreement, oracle
  python evaluation/stage4c/run_4c.py concurrency# small c=1 vs c=2 probe (fresh)
Artifacts: evaluation/stage4c/*.json (see README).
"""
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

from evaluation.stage4b import providers as P  # noqa: E402

OUT = Path(__file__).parent
B4 = OUT.parents[1] / "evaluation" / "stage4b"

DATASETS = ("primary", "secondary")

# Observable-failure vocabulary (R1). Anything outside "ok"+valid category escalates.
R1_BAD_STATUSES = {"timeout", "malformed", "wrong_shape", "multi", "bad_category", "empty",
                   "provider_not_configured"}


def _is_r1_failure(qwen_rec) -> tuple:
    """Observable failure only. No gold, no correctness, no difficulty input."""
    st = str(qwen_rec.get("status", ""))
    if st.startswith(("provider_error", "transport_error", "http_")) or st in R1_BAD_STATUSES:
        return True, st.split(":")[0] if ":" in st else st
    if not (qwen_rec.get("summary") or "").strip():
        return True, "empty_summary"
    if qwen_rec.get("predicted") == "UNKNOWN":
        return True, "unknown"
    return False, ""


def _degenerate_summary(summary: str) -> tuple:
    """Deterministic output-quality heuristics (R2 only). Returns (bool, reason)."""
    s = (summary or "")
    if "..." in s and len(s.strip()) < 120:
        return True, "degenerate_placeholder"
    toks = s.lower().split()
    if len(toks) >= 8 and (max(Counter(toks).values()) / len(toks)) > 0.5:
        return True, "degenerate_repetitive"
    if not s.strip():
        return True, "degenerate_blank"
    return False, ""


def should_escalate_r1(qwen_rec) -> tuple:
    return _is_r1_failure(qwen_rec)


def should_escalate_r2(qwen_rec) -> tuple:
    bad, trigger = _is_r1_failure(qwen_rec)
    if bad:
        return True, trigger
    if qwen_rec.get("status") == "ok":
        deg, reason = _degenerate_summary(qwen_rec.get("summary", ""))
        if deg:
            return True, reason
    return False, ""


def _load_4b(tag, ds):
    return [json.loads(l) for l in
            (B4 / f"{tag}_{ds}_raw.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def route():
    """Execute R0/R1/R2. Fresh gemma calls for escalations, text hash-verified."""
    gemma = P.GemmaProvider()
    ok, msg = gemma.health_check()
    print(f"gemma health={ok} {msg}")
    if not ok:
        raise SystemExit("gemma unavailable — cannot run routing experiment")
    from app.pipeline.contracts import RequirementCandidate
    manifest = {"policies": {
        "R0": "qwen2.5:3b for all; no escalation",
        "R1": "escalate on provider_error|timeout|malformed|wrong_shape|multi|bad_category|empty|empty_summary|UNKNOWN",
        "R2": "R1 + degenerate_placeholder|degenerate_repetitive|degenerate_blank"},
        "gold_rule": "gold NEVER routed on; post-hoc scoring only",
        "contract": "minimal-1, temperature 0, timeout 90s, same text (hash-verified)"}
    escalations = []
    routed = {}
    for ds in DATASETS:
        qwen_rows = _load_4b("qwen25", ds)
        stored_gemma = {r["candidate_id"]: r for r in _load_4b("gemma", ds)}
        ds_rows = []
        for q in qwen_rows:
            r1, t1 = should_escalate_r1(q)
            r2, t2 = should_escalate_r2(q)
            final, used = dict(q), "qwen"
            gemma_fresh = None
            if r1 or r2:
                cand = RequirementCandidate(
                    candidate_id=q["candidate_id"], parent_chunk_id="",
                    source_document="", page=1, source_text=q["source_text"], span=[],
                    deterministic_signal_categories=[])
                res, status, lat, raw = gemma.normalize_requirement(cand)
                gemma_fresh = {"predicted": res.category if res else None,
                               "summary": res.summary if res else "", "status": status,
                               "latency": lat, "raw": raw,
                               "input_hash_match": _text_hash(q["source_text"]) == _text_hash(cand.source_text)}
                sg = stored_gemma.get(q["candidate_id"], {})
                gemma_fresh["stored_prediction_match"] = (sg.get("predicted") == gemma_fresh["predicted"])
                final = {**q, "predicted": gemma_fresh["predicted"],
                         "summary": gemma_fresh["summary"] or q["summary"],
                         "status": ("ok" if status == "ok" else status),
                         "routed": True, "router_latency_gemma": lat}
                used = "gemma"
                escalations.append({
                    "dataset": ds, "candidate_id": q["candidate_id"], "gold": q["gold"],
                    "trigger_r1": t1 if r1 else "", "trigger_r2": t2 if r2 else "",
                    "qwen_predicted": q["predicted"], "qwen_status": q["status"],
                    "qwen_latency": q["latency"], "gemma": gemma_fresh,
                    "final_predicted": final["predicted"], "final_used": used,
                    "arabic": q.get("arabic", False)})
                print(f"[{ds}] ESCALATE {q['candidate_id']} r1={t1 or '-'} r2={t2 or '-'} "
                      f"qwen={q['predicted']} -> gemma={gemma_fresh['predicted']} ({lat:.1f}s)")
            ds_rows.append({**final, "r0_predicted": q["predicted"], "used": used,
                            "escalated_r1": r1, "escalated_r2": r2})
        routed[ds] = ds_rows
        (OUT / f"routed_{ds}.json").write_text(json.dumps(ds_rows, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    (OUT / "escalations.json").write_text(json.dumps(escalations, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    manifest["escalation_count"] = len(escalations)
    (OUT / "routing_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"route complete: {len(escalations)} escalations")


def _error_class(rec):
    gold, pred, status = rec.get("gold"), rec.get("predicted"), rec.get("status")
    if status == "timeout":
        return "timeout"
    if str(status).startswith(("provider_error", "transport_error", "http_")) or \
            status in ("provider_not_configured",):
        return "provider-failure"
    if status in ("malformed", "wrong_shape", "multi", "bad_category", "empty") or \
            str(status).startswith("malformed"):
        return "malformed-output"
    if str(gold).startswith("MULTI"):
        return "source-ambiguity"
    if pred == "UNKNOWN":
        return "unknown"
    if pred == gold:
        return "correct"
    if pred == "TECHNICAL" and gold != "TECHNICAL":
        return "technical-collapse"
    return "semantic-neighbor"


def _score(rows, label):
    en = [r for r in rows if not r.get("arabic")]
    single = [r for r in en if not str(r.get("gold", "")).startswith("MULTI")]
    n = len(single)
    correct = sum(1 for r in single if r.get("predicted") == r.get("gold"))
    collapse = sum(1 for r in single if r.get("predicted") == "TECHNICAL" and r.get("gold") != "TECHNICAL")
    nontech = sum(1 for r in single if r.get("gold") != "TECHNICAL")
    ok = [r for r in single if r.get("status") == "ok"]
    from app.pipeline.postprocessing import grounding_score
    grounded = sum(1 for r in ok if grounding_score(r.get("summary", ""), r.get("source_text", "")) > 0)
    lats, glats = [], []
    for r in rows:
        lats.append(r.get("latency", 0))
        if r.get("router_latency_gemma"):
            glats.append(r["router_latency_gemma"])
    lats.sort()
    return {"policy": label, "scored_n": n, "correct": correct,
            "accuracy": round(correct / n, 4) if n else 0,
            "collapse_count": collapse,
            "collapse_rate": round(collapse / nontech, 4) if nontech else 0,
            "diversity": sorted(set(r.get("predicted") for r in ok if r.get("predicted"))),
            "unknown": sum(1 for r in single if r.get("predicted") == "UNKNOWN"),
            "grounded_rate": round(grounded / len(ok), 4) if ok else 0,
            "malformed": sum(1 for r in single if _error_class(r) == "malformed-output"),
            "qwen_wall_s": round(sum(lats), 1),
            "gemma_wall_s": round(sum(glats), 1),
            "router_wall_s": round(sum(lats) + sum(glats), 1),
            "avg_qwen_s": round(sum(lats) / len(lats), 2) if lats else 0,
            "avg_gemma_s": round(sum(glats) / len(glats), 2) if glats else 0,
            "p95_qwen_s": round(lats[int(len(lats) * 0.95)], 2) if lats else 0,
            "per_100_s": round(100 * (sum(lats) + sum(glats)) / len(lats), 1) if lats else 0}


def analyze():
    comparison, disagreements = {}, []
    for ds in DATASETS:
        routed = json.loads((OUT / f"routed_{ds}.json").read_text(encoding="utf-8"))
        qwen_rows = _load_4b("qwen25", ds)
        r0 = _score(qwen_rows, "R0")  # R0 rows are the untouched qwen originals
        # R1/R2 finals: routed rows but with escalation applied per policy
        r1_rows = [dict(r, predicted=r["predicted"] if r["escalated_r1"] else r["r0_predicted"],
                        status=r["status"] if r["escalated_r1"] else
                        next(q["status"] for q in qwen_rows if q["candidate_id"] == r["candidate_id"]))
                   for r in routed]
        r2_rows = [dict(r, predicted=r["predicted"] if r["escalated_r2"] else r["r0_predicted"],
                        status=r["status"] if r["escalated_r2"] else
                        next(q["status"] for q in qwen_rows if q["candidate_id"] == r["candidate_id"]))
                   for r in routed]
        # fix latencies: non-escalated rows carry gemma latency 0 already; qwen latency kept
        for r, q in zip(r1_rows, qwen_rows):
            if not r["escalated_r1"]:
                r["status"] = q["status"]
        for r, q in zip(r2_rows, qwen_rows):
            if not r["escalated_r2"]:
                r["status"] = q["status"]
        r1, r2 = _score(r1_rows, "R1"), _score(r2_rows, "R2")
        comparison[f"{ds}_R0"], comparison[f"{ds}_R1"], comparison[f"{ds}_R2"] = r0, r1, r2
        (OUT / f"r0_qwen_only_{ds}.json").write_text(json.dumps(r0, indent=2), encoding="utf-8")
        (OUT / f"r1_observable_failure_{ds}.json").write_text(json.dumps(r1, indent=2), encoding="utf-8")
        (OUT / f"r2_strict_observable_{ds}.json").write_text(json.dumps(r2, indent=2), encoding="utf-8")
        esc = json.loads((OUT / "escalations.json").read_text(encoding="utf-8"))
        gemma_rows = {r["candidate_id"]: r for r in _load_4b("gemma", ds)}
        for r in routed:
            if not (r["escalated_r1"] or r["escalated_r2"]):
                continue
            g = gemma_rows.get(r["candidate_id"], {})
            disagreements.append({
                "dataset": ds, "candidate_id": r["candidate_id"], "gold": r["gold"],
                "qwen_category": r["r0_predicted"],
                "gemma_category": r["predicted"] if r["used"] == "gemma" else g.get("predicted"),
                "qwen_error_class": _error_class(next(q for q in qwen_rows if q["candidate_id"] == r["candidate_id"])),
                "final_router_result": r["predicted"], "used": r["used"]})
        # Qwen-wrong-but-invisible (post-hoc analysis, NOT routing): valid ok outputs, wrong category
        invisible = [{"candidate_id": q["candidate_id"], "gold": q["gold"], "predicted": q["predicted"],
                      "class": _error_class(q)}
                     for q in qwen_rows
                     if q["status"] == "ok" and q["predicted"] != "UNKNOWN"
                     and not str(q["gold"]).startswith("MULTI") and not q.get("arabic")
                     and q["predicted"] != q["gold"]]
        (OUT / f"invisible_errors_{ds}.json").write_text(json.dumps(invisible, ensure_ascii=False, indent=2),
                                                          encoding="utf-8")
    (OUT / "disagreement.json").write_text(json.dumps(disagreements, ensure_ascii=False, indent=2),
                                            encoding="utf-8")
    # Oracle upper bound (DIAGNOSTIC): escalate every known qwen error, take gemma when right
    oracle = {"label": "DIAGNOSTIC / ORACLE UPPER BOUND - not a routing policy", "per_dataset": {}}
    for ds in DATASETS:
        qwen_rows = [r for r in _load_4b("qwen25", ds)
                     if not r.get("arabic") and not str(r["gold"]).startswith("MULTI")]
        gemma_rows = {r["candidate_id"]: r for r in _load_4b("gemma", ds)}
        base = sum(1 for q in qwen_rows if q["predicted"] == q["gold"])
        ceil = sum(1 for q in qwen_rows
                   if q["predicted"] == q["gold"] or
                   (gemma_rows.get(q["candidate_id"], {}).get("predicted") == q["gold"]))
        need_esc = sum(1 for q in qwen_rows if q["predicted"] != q["gold"])
        oracle["per_dataset"][ds] = {"scored": len(qwen_rows), "qwen_correct": base,
                                     "oracle_correct": ceil, "would_escalate": need_esc}
    (OUT / "oracle_upper_bound.json").write_text(json.dumps(oracle, indent=2), encoding="utf-8")
    # latency + comparison rollups
    lat = {k: {"qwen_wall_s": v["qwen_wall_s"], "gemma_wall_s": v["gemma_wall_s"],
               "router_wall_s": v["router_wall_s"], "avg_qwen_s": v["avg_qwen_s"],
               "avg_gemma_s": v["avg_gemma_s"], "p95_qwen_s": v["p95_qwen_s"],
               "per_100_s": v["per_100_s"]} for k, v in comparison.items()}
    (OUT / "latency.json").write_text(json.dumps(lat, indent=2), encoding="utf-8")
    (OUT / "comparison_4c.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    print("analyze complete")
    for k, v in comparison.items():
        print(f"  {k}: acc={v['accuracy']} ({v['correct']}/{v['scored_n']}) "
              f"collapse={v['collapse_count']} wall={v['router_wall_s']}s")


def concurrency():
    """Small controlled probe: 4 fixed candidates, qwen25, c=1 vs c=2. Fresh calls."""
    import concurrent.futures
    from app.pipeline.contracts import RequirementCandidate
    qwen_rows = _load_4b("qwen25", "primary")[:4]
    cands = [RequirementCandidate(candidate_id=r["candidate_id"], parent_chunk_id="",
                                  source_document="", page=1, source_text=r["source_text"],
                                  span=[], deterministic_signal_categories=[])
             for r in qwen_rows]

    def call(c):
        p = P.Qwen25Provider()
        t0 = time.time()
        try:
            res, status, lat, _ = p.normalize_requirement(c)
        except Exception as e:  # never fail the probe on one call
            return {"id": c.candidate_id, "status": f"probe_error:{type(e).__name__}",
                    "wall": round(time.time() - t0, 1)}
        return {"id": c.candidate_id, "status": status, "wall": round(time.time() - t0, 1)}

    out = {"note": "measurement only; c=2 max; stability over speed",
           "candidates": [c.candidate_id for c in cands]}
    t0 = time.time()
    seq = [call(c) for c in cands]
    out["c1_wall_s"] = round(time.time() - t0, 1)
    out["c1_calls"] = seq
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        par = list(ex.map(call, cands))
    out["c2_wall_s"] = round(time.time() - t0, 1)
    out["c2_calls"] = par
    try:
        import psutil
        out["ram_avail_gb"] = round(psutil.virtual_memory().available / 2**30, 1)
    except Exception:
        out["ram_avail_gb"] = "unmeasured"
    try:
        from evaluation.stage4b import providers as _  # noqa
        import subprocess
        smi = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                              "--format=csv,noheader"], capture_output=True, text=True, timeout=15)
        out["vram"] = smi.stdout.strip() or "unmeasured"
    except Exception:
        out["vram"] = "unmeasured"
    out["verdict"] = ("c2_faster" if out["c2_wall_s"] < out["c1_wall_s"] else "c2_not_faster")
    (OUT / "concurrency_test.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("c1_wall_s", "c2_wall_s", "verdict", "vram")}, indent=1))


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: run_4c.py (route | analyze | concurrency)")
    {"route": route, "analyze": analyze, "concurrency": concurrency}[sys.argv[1]]()


if __name__ == "__main__":
    main()
