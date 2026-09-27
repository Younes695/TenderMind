"""
Stage 3H — Single-requirement normalization: Test A vs Test B vs Variant B (Test C).
Same snippets, fixed order, same model/endpoint/decoding. No production change.
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


def run_test_a(snippets):
    results = []
    for s in snippets:
        out = call_normalizer(s["source_text"], TASK_A_SYSTEM, timeout=TIMEOUT_SECONDS)
        req, status = parse_single_requirement(out["raw"]) if not out.get("timeout") and out.get("raw") is not None else (None, "timeout" if out.get("timeout") else "empty")
        # parse_single_requirement already handles None/empty; unify:
        if out.get("timeout"):
            req, status = None, "timeout"
        elif out.get("http_error"):
            req, status = None, f"http_{out['http_error']}"
        results.append({
            "test_id": s["test_id"], "category_gold": s["category_gold"],
            "source_text": s["source_text"], "raw_output": out["raw"],
            "requirement": req, "status": status,
            "predicted": (req or {}).get("category"),
            "correct": bool(req and req.get("category") == s["category_gold"]),
            "latency": out["latency"], "timeout": out.get("timeout", False),
        })
        print(f"[A] {s['test_id']} gold={s['category_gold']} pred={(req or {}).get('category')} {status} ({out['latency']:.1f}s)")
    return results


def run_test_b(snippets):
    results = []
    for s in snippets:
        out = call_normalizer(s["source_text"], TASK_B_SYSTEM, timeout=TIMEOUT_SECONDS)
        if out.get("timeout"):
            req, status = None, "timeout"
        elif out.get("http_error"):
            req, status = None, f"http_{out['http_error']}"
        else:
            req, status = parse_single_requirement(out["raw"])
        results.append({
            "test_id": s["test_id"], "category_gold": s["category_gold"],
            "source_text": s["source_text"], "raw_output": out["raw"],
            "requirement": req, "status": status,
            "predicted": (req or {}).get("category"),
            "correct": bool(req and req.get("category") == s["category_gold"]),
            "latency": out["latency"], "timeout": out.get("timeout", False),
        })
        print(f"[B] {s['test_id']} gold={s['category_gold']} pred={(req or {}).get('category')} {status} ({out['latency']:.1f}s)")
    return results


def run_test_c_timed(snippets):
    import time as _time
    from evaluation.llm_generic_extraction import call_ollama_for_chunk as _call
    results = []
    for s in snippets:
        chunk = {
            "chunk_id": f"3h-{s['test_id'].lower()}",
            "source_document": s["source_document"],
            "page_number": s["page"],
            "text": s["source_text"],
        }
        t0 = _time.time()
        try:
            out = _call(chunk)
            lat = _time.time() - t0
        except Exception as e:
            lat = _time.time() - t0
            results.append({
                "test_id": s["test_id"], "category_gold": s["category_gold"],
                "source_text": s["source_text"], "raw_output": None,
                "requirements": [], "evidence": [], "status": "timeout",
                "predicted": None, "correct": False, "latency": lat, "timeout": True,
            })
            print(f"[C] {s['test_id']} gold={s['category_gold']} TIMEOUT ({lat:.1f}s)")
            continue
        if out is None:
            results.append({
                "test_id": s["test_id"], "category_gold": s["category_gold"],
                "source_text": s["source_text"], "raw_output": None,
                "requirements": [], "evidence": [], "status": "timeout",
                "predicted": None, "correct": False, "latency": lat, "timeout": True,
            })
            print(f"[C] {s['test_id']} gold={s['category_gold']} TIMEOUT ({lat:.1f}s)")
            continue
        from evaluation.llm_generic_extraction import parse_llm_json as _parse
        parsed, pstatus = _parse(out["raw"])
        if not parsed:
            results.append({
                "test_id": s["test_id"], "category_gold": s["category_gold"],
                "source_text": s["source_text"], "raw_output": out["raw"],
                "requirements": [], "evidence": [], "status": f"malformed_{pstatus}",
                "predicted": None, "correct": False, "latency": lat, "timeout": False,
            })
            print(f"[C] {s['test_id']} gold={s['category_gold']} MALFORMED ({lat:.1f}s)")
            continue
        reqs = parsed.get("requirements", []) or []
        evs = parsed.get("evidence", []) or []
        # Validate each requirement minimally (category allowed, provenance present)
        first = reqs[0] if reqs else None
        pred = first.get("category") if isinstance(first, dict) else None
        from evaluation.stage3h.single_req_tasks import ALLOWED_CATEGORIES
        status = "ok" if (len(reqs) == 1 and pred in ALLOWED_CATEGORIES) else (
            "empty" if len(reqs) == 0 else ("multi" if len(reqs) > 1 else "bad_category"))
        results.append({
            "test_id": s["test_id"], "category_gold": s["category_gold"],
            "source_text": s["source_text"], "raw_output": out["raw"],
            "requirements": reqs, "evidence": evs, "status": status,
            "predicted": pred if pred in ALLOWED_CATEGORIES else None,
            "correct": bool(pred == s["category_gold"]),
            "latency": lat, "timeout": False,
        })
        print(f"[C] {s['test_id']} gold={s['category_gold']} pred={pred} {status} ({lat:.1f}s) n_reqs={len(reqs)} n_evs={len(evs)}")
    return results


def main():
    out_dir = Path(__file__).parent
    snippets = json.loads((out_dir / "snippets_3h.json").read_text(encoding="utf-8"))
    print(f"Snippets: {len(snippets)} (fixed order A/B/C)")

    model = get_ollama_model()
    base = get_ollama_base_url()
    ok, msg = check_ollama_available()
    print(f"Ollama model={model} base={base} available={ok} {msg}")
    if not ok:
        print("Ollama unavailable — recording explicitly, no fabrication.")
        out_dir.joinpath("capability_unavailable_3h.json").write_text(
            json.dumps({"model": model, "base": base, "available": False, "message": msg}, indent=2))
        return

    print("\n=== Test A (single-req normalization) ===")
    results_a = run_test_a(snippets)
    print("\n=== Test B (single-req + definitions) ===")
    results_b = run_test_b(snippets)
    print("\n=== Test C (Variant B extraction on single-req snippets) ===")
    results_c = run_test_c_timed(snippets)

    out_dir.joinpath("task_a_3h.json").write_text(json.dumps(results_a, ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir.joinpath("task_b_3h.json").write_text(json.dumps(results_b, ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir.joinpath("task_c_3h.json").write_text(json.dumps(results_c, ensure_ascii=False, indent=2), encoding="utf-8")

    def summarize(results, key="predicted"):
        n = len(results)
        correct = sum(1 for r in results if r["correct"])
        tech_collapse = sum(1 for r in results if r.get("predicted") == "TECHNICAL" and r["category_gold"] != "TECHNICAL")
        unknown = sum(1 for r in results if r.get("predicted") == "UNKNOWN")
        timeouts = sum(1 for r in results if r.get("timeout"))
        malformed = sum(1 for r in results if str(r.get("status", "")).startswith("malformed"))
        empty = sum(1 for r in results if r.get("status") in ("empty", "wrong_shape"))
        multi = sum(1 for r in results if r.get("status") == "multi")
        lat = sorted(r["latency"] for r in results)
        per_cat = {}
        for r in results:
            per_cat.setdefault(r["category_gold"], {"n": 0, "correct": 0})
            per_cat[r["category_gold"]]["n"] += 1
            per_cat[r["category_gold"]]["correct"] += 1 if r["correct"] else 0
        total_reqs = sum(len(r.get("requirements", []) or []) if "requirements" in r else (1 if r.get("requirement") else 0) for r in results)
        return {
            "total": n, "correct": correct, "accuracy": correct / n if n else 0,
            "per_category": {k: {"n": v["n"], "correct": v["correct"], "accuracy": v["correct"] / v["n"]} for k, v in per_cat.items()},
            "requirement_count": total_reqs, "expected_requirement_count": n,
            "technical_count": sum(1 for r in results if r.get("predicted") == "TECHNICAL"),
            "technical_collapse": tech_collapse, "unknown": unknown,
            "empty": empty, "malformed": malformed, "multi": multi, "timeouts": timeouts,
            "latencies": lat, "avg_latency": sum(lat) / len(lat) if lat else 0,
            "p95_latency": lat[int(len(lat) * 0.95)] if lat else 0,
        }

    summary = {
        "model": model, "base": base, "timeout": TIMEOUT_SECONDS, "temperature": 0,
        "n_snippets": len(snippets),
        "test_A": summarize(results_a),
        "test_B": summarize(results_b),
        "test_C": summarize(results_c),
    }
    # Confusion matrices
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

    out_dir.joinpath("comparison_3h.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nA accuracy: {summary['test_A']['correct']}/{summary['test_A']['total']} = {summary['test_A']['accuracy']:.2f}")
    print(f"B accuracy: {summary['test_B']['correct']}/{summary['test_B']['total']} = {summary['test_B']['accuracy']:.2f}")
    print(f"C accuracy: {summary['test_C']['correct']}/{summary['test_C']['total']} = {summary['test_C']['accuracy']:.2f}")
    print(f"Saved 3H artifacts to {out_dir}")


if __name__ == "__main__":
    main()
