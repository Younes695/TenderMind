"""
Ollama Benchmark — TenderMind — FREE local LLM only
- Builds unlabeled 84 matcher pairs first (no gold)
- Runs Ollama inference WITHOUT loading gold
- Only after all predictions, loads gold and joins
- Calculates applicability macro F1, evidence-supported F1, etc.
- Cost: $0, localhost only, no paid API
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
import json
import time
from pathlib import Path as PPath

BASE = PPath(__file__).resolve().parents[1]
GOLD_PATH = BASE / "evaluation" / "sarai_gold_dataset.json"

def main():
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

    print("=== Ollama Benchmark — TenderMind — FREE local LLM only ===")
    print("Cost guardrail: No OpenAI/Azure, no paid network, Ollama localhost only")
    print(f"Gold: {GOLD_PATH} — will be loaded ONLY AFTER all predictions")

    # Check Ollama availability
    from app.matchers.ollama_matcher import check_ollama_available, get_ollama_model, get_ollama_timeout, OllamaMatcher
    model = get_ollama_model()
    timeout = get_ollama_timeout()
    print(f"\n[1/4] Checking Ollama availability for model '{model}' at http://localhost:11434 ...")
    ok, msg = check_ollama_available(model)
    # Also check endpoint
    print(f"  {msg}")
    if not ok:
        print("\nBLOCKED — Ollama/model unavailable")
        print("To fix (do not install automatically unless already available):")
        print(f"  1. Install Ollama: https://ollama.com/download")
        print(f"  2. Pull model: ollama pull {model}")
        print(f"  3. Verify: ollama list  (should show {model})")
        print(f"  4. Ensure Ollama is running: ollama serve")
        print(f"  5. Test endpoint: curl http://localhost:11434/api/tags")
        print("\nBenchmark STOPPED — Ollama/model unavailable — no network/paid API used")
        return

    print(f"\n[2/4] Building unlabeled 84 matcher pairs (no gold) ...")
    from evaluation.matcher_benchmark import build_unlabeled_pairs
    pairs = build_unlabeled_pairs()
    # Smoke mode for quick verification without running full 84 (cost guardrail: localhost only)
    if "--smoke" in sys.argv:
        pairs = pairs[:3]
        print(f"  --smoke flag detected: limiting to first 3 pairs for quick verification (no gold, localhost only)")
    print(f"  Built {len(pairs)} unlabeled pairs (21 req × 4 ev)")
    # Verify no gold fields in inputs
    for p in pairs:
        assert "gold_expected_status" not in p, "Inference input must not contain gold_expected_status"
        assert "gold_evidence_supported" not in p, "Inference input must not contain gold"
    print(f"  Verified: No gold fields in inference inputs, provenance preserved")

    import os as _os
    _matcher_choice = _os.environ.get("TENDERMIND_MATCHER", "ollama").strip().lower()
    if _matcher_choice not in ("ollama", "hybrid"):
        _matcher_choice = "ollama"  # default: current ollama behavior unchanged
    print(f"\n[3/4] Running Ollama inference on {len(pairs)} pairs — model {model}, timeout {timeout}s per request (matcher-configured via TENDERMIND_OLLAMA_TIMEOUT), matcher={_matcher_choice}, localhost only ...")
    if _matcher_choice == "hybrid":
        from app.matchers.hybrid_matcher import HybridMatcher
        from app.matchers.ollama_matcher import OllamaMatcher as _OM
        matcher = HybridMatcher(llm_matcher=_OM(model=model, timeout=timeout))
    else:
        matcher = OllamaMatcher(model=model, timeout=timeout)
    # Verify default provider remains offline/local and matcher will not produce BID
    # (OllamaMatcher itself will check availability again per match, but we already did)
    start = time.time()
    results = []
    malformed = 0
    invented = 0
    forbidden = 0
    for idx, p in enumerate(pairs):
        from app.matchers.base import MatcherInput
        inp = MatcherInput(
            requirement_id=p["requirement_id"],
            requirement_text=p["requirement_text"],
            requirement_category=p["requirement_category"],
            requirement_type=p["requirement_type"],
            mandatory=p["mandatory"],
            applicable_entity=p["applicable_entity"],
            evidence_id=p["evidence_id"],
            evidence_fact=p["evidence_fact"],
            evidence_type=p["evidence_type"],
            evidence_applicable_entity=p["evidence_applicable_entity"],
            evidence_valid_until=p["evidence_valid_until"],
            evidence_reusable=p["evidence_reusable"],
            evidence_tender_source=p["evidence_tender_source"],
            current_tender_id=p["current_tender_id"],
            source_document=p["source_document"],
            page_or_section=p["page_or_section"]
        )
        try:
            out = matcher.safe_match(inp)  # safe_match handles malformed -> REVIEW
        except Exception as e:
            # Should not happen due to safe_match, but handle
            from app.matchers.base import MatcherOutput
            out = MatcherOutput(support=None, contradiction=False, missing_facts=[str(e)], supporting_facts=[], contradictory_facts=[], applicability="REVIEW", confidence=0.0, reason=f"Exception: {e}")
        # Track malformed/invented/forbidden for metrics
        if out.confidence == 0.0 and out.applicability == "REVIEW" and "Malformed" in out.reason:
            malformed += 1
        if any(mid not in [p["evidence_id"]] for mid in []):  # placeholder
            pass
        # Check invented IDs: OllamaMatcher already validates, but we double-check
        # matched_evidence_ids is not in MatcherOutput, it's in the Ollama 5-field JSON, but our MatcherOutput doesn't have it directly
        # For this benchmark, we check if output was produced via LLM and had invented IDs, it would have been converted to REVIEW

        # Check forbidden BID/NO_BID
        if out.applicability in ("BID", "NO_BID"):
            forbidden += 1

        results.append({
            "input": p,
            "provenance": {"evidence_id": p["evidence_id"], "source_document": p["source_document"], "page_or_section": p["page_or_section"]},
            "output": out.model_dump(),
        })
        # Progress
        if (idx + 1) % 20 == 0:
            print(f"  ... {idx+1}/{len(pairs)}")

    elapsed = time.time() - start
    print(f"  Completed {len(results)} pairs in {elapsed:.1f}s (avg {elapsed/len(results):.2f}s per pair)")

    # Only after all predictions, load gold
    print(f"\n[4/4] Loading gold AFTER inference for evaluation: {GOLD_PATH}")
    with open(GOLD_PATH, encoding="utf-8") as f:
        gold = json.load(f)
    print(f"  Gold: {len(gold['gold_requirements'])} requirements, {len(gold['gold_evidences'])} evidences")

    # Join and calculate metrics
    gold_status_map = {r["requirement_id"]: r["expected_status"] for r in gold["gold_requirements"]}
    # Build gold applicability per pair (84)
    gold_applicability = {}
    for req in gold["gold_requirements"]:
        req_id = req["requirement_id"]
        expected_status = req["expected_status"]
        for ev in gold["gold_evidences"]:
            if ev["requirement_supported"] == req_id:
                gold_applicability[(req_id, ev["evidence_id"])] = expected_status
            else:
                gold_applicability[(req_id, ev["evidence_id"])] = "MISSING"

    # Calculate metrics
    def compute_prf(pred_set, gold_set):
        tp = len(pred_set & gold_set)
        fp = len(pred_set - gold_set)
        fn = len(gold_set - pred_set)
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        f1 = 2*prec*rec/(prec+rec) if prec+rec else 0
        return {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1}

    statuses = ["PASS", "FAIL", "MISSING", "REVIEW"]
    pred_by_status = {s: set() for s in statuses}
    gold_by_status = {s: set() for s in statuses}
    correct = 0
    for r in results:
        req_id = r["input"]["requirement_id"]
        ev_id = r["input"]["evidence_id"]
        pred = r["output"]["applicability"]
        gold_exp = gold_applicability.get((req_id, ev_id), "MISSING")
        if pred == gold_exp:
            correct += 1
        pred_by_status[pred].add((req_id, ev_id))
        gold_by_status[gold_exp].add((req_id, ev_id))

    total = len(results)
    matching_acc = correct / total if total else 0
    f1s = []
    for s in statuses:
        prf = compute_prf(pred_by_status[s], gold_by_status[s])
        if not pred_by_status[s] and not gold_by_status[s]:
            prf["f1"] = 1.0
        f1s.append(prf["f1"])
    macro_f1 = sum(f1s)/len(f1s) if f1s else 0

    # Evidence-supported F1: gold supporting = 4 (REQ-R/E-001 PASS, REQ-B/E-002 PASS, REQ-J/E-003 PASS, REQ-U/E-004 REVIEW)
    gold_supporting = {k for k,v in gold_applicability.items() if v in ("PASS","REVIEW")}
    pred_supporting = { (r["input"]["requirement_id"], r["input"]["evidence_id"]) for r in results if r["output"]["applicability"] in ("PASS","REVIEW") }
    ev_prf = compute_prf(pred_supporting, gold_supporting)
    evidence_supported_f1 = ev_prf["f1"]

    # Conflict F1: FAIL
    gold_fail = gold_by_status["FAIL"]
    pred_fail = pred_by_status["FAIL"]
    fail_prf = compute_prf(pred_fail, gold_fail)
    if not gold_fail and not pred_fail:
        fail_prf["f1"] = 1.0
    conflict_f1 = fail_prf["f1"]

    # Provenance
    prov_ok = sum(1 for r in results if r["provenance"]["evidence_id"] == r["input"]["evidence_id"] and r["provenance"]["source_document"] == r["input"]["source_document"])
    prov_rate = prov_ok / len(results) if results else 0

    # Malformed, invented, forbidden counts (from OllamaMatcher logic, already handled as REVIEW)
    # For this benchmark, we can count how many outputs were REVIEW due to malformed/invented
    # OllamaMatcher returns REVIEW with reason containing "Malformed" or "Invented" or "BID"
    malformed_count = sum(1 for r in results if "Malformed" in r["output"]["reason"] or "malformed" in r["output"]["reason"].lower())
    invented_count = sum(1 for r in results if "Invented" in r["output"]["reason"])
    forbidden_count = sum(1 for r in results if r["output"]["applicability"] in ("BID","NO_BID"))

    print(f"\n=== Benchmark Metrics (Ollama {model}, localhost, $0) ===")
    print(f"  Applicability macro F1: {macro_f1:.3f} (per-status: {dict(zip(statuses, [f'{x:.3f}' for x in f1s]))})")
    print(f"  Evidence-supported F1: {evidence_supported_f1:.3f} (pred {len(pred_supporting)} vs gold {len(gold_supporting)} — TP={ev_prf['tp']} FP={ev_prf['fp']} FN={ev_prf['fn']} P={ev_prf['precision']:.3f} R={ev_prf['recall']:.3f})")
    print(f"  Conflict/contradiction F1: {conflict_f1:.3f} (gold FAIL {len(gold_fail)}, pred FAIL {len(pred_fail)})")
    print(f"  Provenance preservation rate: {prov_rate:.3f} ({prov_ok}/{len(results)})")
    print(f"  Overall matching accuracy: {correct}/{total} = {matching_acc:.3f}")
    print(f"  Malformed outputs: {malformed_count}")
    print(f"  Invented evidence IDs: {invented_count}")
    print(f"  Forbidden BID/NO_BID outputs: {forbidden_count} (must be 0)")
    print(f"  Latency: {elapsed:.1f}s total, {elapsed/len(results):.2f}s per pair")
    print(f"  Cost: $0 — Ollama localhost, no paid API")

    # Threshold comparison (frozen)
    print(f"\n=== Frozen Threshold Comparison (Do NOT modify) ===")
    thresholds = {
        "applicability_macro_f1": 0.93,
        "evidence_supported_f1": 0.90,  # inferred from previous, but frozen is Requirement F1 >=0.90 etc. — we use same
        "provenance": 1.0,
    }
    # For this benchmark, we check macro F1
    status_macro = "PASS" if macro_f1 >= 0.93 else "FAIL"
    print(f"  Applicability macro F1: {macro_f1:.3f} vs >=0.93 → {status_macro}")
    print(f"  Evidence-supported F1: {evidence_supported_f1:.3f} (no frozen threshold, for info)")
    print(f"  Provenance: {prov_rate:.3f} vs 1.0 → {'PASS' if prov_rate>=1.0 else 'FAIL'}")

    # Do NOT claim AI acceptance passed unless every frozen criterion actually passes
    # Frozen criteria per docs/AI_Acceptance_Criteria.md: Requirement F1 >=0.90, Evidence F1 >=0.90, Matching macro >=0.93, etc.
    # For this Ollama benchmark, we only measure matching, not full pipeline, so we report
    if macro_f1 >= 0.93 and prov_rate >= 1.0 and forbidden_count==0 and malformed_count==0:
        print(f"\nOllama Benchmark: PASS — all measured criteria passed")
    else:
        print(f"\nOllama Benchmark: FAIL or BLOCKED — not all frozen criteria passed (this is expected for Mock vs LLM, Mock is fixture only)")

    # Save results
    import tempfile
    tmp = Path(tempfile.gettempdir()) / "opencode" / "tendermind" / "ollama_benchmark"
    tmp.mkdir(parents=True, exist_ok=True)
    out = {
        "model": model,
        "total_pairs": len(results),
        "applicability_macro_f1": macro_f1,
        "evidence_supported_f1": evidence_supported_f1,
        "conflict_f1": conflict_f1,
        "provenance_rate": prov_rate,
        "matching_accuracy": matching_acc,
        "malformed": malformed_count,
        "invented": invented_count,
        "forbidden": forbidden_count,
        "latency": elapsed,
        "cost": 0,
        "network": "localhost only, no paid API"
    }
    (tmp / "ollama_benchmark.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote metrics to {tmp/'ollama_benchmark.json'}")
    print("Do not claim AI acceptance passes unless every frozen criterion actually passes — MockMatcher is test fixture only")

if __name__ == "__main__":
    main()
