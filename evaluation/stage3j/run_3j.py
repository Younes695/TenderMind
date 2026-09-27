"""
Stage 3J — Minimal-contract Variant B on the exact 16 Stage 3I candidates.
Same candidates, fixed order, same model/endpoint/decoding. Provenance attached
deterministically; evidence derived deterministically (not model-generated).
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from evaluation.stage3j.minimal_contract_prompt import (
    MINIMAL_CONTRACT_SYSTEM, PROMPT_VERSION_3J, prompt_hash_3j,
    attach_provenance, derive_evidence,
)
from evaluation.stage3h.single_req_tasks import parse_single_requirement
from evaluation.llm_generic_extraction import (
    get_ollama_model, get_ollama_base_url, check_ollama_available,
    LLM_SYSTEM_PROMPT, prompt_hash,
)


def call_minimal_contract(source_text: str, timeout: int = 90) -> dict:
    from evaluation.llm_generic_extraction import get_ollama_model, get_ollama_base_url
    import requests
    base = get_ollama_base_url()
    mdl = get_ollama_model()
    payload = {
        "model": mdl,
        "messages": [
            {"role": "system", "content": MINIMAL_CONTRACT_SYSTEM},
            {"role": "user", "content": f'Requirement text:\n"""{source_text}"""\nReturn the normalized requirement.'},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    t0 = time.time()
    try:
        resp = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
        lat = time.time() - t0
        if resp.status_code != 200:
            return {"raw": None, "latency": lat, "timeout": False, "http_error": resp.status_code}
        data = resp.json()
        raw = ""
        if isinstance(data.get("message"), dict):
            raw = data["message"].get("content", "") or ""
        if not raw:
            raw = data.get("response", "") or ""
        return {"raw": raw, "latency": lat, "timeout": False}
    except Exception as e:
        lat = time.time() - t0
        is_timeout = "timeout" in type(e).__name__.lower() or "timeout" in str(e).lower() or "timed out" in str(e).lower()
        return {"raw": None, "latency": lat, "timeout": is_timeout, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def main():
    out_dir = Path(__file__).parent
    candidates = json.loads((Path(__file__).resolve().parents[1] / "stage3i" / "generated_candidates.json").read_text(encoding="utf-8"))
    assert len(candidates) == 16, f"Expected exact 16 Stage 3I candidates, got {len(candidates)}"
    print(f"Candidates: {len(candidates)} (exact Stage 3I set, fixed order)")

    # Baseline verification from stored artifact (not hardcoded)
    baseline = json.loads((Path(__file__).resolve().parents[1] / "stage3i" / "variant_b_outputs_3i.json").read_text(encoding="utf-8"))
    gold = {c["candidate_id"]: c["category_gold"] for c in candidates}
    b_correct = sum(1 for o in baseline for r in o["requirements"] if r.get("category") == gold[o["candidate_id"]])
    b_collapse = sum(1 for o in baseline for r in o["requirements"] if r.get("category") == "TECHNICAL" and gold[o["candidate_id"]] != "TECHNICAL")
    print(f"Baseline Variant B (stored 3I artifact): accuracy {b_correct}/16, collapse {b_collapse}/16")
    assert b_correct == 9 and b_collapse == 4, f"Baseline drift: {b_correct}/16 acc, {b_collapse} collapse"

    model = get_ollama_model()
    base = get_ollama_base_url()
    ok, msg = check_ollama_available()
    print(f"Ollama model={model} base={base} available={ok} {msg}")
    print(f"Minimal-contract prompt hash: {prompt_hash_3j(MINIMAL_CONTRACT_SYSTEM)} version {PROMPT_VERSION_3J}")
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd", "Variant B must remain unchanged"
    if not ok:
        print("Ollama unavailable — recording explicitly, no fabrication.")
        out_dir.joinpath("capability_unavailable_3j.json").write_text(
            json.dumps({"model": model, "base": base, "available": False, "message": msg}, indent=2))
        return

    print("\n=== Stage 3J minimal contract ===")
    results = []
    for c in candidates:
        out = call_minimal_contract(c["source_text"])
        if out.get("timeout"):
            req, status = None, "timeout"
        elif out.get("http_error"):
            req, status = None, f"http_{out['http_error']}"
        else:
            req, status = parse_single_requirement(out["raw"])
        entry = {
            "candidate_id": c["candidate_id"], "category_gold": c["category_gold"],
            "source_text": c["source_text"], "raw_output": out["raw"],
            "requirement": req, "status": status,
            "predicted": (req or {}).get("category"),
            "correct": bool(req and req.get("category") == c["category_gold"]),
            "latency": out["latency"], "timeout": out.get("timeout", False),
        }
        if req is not None and status == "ok":
            full = attach_provenance({**req, "requirement_id": c["candidate_id"]}, c)
            entry["requirement_full"] = full
            entry["evidence"] = derive_evidence(full)
        else:
            entry["requirement_full"] = None
            entry["evidence"] = None
        results.append(entry)
        print(f"[3J] {c['candidate_id']} gold={c['category_gold']} pred={(req or {}).get('category')} {status} ({out['latency']:.1f}s)")

    out_dir.joinpath("task_c_3j.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    n = len(results)
    correct = sum(1 for r in results if r["correct"])
    per_cat = {}
    for r in results:
        per_cat.setdefault(r["category_gold"], {"n": 0, "correct": 0})
        per_cat[r["category_gold"]]["n"] += 1
        per_cat[r["category_gold"]]["correct"] += 1 if r["correct"] else 0
    lat = sorted(r["latency"] for r in results)
    summary = {
        "model": model, "base": base, "timeout": 90, "temperature": 0,
        "n_candidates": n, "correct": correct, "accuracy": correct / n if n else 0,
        "per_category": {k: {"n": v["n"], "correct": v["correct"], "accuracy": v["correct"] / v["n"]} for k, v in per_cat.items()},
        "technical_collapse": sum(1 for r in results if r.get("predicted") == "TECHNICAL" and r["category_gold"] != "TECHNICAL"),
        "unknown": sum(1 for r in results if r.get("predicted") == "UNKNOWN"),
        "timeouts": sum(1 for r in results if r.get("timeout")),
        "malformed": sum(1 for r in results if str(r.get("status", "")).startswith("malformed")),
        "empty": sum(1 for r in results if r.get("status") in ("empty", "wrong_shape")),
        "multi": sum(1 for r in results if r.get("status") == "multi"),
        "provenance_attached": sum(1 for r in results if r.get("requirement_full")),
        "evidence_derived": sum(1 for r in results if r.get("evidence")),
        "latencies": lat, "avg_latency": sum(lat) / len(lat) if lat else 0,
        "p95_latency": lat[int(len(lat) * 0.95)] if lat else 0,
    }

    def confusion(results):
        cats = sorted(set(r["category_gold"] for r in results))
        matrix = {g: {} for g in cats}
        for r in results:
            pred = r.get("predicted") or ("TIMEOUT" if r.get("timeout") else r.get("status", "INVALID").upper())
            matrix[r["category_gold"]][pred] = matrix[r["category_gold"]].get(pred, 0) + 1
        return matrix

    summary["confusion"] = confusion(results)
    out_dir.joinpath("comparison_3j.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir.joinpath("confusion_matrix_3j.json").write_text(json.dumps(summary["confusion"], ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir.joinpath("latency_3j.json").write_text(json.dumps(
        {"latencies": lat, "avg_latency": summary["avg_latency"], "p95_latency": summary["p95_latency"],
         "timeouts": summary["timeouts"]}, ensure_ascii=False, indent=2), encoding="utf-8")

    # Per-candidate table across 3H-A, 3I-B, 3J (3H-A/B from stored 3H artifacts on overlapping candidates is not 1:1;
    # the required table uses 3H-A on the 12-snippet set where candidate sentences overlap — built in the report.
    # Here store the 3J side; the report joins them.)
    print(f"\n3J accuracy: {correct}/{n} = {summary['accuracy']:.2f}")
    print(f"3J collapse: {summary['technical_collapse']}")
    print(f"Saved 3J artifacts to {out_dir}")


if __name__ == "__main__":
    main()
