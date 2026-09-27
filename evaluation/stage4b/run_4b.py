"""Stage 4B — controlled model shootout harness (evaluation-only).

Fairness: every model receives the EXACT SAME candidates (byte-identical
source_text, fixed order), the SAME MINIMAL_CONTRACT_SYSTEM string, the SAME
parser, temperature 0, format json, timeout 90s. Fixture sha256 is recorded
per model run and asserted equal. No per-model tuning, examples, or hints.

Usage:
  python evaluation/stage4b/run_4b.py probe <model>      # 1-candidate sanity
  python evaluation/stage4b/run_4b.py run <model>        # primary(16)+secondary(41)
  python evaluation/stage4b/run_4b.py analyze            # all comparisons from JSONL
Artifacts: evaluation/stage4b/*.json per the Stage 4B file list.
"""
import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

from app.pipeline.contracts import RequirementCandidate  # noqa: E402
from evaluation.stage4b import providers as P  # noqa: E402

OUT = Path(__file__).parent
REPO = OUT.parents[1]

PRIMARY_FIXTURE = REPO / "evaluation" / "stage3i" / "generated_candidates.json"
SECONDARY_FIXTURE = REPO / "evaluation" / "stage3k" / "representative_candidates_3k.json"

CONTRACT_VERSION = "minimal-1"
TIMEOUT_S = 90


def _load(fixture: Path):
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    cands, golds = [], {}
    for c in raw:
        cands.append(RequirementCandidate(
            candidate_id=c["candidate_id"], parent_chunk_id=c.get("parent_chunk_id", ""),
            source_document=c.get("source_document", ""), page=int(c.get("page", 1) or 1),
            source_text=c["source_text"], span=list(c.get("span", []) or []),
            deterministic_signal_categories=list(c.get("deterministic_signal_categories", []))))
        golds[c["candidate_id"]] = c.get("category_gold", "UNKNOWN")
    return cands, golds


def fixture_sha(cands) -> str:
    h = hashlib.sha256()
    for c in cands:
        h.update(c.candidate_id.encode() + b"\x00" + c.source_text.encode("utf-8") + b"\x00")
    return h.hexdigest()[:16]


def _is_arabic(text: str) -> bool:
    import re
    return bool(re.search(r"[\u0600-\u06FF]", text))


def run_model(tag: str, dataset: str):
    """Run one model over one dataset with incremental save + resume."""
    cands, golds = _load(PRIMARY_FIXTURE if dataset == "primary" else SECONDARY_FIXTURE)
    provider = P.PROVIDER_CLASSES[tag]()
    ok, msg = provider.health_check()
    print(f"[{tag}] health={ok} {msg}")
    out_path = OUT / f"{tag}_{dataset}_raw.jsonl"
    done = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    r = json.loads(line)
                    done[r["candidate_id"]] = r
                except Exception:
                    pass
    mode = "a" if out_path.exists() else "w"
    sha = fixture_sha(cands)
    with open(out_path, mode, encoding="utf-8") as f:
        for c in cands:
            if c.candidate_id in done:
                continue
            res, status, lat, raw = provider.normalize_requirement(c)
            rec = {"candidate_id": c.candidate_id, "gold": golds[c.candidate_id],
                   "source_text": c.source_text, "fixture_sha": sha,
                   "predicted": (res.category if res else None),
                   "summary": (res.summary if res else ""),
                   "mandatory": (res.mandatory if res else None),
                   "applicable_entity": (res.applicable_entity if res else None),
                   "status": status, "latency": lat, "raw": raw,
                   "usage": {}, "arabic": _is_arabic(c.source_text)}
            done[c.candidate_id] = rec
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{tag}/{dataset}] {c.candidate_id} gold={rec['gold']} "
                  f"pred={rec['predicted']} {status} ({lat:.1f}s) [{len(done)}/{len(cands)}]")
    (OUT / f"{tag}_{dataset}_metrics.json").write_text(
        json.dumps(provider.metrics(), indent=2), encoding="utf-8")
    print(f"[{tag}/{dataset}] done {len(done)}/{len(cands)}")


def _classify(rec) -> str:
    gold, pred, status = rec["gold"], rec["predicted"], rec["status"]
    if status == "timeout":
        return "timeout"
    if status in ("provider_error", "provider_not_configured", "transport_error") or \
            str(status).startswith(("provider_error", "transport_error", "http_")):
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


