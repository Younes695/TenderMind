"""
Stage 3K — Experiments A (3D representative set) and B (full Mobile tender).

Usage:
  python evaluation/stage3k/run_3k.py A   # representative set only
  python evaluation/stage3k/run_3k.py B   # full Mobile (resumable, ceiling-guarded)

Saves incrementally after every candidate so a timeout never loses data.
Resume: re-running skips candidate_ids already recorded in the per-candidate file.
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

from evaluation.stage3k.two_stage_pipeline import (
    discover_candidates, normalize_candidate, post_process, SKIPPED_TINY_INPUT,
)
from evaluation.llm_generic_extraction import (
    get_ollama_model, get_ollama_base_url, check_ollama_available,
)
from evaluation.stage3i.presegment import segment_parent_chunk

OUT = Path(__file__).parent
GOLD = json.loads((OUT.parent / "gold" / "mobile_representative_gold.json").read_text(encoding="utf-8"))

# Experiment B ceiling: stop cleanly after this many LLM calls OR seconds.
B_MAX_CALLS = 150
B_MAX_SECONDS = 1500


def process_candidates(candidates, tag, per_candidate_path, max_calls=None, t_start=None, max_seconds=None):
    """Run minimal-contract LLM over candidates with incremental saves + resume."""
    done = {}
    if per_candidate_path.exists():
        for line in per_candidate_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rec = json.loads(line)
                    done[rec["candidate_id"]] = rec
                except Exception:
                    pass
    mode = "a" if per_candidate_path.exists() else "w"
    out_f = open(per_candidate_path, mode, encoding="utf-8")
    try:
        for cand in candidates:
            if cand["candidate_id"] in done:
                continue
            if max_calls is not None and len(done) >= max_calls:
                print(f"[{tag}] call ceiling {max_calls} reached — stopping cleanly")
                break
            if t_start is not None and max_seconds is not None and (time.time() - t_start) >= max_seconds:
                print(f"[{tag}] time ceiling {max_seconds}s reached — stopping cleanly")
                break
            req, status, lat, raw = normalize_candidate(cand)
            rec = {
                "candidate_id": cand["candidate_id"],
                "category_gold": cand.get("category_gold"),
                "source_document": cand["source_document"],
                "page": cand["page"],
                "status": status,
                "predicted": (req or {}).get("category"),
                "correct": bool(req and req.get("category") == cand.get("category_gold")) if not str(cand.get("category_gold", "")).startswith("MULTI") else None,
                "requirement": req,
                "raw_output": raw,
                "latency": lat,
                "timeout": status == "timeout",
            }
            done[cand["candidate_id"]] = rec
            out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_f.flush()
            print(f"[{tag}] {cand['candidate_id']} gold={cand.get('category_gold')} pred={(req or {}).get('category')} {status} ({lat:.1f}s) [{len(done)} done]")
    finally:
        out_f.close()
    return done


def summarize(done_map, candidates, tag):
    """Metrics over completed candidates (single-gold only for accuracy)."""
    recs = list(done_map.values())
    single = [r for r in recs if not str(r.get("category_gold", "")).startswith("MULTI")]
    n = len(single)
    correct = sum(1 for r in single if r["correct"])
    per_cat = {}
    for r in single:
        per_cat.setdefault(r["category_gold"], {"n": 0, "correct": 0})
        per_cat[r["category_gold"]]["n"] += 1
        per_cat[r["category_gold"]]["correct"] += 1 if r["correct"] else 0
    lat = sorted(r["latency"] for r in recs)
    ok_recs = [r for r in recs if r["status"] == "ok" and r["requirement"]]
    # Deterministic post-processing over ok records
    cand_by_id = {c["candidate_id"]: c for c in candidates}
    pairs = [(r["requirement"], cand_by_id[r["candidate_id"]]) for r in ok_recs if r["candidate_id"] in cand_by_id]
    final_reqs, final_evs = post_process(pairs) if pairs else ([], [])
    cats = sorted(set(r["category"] for r in final_reqs))
    return {
        "tag": tag,
        "completed": len(recs),
        "accuracy": {"n": n, "correct": correct, "rate": correct / n if n else 0},
        "per_category": {k: {"n": v["n"], "correct": v["correct"]} for k, v in per_cat.items()},
        "technical_collapse": sum(1 for r in single if r.get("predicted") == "TECHNICAL" and r["category_gold"] != "TECHNICAL"),
        "unknown": sum(1 for r in single if r.get("predicted") == "UNKNOWN"),
        "timeouts": sum(1 for r in recs if r.get("timeout")),
        "malformed": sum(1 for r in recs if str(r.get("status", "")).startswith("malformed")),
        "empty": sum(1 for r in recs if r.get("status") in ("empty", "wrong_shape")),
        "multi": sum(1 for r in recs if r.get("status") == "multi"),
        "final_requirements": len(final_reqs),
        "final_evidence": len(final_evs),
        "final_categories": cats,
        "latencies": lat,
        "avg_latency": sum(lat) / len(lat) if lat else 0,
        "p95_latency": lat[int(len(lat) * 0.95)] if lat else 0,
    }


def experiment_a():
    """Representative set: the exact 12 Stage 3D chunks as parents."""
    full = json.loads((OUT.parent / "stage3e" / "selected_chunks_full_3e.json").read_text(encoding="utf-8"))
    assert len(full) == 12, f"Expected 12 Stage 3D chunks, got {len(full)}"
    expected_3d = [r["chunk_id"] for r in json.loads((OUT.parent / "stage3d" / "selection_rationale_3d.json").read_text(encoding="utf-8"))]
    got = [c["chunk_id"] for c in full]
    print(f"Chunk match with Stage 3D: {got == expected_3d}")
    assert got == expected_3d, "Stage 3D chunk set changed — aborting"
    candidates, rejected = [], []
    seq = 0
    for ch in full:
        acc, rej = segment_parent_chunk({
            "chunk_id": ch["chunk_id"], "source_document": ch["source_document"],
            "page_number": ch["page_number"], "text": ch["text"]})
        rejected.extend([{**r, "experiment": "A"} for r in rej])
        for a in acc:
            seq += 1
            hits = a["deterministic_signal_categories"]
            candidates.append({**a, "candidate_id": f"3k-A-{seq:02d}",
                               "category_gold": hits[0] if len(hits) == 1 else f"MULTI:{'+'.join(hits)}"})
    print(f"Experiment A: 12 parents -> {len(candidates)} candidates, {len(rejected)} rejected")
    OUT.joinpath("representative_candidates_3k.json").write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT.joinpath("representative_rejected_3k.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8")
    done = process_candidates(candidates, "A-rep", OUT / "representative_per_candidate_3k.jsonl")
    summary = summarize(done, candidates, "A-rep")
    OUT.joinpath("comparison_3k.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"A accuracy (single-gold): {summary['accuracy']['correct']}/{summary['accuracy']['n']} collapse {summary['technical_collapse']}")
    return candidates, done, summary


def experiment_b():
    """Full Mobile tender with ceiling + resume."""
    from evaluation.generic_extraction import ingest_tender
    mobile = Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations")
    t0 = time.time()
    ing = ingest_tender(mobile, "Mobile-Stage3K-Full")
    dt_ing = time.time() - t0
    print(f"Full ingestion: {dt_ing:.1f}s")
    t0 = time.time()
    acc, rej, skipped = discover_candidates(doc_results=ing["doc_results"])
    for i, a in enumerate(acc):
        a["candidate_id"] = f"3k-F-{i+1:04d}"
        hits = a["deterministic_signal_categories"]
        a["category_gold"] = hits[0] if len(hits) == 1 else f"MULTI:{'+'.join(hits)}"
    print(f"Full: {len(acc)} accepted, {len(rej)} rejected, {len(skipped)} tiny-skipped (seg {time.time()-t0:.1f}s)")
    OUT.joinpath("full_mobile_meta_3k.json").write_text(json.dumps({
        "accepted": len(acc), "rejected": len(rej), "skipped_tiny": len(skipped),
        "ingestion_s": dt_ing, "llm_budget_calls": B_MAX_CALLS, "llm_budget_seconds": B_MAX_SECONDS,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    t_start = time.time()
    done = process_candidates(acc, "B-full", OUT / "full_mobile_per_candidate_3k.jsonl",
                              max_calls=B_MAX_CALLS, t_start=t_start, max_seconds=B_MAX_SECONDS)
    summary = summarize(done, acc, "B-full")
    summary["accepted_total"] = len(acc)
    summary["stopped_at_ceiling"] = len(done) < len(acc)
    summary["ingestion_s"] = dt_ing
    OUT.joinpath("full_mobile_summary_3k.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"B completed {len(done)}/{len(acc)} (ceiling stop: {summary['stopped_at_ceiling']})")
    return acc, done, summary


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "A"
    from evaluation.llm_generic_extraction import get_ollama_model, get_ollama_base_url, check_ollama_available
    model = get_ollama_model()
    base = get_ollama_base_url()
    ok, msg = check_ollama_available()
    print(f"Ollama model={model} base={base} available={ok} {msg}")
    if not ok:
        print("Ollama unavailable — recording explicitly, no fabrication.")
        OUT.joinpath(f"capability_unavailable_3k_{which}.json").write_text(
            json.dumps({"model": model, "base": base, "available": False, "message": msg}, indent=2))
        return
    if which == "A":
        experiment_a()
    elif which == "B":
        experiment_b()
    else:
        raise SystemExit("usage: run_3k.py [A|B]")
    print(f"Saved 3K artifacts to {OUT}")


if __name__ == "__main__":
    main()
