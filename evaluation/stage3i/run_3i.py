"""
Stage 3I — Variant B on deterministically pre-segmented single-purpose candidates.
A/B reuse the 3H minimal interface; C reuses the unchanged Variant B path.
Same candidates, fixed order, same model/endpoint/decoding. No production change.
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.stage3h.single_req_tasks import (
    TASK_A_SYSTEM, TASK_B_SYSTEM, TIMEOUT_SECONDS,
    call_normalizer, parse_single_requirement,
)
from evaluation.llm_generic_extraction import (
    get_ollama_model, get_ollama_base_url, check_ollama_available,
    call_ollama_for_chunk, parse_llm_json, validate_requirement,
)


def run_ab(candidates, system_prompt, label):
    results = []
    for c in candidates:
        out = call_normalizer(c["source_text"], system_prompt, timeout=TIMEOUT_SECONDS)
        if out.get("timeout"):
            req, status = None, "timeout"
        elif out.get("http_error"):
            req, status = None, f"http_{out['http_error']}"
        else:
            req, status = parse_single_requirement(out["raw"])
        results.append({
            "candidate_id": c["candidate_id"], "category_gold": c["category_gold"],
            "source_text": c["source_text"], "raw_output": out["raw"],
            "requirement": req, "status": status,
            "predicted": (req or {}).get("category"),
            "correct": bool(req and req.get("category") == c["category_gold"]),
            "latency": out["latency"], "timeout": out.get("timeout", False),
        })
        print(f"[{label}] {c['candidate_id']} gold={c['category_gold']} pred={(req or {}).get('category')} {status} ({out['latency']:.1f}s)")
    return results


def run_c(candidates):
    results = []
    for c in candidates:
        chunk = {
            "chunk_id": c["candidate_id"],
            "source_document": c["source_document"],
            "page_number": c["page"],
            "text": c["source_text"],
        }
        t0 = time.time()
        try:
            out = call_ollama_for_chunk(chunk)  # default Variant B, unchanged
            lat = time.time() - t0
        except Exception as e:
            lat = time.time() - t0
            results.append({
                "candidate_id": c["candidate_id"], "category_gold": c["category_gold"],
                "source_text": c["source_text"], "raw_output": None,
                "requirements": [], "evidence": [], "status": "timeout",
                "predicted": None, "correct": False, "latency": lat, "timeout": True,
            })
            print(f"[C] {c['candidate_id']} gold={c['category_gold']} TIMEOUT ({lat:.1f}s)")
            continue
        if out is None:
            results.append({
                "candidate_id": c["candidate_id"], "category_gold": c["category_gold"],
                "source_text": c["source_text"], "raw_output": None,
                "requirements": [], "evidence": [], "status": "timeout",
                "predicted": None, "correct": False, "latency": lat, "timeout": True,
            })
            print(f"[C] {c['candidate_id']} gold={c['category_gold']} TIMEOUT ({lat:.1f}s)")
            continue
        parsed, pstatus = parse_llm_json(out["raw"])
        if not parsed:
            results.append({
                "candidate_id": c["candidate_id"], "category_gold": c["category_gold"],
                "source_text": c["source_text"], "raw_output": out["raw"],
                "requirements": [], "evidence": [], "status": f"malformed_{pstatus}",
                "predicted": None, "correct": False, "latency": lat, "timeout": False,
            })
            print(f"[C] {c['candidate_id']} gold={c['category_gold']} MALFORMED ({lat:.1f}s)")
            continue
        reqs = parsed.get("requirements", []) or []
        evs = parsed.get("evidence", []) or []
        # Validate each requirement against its own candidate-as-chunk (source-local)
        validated = []
        for r in reqs:
            ok, _ = validate_requirement(r, chunk)
            validated.append(ok)
        first = reqs[0] if reqs else None
        pred = first.get("category") if isinstance(first, dict) else None
        from evaluation.stage3h.single_req_tasks import ALLOWED_CATEGORIES
        if len(reqs) == 0:
            status = "empty"
        elif len(reqs) > 1:
            status = "multi"
        elif pred not in ALLOWED_CATEGORIES:
            status = "bad_category"
        else:
            status = "ok"
        # Evidence linkage check: each evidence must reference a requirement from THIS candidate
        local_ids = {r.get("candidate_id") for r in reqs if isinstance(r, dict) and r.get("candidate_id")}
        ev_ok = 0
        for e in evs:
            if not isinstance(e, dict):
                continue
            rc = e.get("requirement_candidate_id")
            if rc in local_ids and e.get("source_document") == chunk["source_document"]:
                ev_ok += 1
        results.append({
            "candidate_id": c["candidate_id"], "category_gold": c["category_gold"],
            "source_text": c["source_text"], "raw_output": out["raw"],
            "requirements": reqs, "evidence": evs, "status": status,
            "predicted": pred if pred in ALLOWED_CATEGORIES else None,
            "correct": bool(pred == c["category_gold"]),
            "evidence_local_ok": ev_ok, "evidence_total": len(evs),
            "requirements_validated": validated,
            "latency": lat, "timeout": False,
        })
        print(f"[C] {c['candidate_id']} gold={c['category_gold']} pred={pred} {status} ({lat:.1f}s) n_reqs={len(reqs)} n_evs={len(evs)} ev_ok={ev_ok}")
    return results


def main():
    out_dir = Path(__file__).parent
    candidates = json.loads((out_dir / "generated_candidates.json").read_text(encoding="utf-8"))
    print(f"Candidates: {len(candidates)} (fixed order A/B/C)")

    model = get_ollama_model()
    base = get_ollama_base_url()
    ok, msg = check_ollama_available()
    print(f"Ollama model={model} base={base} available={ok} {msg}")
    if not ok:
        print("Ollama unavailable — recording explicitly, no fabrication.")
        out_dir.joinpath("capability_unavailable_3i.json").write_text(
            json.dumps({"model": model, "base": base, "available": False, "message": msg}, indent=2))
        return

    print("\n=== Test A (single-req normalization) ===")
    results_a = run_ab(candidates, TASK_A_SYSTEM, "A")
    print("\n=== Test B (single-req + definitions) ===")
    results_b = run_ab(candidates, TASK_B_SYSTEM, "B")
    print("\n=== Test C (Variant B on pre-segmented candidates) ===")
    results_c = run_c(candidates)

    out_dir.joinpath("variant_b_outputs_3i.json").write_text(json.dumps(results_c, ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir.joinpath("task_a_3i.json").write_text(json.dumps(results_a, ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir.joinpath("task_b_3i.json").write_text(json.dumps(results_b, ensure_ascii=False, indent=2), encoding="utf-8")

    def summarize_ab(results):
        n = len(results)
        correct = sum(1 for r in results if r["correct"])
        per_cat = {}
        for r in results:
            per_cat.setdefault(r["category_gold"], {"n": 0, "correct": 0})
            per_cat[r["category_gold"]]["n"] += 1
            per_cat[r["category_gold"]]["correct"] += 1 if r["correct"] else 0
        lat = sorted(r["latency"] for r in results)
        return {
            "total": n, "correct": correct, "accuracy": correct / n if n else 0,
            "per_category": {k: {"n": v["n"], "correct": v["correct"], "accuracy": v["correct"] / v["n"]} for k, v in per_cat.items()},
            "technical_collapse": sum(1 for r in results if r.get("predicted") == "TECHNICAL" and r["category_gold"] != "TECHNICAL"),
            "unknown": sum(1 for r in results if r.get("predicted") == "UNKNOWN"),
            "timeouts": sum(1 for r in results if r.get("timeout")),
            "malformed": sum(1 for r in results if str(r.get("status", "")).startswith("malformed")),
            "empty": sum(1 for r in results if r.get("status") in ("empty", "wrong_shape")),
            "multi": sum(1 for r in results if r.get("status") == "multi"),
            "latencies": lat, "avg_latency": sum(lat) / len(lat) if lat else 0,
            "p95_latency": lat[int(len(lat) * 0.95)] if lat else 0,
        }

    def summarize_c(results):
        s = summarize_ab(results)
        s["requirement_count"] = sum(len(r.get("requirements", [])) for r in results)
        s["expected_requirement_count"] = len(results)
        s["exact_one_rate"] = sum(1 for r in results if len(r.get("requirements", [])) == 1) / len(results) if results else 0
        s["zero_rate"] = sum(1 for r in results if len(r.get("requirements", [])) == 0) / len(results) if results else 0
        s["evidence_total"] = sum(len(r.get("evidence", [])) for r in results)
        s["evidence_local_ok"] = sum(r.get("evidence_local_ok", 0) for r in results)
        return s

    summary = {
        "model": model, "base": base, "timeout": TIMEOUT_SECONDS, "temperature": 0,
        "n_candidates": len(candidates),
        "test_A": summarize_ab(results_a),
        "test_B": summarize_ab(results_b),
        "test_C": summarize_c(results_c),
    }

    def confusion(results):
        cats = sorted(set(r["category_gold"] for r in results))
        matrix = {g: {} for g in cats}
        for r in results:
            pred = r.get("predicted") or ("TIMEOUT" if r.get("timeout") else r.get("status", "INVALID").upper())
            matrix[r["category_gold"]][pred] = matrix[r["category_gold"]].get(pred, 0) + 1
        return matrix

    summary["confusion_A"] = confusion(results_a)
    summary["confusion_B"] = confusion(results_b)
    summary["confusion_C"] = confusion(results_c)

    out_dir.joinpath("comparison_3i.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nA accuracy: {summary['test_A']['correct']}/{summary['test_A']['total']} = {summary['test_A']['accuracy']:.2f}")
    print(f"B accuracy: {summary['test_B']['correct']}/{summary['test_B']['total']} = {summary['test_B']['accuracy']:.2f}")
    print(f"C accuracy: {summary['test_C']['correct']}/{summary['test_C']['total']} = {summary['test_C']['accuracy']:.2f}")
    print(f"Saved 3I artifacts to {out_dir}")


if __name__ == "__main__":
    main()