def score_dataset(tag: str, dataset: str):
    from app.pipeline.postprocessing import grounding_score
    path = OUT / f"{tag}_{dataset}_raw.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    en = [r for r in recs if not r["arabic"]]
    single = [r for r in en if not str(r["gold"]).startswith("MULTI")]
    n = len(single)
    correct = sum(1 for r in single if r["predicted"] == r["gold"])
    per_cat: Dict[str, Dict[str, int]] = {}
    for r in single:
        per_cat.setdefault(r["gold"], {"n": 0, "correct": 0})
        per_cat[r["gold"]]["n"] += 1
        per_cat[r["gold"]]["correct"] += 1 if r["predicted"] == r["gold"] else 0
    collapse = sum(1 for r in single if r["predicted"] == "TECHNICAL" and r["gold"] != "TECHNICAL")
    nontech_gold = sum(1 for r in single if r["gold"] != "TECHNICAL")
    classes = Counter(_classify(r) for r in recs)
    unknown = sum(1 for r in single if r["predicted"] == "UNKNOWN")
    ok_recs = [r for r in single if r["status"] == "ok"]
    grounded = [r for r in ok_recs if grounding_score(r["summary"], r["source_text"]) > 0]
    ungrounded = [r["candidate_id"] for r in ok_recs
                  if grounding_score(r["summary"], r["source_text"]) == 0]
    non_null_mand = [r["candidate_id"] for r in ok_recs if r["mandatory"] is not None]
    non_null_ent = [r["candidate_id"] for r in ok_recs if r["applicable_entity"] is not None]
    lats = sorted(r["latency"] for r in recs)
    diversity = sorted(set(r["predicted"] for r in ok_recs if r["predicted"]))
    contract_viol = classes["malformed-output"]
    return {
        "model": tag, "dataset": dataset, "total": len(recs),
        "english_scored": len(en), "accuracy_n": n, "accuracy_correct": correct,
        "accuracy": round(correct / n, 4) if n else 0.0,
        "per_category": per_cat, "category_diversity": diversity,
        "collapse_count": collapse,
        "collapse_rate": round(collapse / nontech_gold, 4) if nontech_gold else 0.0,
        "unknown_count": unknown, "unknown_rate": round(unknown / n, 4) if n else 0,
        "error_classes": dict(classes),
        "contract_violation_count": contract_viol,
        "contract_violation_rate": round(contract_viol / len(recs), 4) if recs else 0,
        "timeout_count": classes["timeout"], "provider_failures": classes["provider-failure"],
        "grounded_summary_rate": round(len(grounded) / len(ok_recs), 4) if ok_recs else 0,
        "ungrounded_candidate_ids": ungrounded,
        "mandatory_non_null_ids": non_null_mand,
        "mandatory_null_compliance": round(1 - len(non_null_mand) / len(ok_recs), 4) if ok_recs else 1.0,
        "entity_non_null_ids": non_null_ent,
        "entity_null_compliance": round(1 - len(non_null_ent) / len(ok_recs), 4) if ok_recs else 1.0,
        "valid_outputs": len(ok_recs),
        "wall_s": round(sum(lats), 1), "avg_s": round(sum(lats) / len(lats), 2) if lats else 0,
        "p50_s": round(lats[len(lats) // 2], 2) if lats else 0,
        "p95_s": round(lats[int(len(lats) * 0.95)], 2) if lats else 0,
        "min_s": round(lats[0], 2) if lats else 0, "max_s": round(lats[-1], 2) if lats else 0,
        "throughput_per_s": round(len(lats) / sum(lats), 4) if sum(lats) else 0,
        "per_100_s": round(100 * sum(lats) / len(lats), 1) if lats else 0,
    }


def analyze():
    from evaluation.stage3j.minimal_contract_prompt import MINIMAL_CONTRACT_SYSTEM
    models = [p.stem.replace("_primary_raw", "") for p in OUT.glob("*_primary_raw.jsonl")]
    models = sorted(set(models))
    contract_hash = hashlib.sha256(MINIMAL_CONTRACT_SYSTEM.encode()).hexdigest()[:16]

    manifest = {"contract": CONTRACT_VERSION, "contract_sha": contract_hash,
                "temperature": 0, "format": "json", "timeout_s": TIMEOUT_S,
                "think": {"qwen3": False, "others": "backend-default"},
                "controls": "same candidates/order/text/label-space/contract/parser, no tuning/examples/hints",
                "datasets": {}, "models": models}
    for ds, fix in (("primary", PRIMARY_FIXTURE), ("secondary", SECONDARY_FIXTURE)):
        cands, _ = _load(fix)
        manifest["datasets"][ds] = {"fixture": fix.name, "n": len(cands),
                                    "fixture_sha": fixture_sha(cands)}

    # per-model results + fairness assertion (fixture bytes identical per model)
    results, per_model_rows = {}, {}
    for tag in models:
        for ds in ("primary", "secondary"):
            p = OUT / f"{tag}_{ds}_raw.jsonl"
            if not p.exists():
                continue
            recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            shas = set(r["fixture_sha"] for r in recs)
            assert shas == {manifest["datasets"][ds]["fixture_sha"]}, f"fixture drift for {tag}/{ds}"
            per_model_rows[(tag, ds)] = recs
            results[f"{tag}_{ds}"] = score_dataset(tag, ds)
            (OUT / f"{tag}_results.json").write_text(
                json.dumps(results[f"{tag}_{ds}"], indent=2), encoding="utf-8")
    (OUT / "comparison_4b.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    # per-candidate comparison (+ confusion matrices + latency/resource tables)
    for ds in ("primary", "secondary"):
        rows = []
        cands, _ = _load(PRIMARY_FIXTURE if ds == "primary" else SECONDARY_FIXTURE)
        for c in cands:
            row = {"candidate_id": c.candidate_id, "gold": None, "source_text": c.source_text,
                   "predictions": {}, "summaries": {}, "error_class": {}, "latency": {},
                   "valid": {}}
            for tag in models:
                recs = per_model_rows.get((tag, ds), [])
                r = next((x for x in recs if x["candidate_id"] == c.candidate_id), None)
                if r is None:
                    continue
                row["gold"] = r["gold"]
                row["predictions"][tag] = r["predicted"]
                row["summaries"][tag] = r["summary"]
                row["error_class"][tag] = _classify(r)
                row["latency"][tag] = r["latency"]
                row["valid"][tag] = r["status"] == "ok"
            rows.append(row)
        (OUT / f"per_candidate_comparison_{ds}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    conf = {}
    for (tag, ds), recs in per_model_rows.items():
        m: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in recs:
            if str(r["gold"]).startswith("MULTI"):
                continue
            m[r["gold"]][str(r["predicted"])] += 1
        conf[f"{tag}_{ds}"] = {g: dict(p) for g, p in m.items()}
    (OUT / "confusion_matrices.json").write_text(json.dumps(conf, indent=2), encoding="utf-8")

    lat = {k: {"avg_s": v["avg_s"], "p50_s": v["p50_s"], "p95_s": v["p95_s"],
               "min_s": v["min_s"], "max_s": v["max_s"], "wall_s": v["wall_s"],
               "throughput_per_s": v["throughput_per_s"], "per_100_s": v["per_100_s"]}
           for k, v in results.items()}
    (OUT / "latency_comparison.json").write_text(json.dumps(lat, indent=2), encoding="utf-8")

    # agreement (primary: balanced golds; secondary likewise)
    for ds in ("primary", "secondary"):
        rows = json.loads((OUT / f"per_candidate_comparison_{ds}.json").read_text(encoding="utf-8"))
        agree = []
        for row in rows:
            preds = {t: p for t, p in row["predictions"].items() if p is not None}
            counts = Counter(preds.values())
            top, topn = counts.most_common(1)[0] if counts else (None, 0)
            agree.append({
                "candidate_id": row["candidate_id"], "gold": row["gold"],
                "predictions": preds, "n_models": len(preds),
                "n_agreeing": topn, "majority": top,
                "unanimous": topn == len(preds) and len(preds) > 1,
                "single_differ": topn == len(preds) - 1 and len(preds) > 2,
                "split_2_2": sorted(counts.values()) == [2, 2],
                "agree_technical_gold_not": top == "TECHNICAL" and row["gold"] != "TECHNICAL",
            })
        (OUT / f"model_agreement_{ds}.json").write_text(json.dumps(agree, indent=2), encoding="utf-8")

    # router simulation: A=qwen25 fast baseline; each challenger as B.
    # Scored set == main accuracy set (single-gold, English-only).
    arabic_ids = {}
    for ds in ("primary", "secondary"):
        ids = set()
        for tag in models:
            p = OUT / f"{tag}_{ds}_raw.jsonl"
            if p.exists():
                for line in p.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        r = json.loads(line)
                        if r.get("arabic"):
                            ids.add(r["candidate_id"])
        arabic_ids[ds] = ids
    sim = {"policy": "escalate on UNKNOWN | contract-violation | malformed | provider-error | timeout",
           "note": "simulation only; no calibrated confidence used; no production policy",
           "results": {}}
    for ds in ("primary", "secondary"):
        rows = json.loads((OUT / f"per_candidate_comparison_{ds}.json").read_text(encoding="utf-8"))
        for b in [m for m in models if m != "qwen25"]:
            esc, sim_correct, scored = 0, 0, 0
            for row in rows:
                if str(row["gold"]).startswith("MULTI") or row["candidate_id"] in arabic_ids[ds]:
                    continue
                scored += 1
                a_cls = row["error_class"].get("qwen25", "")
                escalate = a_cls in ("unknown", "malformed-output", "timeout", "provider-failure")
                pred = row["predictions"].get(b) if escalate else row["predictions"].get("qwen25")
                if escalate:
                    esc += 1
                if pred == row["gold"]:
                    sim_correct += 1
            sim["results"][f"{ds}_qwen25-then-{b}"] = {
                "escalated": esc, "scored": scored,
                "escalation_rate": round(esc / scored, 4) if scored else 0,
                "simulated_accuracy": round(sim_correct / scored, 4) if scored else 0}
    (OUT / "router_simulation.json").write_text(json.dumps(sim, indent=2), encoding="utf-8")

    # language supplement: Arabic-source rows of the secondary set, per model
    lang = {}
    for (tag, ds), recs in per_model_rows.items():
        if ds != "secondary":
            continue
        ar = [r for r in recs if r["arabic"] and not str(r["gold"]).startswith("MULTI")]
        lang[tag] = {"n": len(ar),
                     "correct": sum(1 for r in ar if r["predicted"] == r["gold"]),
                     "unknown": sum(1 for r in ar if r["predicted"] == "UNKNOWN"),
                     "collapse": sum(1 for r in ar if r["predicted"] == "TECHNICAL" and r["gold"] != "TECHNICAL"),
                     "classes": dict(Counter(_classify(r) for r in [x for x in recs if x["arabic"]]))}
    (OUT / "language_robustness.json").write_text(
        json.dumps({"note": "supplementary only; existing Arabic-source fixture rows; NOT mixed into main accuracy",
                    "per_model": lang}, indent=2), encoding="utf-8")

    (OUT / "benchmark_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"analyze complete: models={models}")
    for k, v in results.items():
        print(f"  {k}: acc={v['accuracy']} ({v['accuracy_correct']}/{v['accuracy_n']}) "
              f"collapse={v['collapse_count']} unk={v['unknown_count']} avg={v['avg_s']}s")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: run_4b.py (probe <model> [dataset] | run <model> [dataset] | analyze)")
    cmd = sys.argv[1]
    if cmd == "probe":
        tag = sys.argv[2]
        cands, _ = _load(PRIMARY_FIXTURE)
        provider = P.PROVIDER_CLASSES[tag]()
        print("health:", provider.health_check())
        res, status, lat, raw = provider.normalize_requirement(cands[0])
        print("status:", status, "lat:", round(lat, 1))
        print("result:", json.dumps(res.to_dict() if res else None, ensure_ascii=False)[:300])
        print("raw:", (raw or "")[:300])
    elif cmd == "run":
        tag = sys.argv[2]
        ds = sys.argv[3] if len(sys.argv) > 3 else "both"
        for d in (["primary", "secondary"] if ds == "both" else [ds]):
            run_model(tag, d)
    elif cmd == "analyze":
        analyze()
    else:
        raise SystemExit("unknown command")


if __name__ == "__main__":
    main()
