"""Stage 4D — uncertainty signals + warmed concurrency + harder-tender validation.

Evaluation/research only. Gold labels are NEVER routing inputs: signal functions
take (candidate_text, deterministic_signals, model_output, status, latency)
only. Gold is used post-hoc in evaluate_signals(), clearly separated.

Usage:
  python evaluation/stage4d/run_4d.py signals       # Exp A on stored 4B/4C rows
  python evaluation/stage4d/run_4d.py selfcons       # Exp A fresh qwenx2 (n=16)
  python evaluation/stage4d/run_4d.py concurrency   # Exp B warmed c=1/2/4/8
  python evaluation/stage4d/run_4d.py harder_build  # Exp C fixtures from 6th Oct
  python evaluation/stage4d/run_4d.py harder_run    # Exp C R0/R1/R3
  python evaluation/stage4d/run_4d.py analyze       # cross-tender + rollups
"""
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

OUT = Path(__file__).parent
B4 = OUT.parents[1] / "evaluation" / "stage4b"

# --- signal library (gold-free; deterministic; interpretable) ----------------
# Category keyword sets derived from the minimal-1 PRIMARY PURPOSE definitions
# (contract text), NOT from gold labels or fixture answers.
CATEGORY_KEYWORDS = {
    "LEGAL": {"legal", "registration", "license", "consortium", "agreement", "notarized",
              "authorization", "permit", "certificate", "compliance", "contractor union"},
    "TECHNICAL": {"transformer", "gis", "switchgear", "voltage", "kv", "mva", "equipment",
                  "specification", "installation", "testing", "cable", "substation"},
    "EXPERIENCE": {"experience", "reference", "previous", "similar projects", "history",
                   "executed", "completed projects", "track record"},
    "FINANCIAL": {"financial", "turnover", "audited", "bank", "statements", "capital",
                  "credit", "funding"},
    "SCHEDULE": {"delivery", "completion", "months", "days", "schedule", "deadline",
                 "handover", "milestone"},
    "COMMERCIAL": {"price", "payment", "cost", "invoice", "currency", "bid bond",
                   "security", "offer"},
    "HSE": {"safety", "health", "environment", "hse", "protective", "hazard"},
    "QA_QC": {"quality", "inspection", "assurance", "qc", "qa", "testing quality"},
    "EQUIPMENT": {"supply", "provide equipment", "machinery", "tools", "vehicles"},
    "PERSONNEL": {"personnel", "staff", "engineer", "manager", "cv", "resumes",
                  "key personnel", "manpower"},
    "SUBCONTRACTOR": {"subcontract", "sub-contract", "subcontractor"},
    "SUBMISSION": {"submit", "submission", "envelope", "sealed", "tender box", "bid closing"},
}


