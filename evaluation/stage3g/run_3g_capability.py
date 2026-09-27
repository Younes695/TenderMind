"""
Stage 3G — Controlled single-label classification capability test.
Task A: snippet + bare label list. Task B: same snippets + concise definitions.
Same model/endpoint/temperature/timeout/order for both. No production change.
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.stage3g.classification_tasks import (
    ALLOWED_LABELS, TASK_A_SYSTEM, TASK_B_SYSTEM, TIMEOUT_SECONDS,
    build_user_message, normalize_output, call_classifier,
)
from evaluation.llm_generic_extraction import get_ollama_model, get_ollama_base_url, check_ollama_available


def run_task(snippets, system_prompt, label):
    results = []
    for s in snippets:
        out = call_classifier(s["source_text"], system_prompt, timeout=TIMEOUT_SECONDS)
        norm, reason = normalize_output(out["raw"])
        predicted = norm
        timed_out = out.get("timeout", False)
        invalid = (norm is None) and not timed_out
        results.append({
            "test_id": s["test_id"],
            "category_gold": s["category_gold"],
            "source_text": s["source_text"],
            "raw_output": out["raw"],
            "predicted": predicted,
            "correct": (predicted == s["category_gold"]),
            "normalize_reason": reason,
            "latency": out["latency"],
            "timeout": timed_out,
            "invalid": invalid,
        })
        status = "OK" if predicted == s["category_gold"] else ("TIMEOUT" if timed_out else ("INVALID" if invalid else "WRONG"))
        print(f"[{label}] {s['test_id']} gold={s['category_gold']} pred={predicted} {status} ({out['latency']:.1f}s) raw={ (out['raw'] or '')[:80]!r}")
    return results


def confusion(results):
    cats = sorted(set(r["category_gold"] for r in results))
    matrix = {g: {p: 0 for p in cats + ["UNKNOWN", "INVALID", "TIMEOUT"]} for g in cats}
    for r in results:
        key = r["predicted"] if r["predicted"] else ("TIMEOUT" if r["timeout"] else "INVALID")
        if key not in matrix[r["category_gold"]]:
            matrix[r["category_gold"]][key] = 0
        matrix[r["category_gold"]][key] += 1
    return matrix


def main():
    out_dir = Path(__file__).parent
    snippets = json.loads((out_dir / "snippets_3g.json").read_text(encoding="utf-8"))
    print(f"Snippets: {len(snippets)} (order fixed for both tasks)")

    model = get_ollama_model()
    base = get_ollama_base_url()
    ok, msg = check_ollama_available()
    print(f"Ollama model={model} base={base} available={ok} {msg}")
    if not ok:
        print("Ollama unavailable — recording explicitly, no fabrication.")
        out_dir.joinpath("capability_unavailable_3g.json").write_text(
            json.dumps({"model": model, "base": base, "available": False, "message": msg}, indent=2))
        return

    print("\n=== Task A (bare labels) ===")
    t0 = time.time()
    results_a = run_task(snippets, TASK_A_SYSTEM, "A")
    time_a = time.time() - t0

    print("\n=== Task B (concise definitions) ===")
    t0 = time.time()
    results_b = run_task(snippets, TASK_B_SYSTEM, "B")
    time_b = time.time() - t0

    def summarize(results):
        n = len(results)
        correct = sum(1 for r in results if r["correct"])
        tech_collapse = sum(1 for r in results if r["predicted"] == "TECHNICAL" and r["category_gold"] != "TECHNICAL")
        unknown = sum(1 for r in results if r["predicted"] == "UNKNOWN")
        timeouts = sum(1 for r in results if r["timeout"])
        invalid = sum(1 for r in results if r["invalid"])
        lat = sorted(r["latency"] for r in results)
        per_cat = {}
        for r in results:
            per_cat.setdefault(r["category_gold"], {"n": 0, "correct": 0})
            per_cat[r["category_gold"]]["n"] += 1
            per_cat[r["category_gold"]]["correct"] += 1 if r["correct"] else 0
        return {
            "total": n, "correct": correct, "accuracy": correct / n if n else 0,
            "per_category": {k: {"n": v["n"], "correct": v["correct"], "accuracy": v["correct"] / v["n"]} for k, v in per_cat.items()},
            "technical_collapse": tech_collapse, "unknown": unknown,
            "timeouts": timeouts, "invalid": invalid,
            "latencies": lat, "avg_latency": sum(lat) / len(lat) if lat else 0,
            "p95_latency": lat[int(len(lat) * 0.95)] if lat else 0,
        }

    summary = {
        "model": model, "base": base, "timeout": TIMEOUT_SECONDS, "temperature": 0,
        "n_snippets": len(snippets),
        "task_A": summarize(results_a),
        "task_B": summarize(results_b),
        "confusion_A": confusion(results_a),
        "confusion_B": confusion(results_b),
        "total_time_A": time_a, "total_time_B": time_b,
    }
    out_dir.joinpath("task_a_3g.json").write_text(json.dumps(results_a, ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir.joinpath("task_b_3g.json").write_text(json.dumps(results_b, ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir.joinpath("capability_summary_3g.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nTask A accuracy: {summary['task_A']['correct']}/{summary['task_A']['total']} = {summary['task_A']['accuracy']:.2f}")
    print(f"Task B accuracy: {summary['task_B']['correct']}/{summary['task_B']['total']} = {summary['task_B']['accuracy']:.2f}")
    print(f"Saved 3G artifacts to {out_dir}")


if __name__ == "__main__":
    main()