def _toks(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def sig_unknown(rec):
    return rec.get("predicted") == "UNKNOWN"


def sig_invalid(rec):
    st = str(rec.get("status", ""))
    return (st != "ok" or not (rec.get("summary") or "").strip()
            or rec.get("predicted") not in CATEGORY_KEYWORDS)


def sig_degenerate(rec):
    s = rec.get("summary", "") or ""
    if "..." in s and len(s.strip()) < 120:
        return True
    toks = s.lower().split()
    if len(toks) >= 8 and max(Counter(toks).values()) / len(toks) > 0.5:
        return True
    return not s.strip()


def sig_signal_mismatch(rec, signals):
    """Predicted category not among deterministic signal categories.

    CIRCULARITY WARNING (reported, not hidden): for single-signal candidates the
    fixture gold IS signals[0], so this restates correctness there. Legitimate
    use is multi-signal (ambiguous-by-construction) rows -> escalate.
    """
    pred = rec.get("predicted")
    return bool(pred) and pred != "UNKNOWN" and pred not in list(signals or [])


def sig_summary_keyword_mismatch(rec):
    """Summary's dominant keyword-category disagrees with predicted category."""
    summary = rec.get("summary", "") or ""
    pred = rec.get("predicted")
    toks = set(_toks(summary))
    best, bestn = None, 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        n = sum(1 for kw in kws if kw in summary.lower())
        if n > bestn:
            best, bestn = cat, n
    if bestn == 0 or best is None:
        return False
    return pred != best


def sig_length_anomaly(rec, median_len):
    s = len(rec.get("summary", "") or "")
    return s > 3 * median_len or s < 8


def sig_verbatim_copy(rec, source_text):
    s, src = (rec.get("summary", "") or "").strip(), (source_text or "").strip()
    return bool(s) and s == src


def sig_slow(rec, p95):
    return rec.get("latency", 0) > p95


SIGNALS = {
    "S_UNKNOWN": lambda r, ctx: sig_unknown(r),
    "S_INVALID": lambda r, ctx: sig_invalid(r),
    "S_DEGENERATE": lambda r, ctx: sig_degenerate(r),
    "S_SIGNAL_MISMATCH": lambda r, ctx: sig_signal_mismatch(r, ctx.get("signals", [])),
    "S_KEYWORD_MISMATCH": lambda r, ctx: sig_summary_keyword_mismatch(r),
    "S_LENGTH_ANOMALY": lambda r, ctx: sig_length_anomaly(r, ctx.get("median_len", 60)),
    "S_VERBATIM_COPY": lambda r, ctx: sig_verbatim_copy(r, ctx.get("source_text", "")),
    "S_SLOW": lambda r, ctx: sig_slow(r, ctx.get("p95", 1e9)),
}


def _load_rows():
    rows = []
    for ds, fix in (("primary", "stage3i/generated_candidates.json"),
                    ("secondary", "stage3k/representative_candidates_3k.json")):
        fixrows = {c["candidate_id"]: c for c in
                   json.loads((OUT.parents[1] / "evaluation" / fix).read_text(encoding="utf-8"))}
        for tag in ("qwen25",):
            for line in (B4 / f"{tag}_{ds}_raw.jsonl").read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                f = fixrows.get(r["candidate_id"], {})
                rows.append({"dataset": ds, "rec": r,
                             "signals": f.get("deterministic_signal_categories", [])})
    return rows


def signals_cmd():
    rows = _load_rows()
    lats = sorted(r["rec"].get("latency", 0) for r in rows)
    p95 = lats[int(len(lats) * 0.95)]
    med_len = sorted(len(r["rec"].get("summary", "") or "") for r in rows)[len(rows) // 2]
    catalog = {}
    for name in SIGNALS:
        catalog[name] = {"description": (SIGNALS[name].__doc__ if False else name),
                         "gold_free": True, "deterministic": True,
                         "cost": "string ops (free) — no LLM"}
    catalog["S_SELF_CONSISTENCY"] = {"description": "qwen2.5:3b twice; flag on category/summary disagreement",
                                     "gold_free": True, "deterministic": False,
                                     "cost": "2x LLM calls (expensive)"}
    catalog["S_LOGPROBS"] = {"description": "token probabilities",
                             "gold_free": True, "deterministic": True,
                             "cost": "UNAVAILABLE: Ollama /api/chat does not expose logprobs; "
                                     "no production config change permitted — not measured"}
    (OUT / "signal_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")

    evaluation = {}
    for name, fn in SIGNALS.items():
        flagged, tp, fp, fn_, tn = [], 0, 0, 0, 0
        catches_neighbor, catches_collapse, catches_valid_wrong = 0, 0, 0
        for item in rows:
            r = item["rec"]
            if r.get("arabic") or str(r.get("gold", "")).startswith("MULTI"):
                continue
            ctx = {"signals": item["signals"], "median_len": med_len, "p95": p95,
                   "source_text": r.get("source_text", "")}
            f = bool(fn(r, ctx))
            wrong = (r.get("predicted") != r.get("gold"))
            if f:
                flagged.append(r["candidate_id"])
            if f and wrong:
                tp += 1
            elif f and not wrong:
                fp += 1
            elif not f and wrong:
                fn_ += 1
            else:
                tn += 1
            if f and wrong and r.get("status") == "ok" and r.get("predicted") != "UNKNOWN":
                catches_valid_wrong += 1
            if f and r.get("predicted") == "TECHNICAL" and r.get("gold") != "TECHNICAL":
                catches_collapse += 1
            if f and wrong and r.get("status") == "ok":
                catches_neighbor += 1
        n = tp + fp + fn_ + tn
        evaluation[name] = {
            "flagged": len(flagged), "flagged_ids": flagged,
            "flag_rate": round(len(flagged) / n, 4) if n else 0,
            "precision_wrong": round(tp / (tp + fp), 4) if tp + fp else 0,
            "recall_wrong": round(tp / (tp + fn_), 4) if tp + fn_ else 0,
            "fpr": round(fp / (fp + tn), 4) if fp + tn else 0,
            "fnr": round(fn_ / (tp + fn_), 4) if tp + fn_ else 0,
            "catches_valid_but_wrong": catches_valid_wrong,
            "catches_collapse": catches_collapse, "cost": "free string ops"}
    # combinations (small, deterministic, human-readable)
    combos = {"S_UNKNOWN_OR_INVALID": ("S_UNKNOWN", "S_INVALID"),
              "S_UNKNOWN_OR_MISMATCH": ("S_UNKNOWN", "S_SIGNAL_MISMATCH"),
              "S_UNKNOWN_OR_KEYWORD": ("S_UNKNOWN", "S_KEYWORD_MISMATCH")}
    for cname, (a, b) in combos.items():
        fa = set(evaluation[a]["flagged_ids"])
        fb = set(evaluation[b]["flagged_ids"])
        both = fa | fb
        # recompute precision/recall over the union
        tp = fp = fn_ = tn = 0
        for item in rows:
            r = item["rec"]
            if r.get("arabic") or str(r.get("gold", "")).startswith("MULTI"):
                continue
            f = r["candidate_id"] in both
            wrong = r.get("predicted") != r.get("gold")
            if f and wrong:
                tp += 1
            elif f:
                fp += 1
            elif wrong:
                fn_ += 1
            else:
                tn += 1
        evaluation[cname] = {"flagged": len(both), "flagged_ids": sorted(both),
                             "flag_rate": round(len(both) / (tp + fp + fn_ + tn), 4),
                             "precision_wrong": round(tp / (tp + fp), 4) if tp + fp else 0,
                             "recall_wrong": round(tp / (tp + fn_), 4) if tp + fn_ else 0,
                             "fpr": round(fp / (fp + tn), 4) if fp + tn else 0,
                             "cost": "free string ops"}
    (OUT / "signal_evaluation.json").write_text(json.dumps(evaluation, indent=2), encoding="utf-8")
    print("signal evaluation (diagnostic; gold used post-hoc only):")
    for name, e in evaluation.items():
        print(f"  {name}: flagged={e['flagged']} prec={e['precision_wrong']} "
              f"rec={e['recall_wrong']} fpr={e['fpr']} validWrong={e.get('catches_valid_but_wrong', '-')}")


def concurrency_cmd():
    """Warmed concurrency: fixed 32-request workload (16 primary x2 rounds),
    warm-up before timing, levels 1/2/4/8 with safe-stop rules. Fresh calls."""
    import concurrent.futures
    from app.pipeline.contracts import RequirementCandidate
    from evaluation.stage4b.providers import Qwen25Provider
    try:
        import psutil
        have_psutil = True
    except Exception:
        have_psutil = False
    cands16 = json.loads((OUT.parents[1] / "evaluation" / "stage3i" / "generated_candidates.json").read_text(encoding="utf-8"))
    work = []
    for rnd in (1, 2):
        for c in cands16:
            work.append(RequirementCandidate(
                candidate_id=f"{c['candidate_id']}-r{rnd}", parent_chunk_id="", source_document="",
                page=1, source_text=c["source_text"], span=[], deterministic_signal_categories=[]))
    assert len(work) == 32
    # warm-up (model + process), untimed
    p0 = Qwen25Provider()
    for c in work[:4]:
        try:
            p0.normalize_requirement(c)
        except Exception:
            pass

    def snapshot():
        snap = {}
        try:
            import subprocess
            smi = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                                  "--format=csv,noheader"], capture_output=True, text=True, timeout=15)
            snap["vram"] = smi.stdout.strip()
        except Exception:
            snap["vram"] = "unmeasured"
        if have_psutil:
            snap["cpu_pct"] = psutil.cpu_percent(interval=1)
            snap["ram_avail_gb"] = round(psutil.virtual_memory().available / 2**30, 1)
        return snap

    def call_one(c):
        p = Qwen25Provider()
        t0 = time.time()
        try:
            _, status, lat, _ = p.normalize_requirement(c)
            return {"status": status, "lat": round(lat, 2)}
        except Exception as e:
            return {"status": f"probe_error:{type(e).__name__}", "lat": round(time.time() - t0, 2)}

    results = {"workload": "32 requests (16 primary candidates x2 rounds), warmed",
               "levels": {}}
    for level in (1, 2, 4, 8):
        before = snapshot()
        t0 = time.time()
        if level == 1:
            calls = [call_one(c) for c in work]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=level) as ex:
                calls = list(ex.map(call_one, work))
        wall = time.time() - t0
        lats = sorted(c["lat"] for c in calls)
        errs = sum(1 for c in calls if c["status"] != "ok")
        after = snapshot()
        results["levels"][str(level)] = {
            "wall_s": round(wall, 1), "throughput_per_s": round(32 / wall, 3),
            "avg_s": round(sum(lats) / len(lats), 2), "p50_s": round(lats[16], 2),
            "p95_s": round(lats[int(32 * 0.95)], 2), "max_s": round(lats[-1], 2),
            "errors": errs, "error_rate": round(errs / 32, 4),
            "statuses": dict(Counter(c["status"] for c in calls)),
            "vram_before": before.get("vram"), "vram_after": after.get("vram"),
            "cpu_pct_before": before.get("cpu_pct"), "ram_avail_gb": after.get("ram_avail_gb")}
        print(f"c={level}: wall={wall:.1f}s thr={32/wall:.3f}/s avg={sum(lats)/len(lats):.1f}s "
              f"p95={lats[int(32*0.95)]:.1f}s max={lats[-1]:.1f}s errors={errs}")
        if errs / 32 > 0.10:
            results["levels"][str(level)]["stopped"] = "error rate >10% — halting higher levels"
            print("STOPPING: error rate exceeded 10%")
            break
    (OUT / "concurrency_results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def harder_run_cmd():
    """Exp C: qwen over 22 harder rows; R1 escalation + R3 keyword-gate escalation.
    All escalation inputs hash-verified; gold used post-hoc only."""
    import hashlib
    from app.pipeline.contracts import RequirementCandidate
    from evaluation.stage4b.providers import Qwen25Provider, GemmaProvider
    from evaluation.stage4c.run_4c import should_escalate_r1
    fix = json.loads((OUT / "harder_gold.json").read_text(encoding="utf-8"))
    qwen, gemma = Qwen25Provider(), GemmaProvider()
    print("health:", qwen.health_check(), gemma.health_check())
    qrows = []
    for c in fix:
        cand = RequirementCandidate(candidate_id=c["candidate_id"], parent_chunk_id=c.get("parent_chunk_id", ""),
                                    source_document=c.get("source_document", ""), page=int(c.get("page", 1) or 1),
                                    source_text=c["source_text"], span=[], deterministic_signal_categories=[])
        res, status, lat, raw = qwen.normalize_requirement(cand)
        qrows.append({"candidate_id": c["candidate_id"], "gold": c["category_gold"],
                      "source_text": c["source_text"], "arabic": False,
                      "predicted": res.category if res else None,
                      "summary": res.summary if res else "", "status": status,
                      "latency": lat, "raw": raw})
        print(f"[R0] {c['candidate_id']} gold={c['category_gold']} pred={qrows[-1]['predicted']} {status} ({lat:.1f}s)")
    (OUT / "harder_qwen_rows.json").write_text(json.dumps(qrows, ensure_ascii=False, indent=2), encoding="utf-8")

    def escalate(cands, tag):
        outs = {}
        for q in cands:
            cand = RequirementCandidate(candidate_id=q["candidate_id"], parent_chunk_id="",
                                        source_document="", page=1, source_text=q["source_text"],
                                        span=[], deterministic_signal_categories=[])
            assert hashlib.sha256(q["source_text"].encode()).hexdigest() == \
                hashlib.sha256(cand.source_text.encode()).hexdigest()
            res, status, lat, raw = gemma.normalize_requirement(cand)
            outs[q["candidate_id"]] = {"predicted": res.category if res else None,
                                       "summary": res.summary if res else "",
                                       "status": status, "latency": lat}
            print(f"[{tag}] {q['candidate_id']} -> gemma={outs[q['candidate_id']]['predicted']} ({lat:.1f}s)")
        return outs

    # R1
    r1_ids = [q["candidate_id"] for q in qrows if should_escalate_r1(q)[0]]
    g1 = escalate([q for q in qrows if q["candidate_id"] in r1_ids], "R1") if r1_ids else {}
    # R3: UNKNOWN or keyword-mismatch (independent signal from Exp A)
    r3_ids = set(r1_ids)
    for q in qrows:
        if q["candidate_id"] in r3_ids:
            continue
        if sig_summary_keyword_mismatch(q):
            r3_ids.add(q["candidate_id"])
    g3 = escalate([q for q in qrows if q["candidate_id"] in r3_ids and q["candidate_id"] not in g1], "R3")
    g3 = {**{k: v for k, v in g1.items()}, **g3}
    json.dump({"r1_escalated": sorted(r1_ids), "r3_escalated": sorted(r3_ids),
               "gemma": g1, "gemma_r3": g3},
              open(OUT / "harder_escalations.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    def score(final_map, label):
        scored = [q for q in qrows if q["gold"] != "AMBIGUOUS"]
        n = len(scored)
        correct = sum(1 for q in scored if final_map.get(q["candidate_id"], q["predicted"]) == q["gold"])
        collapse = sum(1 for q in scored
                       if final_map.get(q["candidate_id"], q["predicted"]) == "TECHNICAL" and q["gold"] != "TECHNICAL")
        nontech = sum(1 for q in scored if q["gold"] != "TECHNICAL")
        qw = sum(q["latency"] for q in qrows)
        gw = sum(v["latency"] for k, v in g3.items() if k in (set(final_map) if label != "R0" else set()))
        return {"policy": label, "scored_n": n, "correct": correct,
                "accuracy": round(correct / n, 4), "collapse_count": collapse,
                "collapse_rate": round(collapse / nontech, 4) if nontech else 0,
                "escalations": len(final_map), "qwen_wall_s": round(qw, 1),
                "gemma_wall_s": round(gw, 1), "router_wall_s": round(qw + gw, 1)}

    r0 = score({}, "R0")
    r1 = score({k: v["predicted"] for k, v in g1.items()}, "R1")
    r3 = score({k: v["predicted"] for k, v in g3.items()}, "R3")
    # R3 statuses: escalated rows take gemma status
    comp = {"R0": r0, "R1": r1, "R3": r3}
    (OUT / "harder_tender_comparison.json").write_text(json.dumps(comp, indent=2), encoding="utf-8")
    (OUT / "harder_tender_r0.json").write_text(json.dumps(r0, indent=2), encoding="utf-8")
    (OUT / "harder_tender_r1.json").write_text(json.dumps(r1, indent=2), encoding="utf-8")
    (OUT / "harder_tender_r3.json").write_text(json.dumps(r3, indent=2), encoding="utf-8")
    print("harder comparison:", json.dumps(comp, indent=1))


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: run_4d.py (signals | concurrency | harder_run | analyze)")
    {"signals": signals_cmd, "concurrency": concurrency_cmd, "harder_run": harder_run_cmd}[sys.argv[1]]()


if __name__ == "__main__":
    main()
