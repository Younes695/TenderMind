"""
Benchmark Adapter — TenderMind — 84 Requirement-Evidence Pairs
- Can later run 21 requirements × 4 evidences = 84 pairs with any matcher provider
- DO NOT execute real benchmark now (per cost guardrail, no network inference)
- Gold remains evaluation-only, deterministic decision remains separate
- Inference inputs contain NO gold labels — gold loaded only AFTER matcher inference
"""
import json
from pathlib import Path
from typing import List, Dict, Any

BASE = Path(__file__).resolve().parents[1]
GOLD_PATH = BASE / "evaluation" / "sarai_gold_dataset.json"

def _load_gold_raw():
    with open(GOLD_PATH, encoding="utf-8") as f:
        return json.load(f)

# Build UNLABELED pairs for inference (no gold fields)
def build_unlabeled_pairs() -> List[Dict[str, Any]]:
    """
    Build 84 unlabeled requirement-evidence inputs for inference.
    - Loads gold to get requirement/evidence definitions, but DOES NOT include gold_expected_status or gold_evidence_supported in returned inputs
    - Returned dicts contain ONLY fields needed for MatcherInput (requirement + evidence + provenance)
    - Gold is NOT passed to matcher; it will be loaded after inference for evaluation
    """
    gold = _load_gold_raw()
    reqs = gold["gold_requirements"]
    evs = gold["gold_evidences"]
    pairs = []
    for req in reqs:
        for ev in evs:
            pairs.append({
                "requirement_id": req["requirement_id"],
                "requirement_text": req["requirement"],
                "requirement_category": req["category"],
                "requirement_type": req["requirement_type"],
                "mandatory": req["mandatory"],
                "applicable_entity": req.get("applicable_entity", "CONSORTIUM"),
                "evidence_id": ev["evidence_id"],
                "evidence_fact": ev["fact"],
                "evidence_type": ev["evidence_type"],
                "evidence_applicable_entity": ev.get("applicable_entity", "CONSORTIUM"),
                "evidence_valid_until": ev.get("valid_until"),
                "evidence_reusable": ev.get("reusable", True),
                "evidence_tender_source": ev.get("tender_source_id"),
                "current_tender_id": "SA-2018-HV2",
                "source_document": ev["source_document"],
                "page_or_section": ev["page_or_section"],
                # NO gold_expected_status, NO gold_evidence_supported here — per requirement
            })
    return pairs

# Legacy helper for backward compatibility (do not use for inference)
def build_pairs():
    """Deprecated: use build_unlabeled_pairs() for inference; this includes gold for backward compat but should not be used for matcher inputs"""
    gold = _load_gold_raw()
    reqs = gold["gold_requirements"]
    evs = gold["gold_evidences"]
    pairs = []
    for req in reqs:
        for ev in evs:
            pairs.append({
                "requirement_id": req["requirement_id"],
                "requirement_text": req["requirement"],
                "requirement_category": req["category"],
                "requirement_type": req["requirement_type"],
                "mandatory": req["mandatory"],
                "applicable_entity": req.get("applicable_entity", "CONSORTIUM"),
                "evidence_id": ev["evidence_id"],
                "evidence_fact": ev["fact"],
                "evidence_type": ev["evidence_type"],
                "evidence_applicable_entity": ev.get("applicable_entity", "CONSORTIUM"),
                "evidence_valid_until": ev.get("valid_until"),
                "evidence_reusable": ev.get("reusable", True),
                "evidence_tender_source": ev.get("tender_source_id"),
                "current_tender_id": "SA-2018-HV2",
                "source_document": ev["source_document"],
                "page_or_section": ev["page_or_section"],
                "gold_expected_status": req["expected_status"],
                "gold_evidence_supported": ev["requirement_supported"]
            })
    return pairs, gold

# Adapter to run a matcher over all pairs (offline, no network if using MockMatcher)
def run_benchmark(matcher, limit: int = None):
    """
    Run matcher over 84 pairs, collect outputs, do NOT decide BID/NO_BID here.
    Flow per requirement (gold loaded ONLY AFTER inference):
      1. Build UNLABELED inputs (no gold fields)
      2. Run matcher.safe_match on each input (no gold passed)
      3. Load gold AFTER inference for evaluation
      4. Join predictions with gold for evaluation (provenance retained alongside output)
    matcher: instance of BaseMatcher (e.g., MockMatcher for offline, OpenAIMatcher for paid)
    limit: for smoke, run only first N pairs
    Returns: list of results with input + output + gold for evaluation (gold not used during inference)
    """
    from app.matchers.base import MatcherInput
    # 1. Build UNLABELED inputs (no gold)
    unlabeled_pairs = build_unlabeled_pairs()
    if limit:
        unlabeled_pairs = unlabeled_pairs[:limit]
    # 2. Run matcher on unlabeled inputs (no gold)
    results = []
    for p in unlabeled_pairs:
        # Ensure input contains NO gold fields
        assert "gold_expected_status" not in p, "Inference input must not contain gold_expected_status"
        assert "gold_evidence_supported" not in p, "Inference input must not contain gold_evidence_supported"
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
        out = matcher.safe_match(inp)
        # Preserve provenance explicitly alongside output (MatcherOutput itself does not contain provenance)
        provenance = {
            "evidence_id": p["evidence_id"],
            "source_document": p["source_document"],
            "page_or_section": p["page_or_section"]
        }
        results.append({
            "input": p,  # Unlabeled input (no gold)
            "provenance": provenance,  # Explicitly retained alongside output
            "output": out.model_dump(),
        })
    # 3. Load gold AFTER inference for evaluation
    gold = _load_gold_raw()
    gold_status_map = {r["requirement_id"]: r["expected_status"] for r in gold["gold_requirements"]}
    gold_supported_map = {e["evidence_id"]: e["requirement_supported"] for e in gold["gold_evidences"]}
    # 4. Join predictions with gold for evaluation (not used during inference)
    for r in results:
        req_id = r["input"]["requirement_id"]
        ev_id = r["input"]["evidence_id"]
        r["gold_expected"] = gold_status_map.get(req_id, "UNKNOWN")
        r["gold_evidence_supported"] = gold_supported_map.get(ev_id, "UNKNOWN")
        # Also retain provenance in result wrapper (explicit)
        # Already in r["provenance"] and r["input"]["source_document"] etc.
    return results

# For future real LLM run, example (DO NOT RUN NOW per cost guardrail):
# from app.matchers import OpenAIMatcher
# matcher = OpenAIMatcher(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4o")
# results = run_benchmark(matcher)  # Would incur 84 LLM calls × $0.0005 ≈ $0.04
# Then evaluate matching_macro_f1 vs gold, but decision still via deterministic engine

if __name__ == "__main__":
    # Offline smoke: run with MockMatcher for 5 pairs only, no network
    from app.matchers import MockMatcher
    matcher = MockMatcher()
    results = run_benchmark(matcher, limit=5)
    print(f"Benchmark adapter smoke: {len(results)} pairs with {matcher.name} v{matcher.version} (no gold during inference, gold joined after)")
    for r in results:
        print(f"  {r['input']['requirement_id']} vs {r['input']['evidence_id']} -> {r['output']['applicability']} (support={r['output']['support']}) provenance={r['provenance']['source_document']}:{r['provenance']['page_or_section']}")
    print("Adapter ready for 84 pairs — to run full 84 with real LLM, set TENDERMIND_MATCHER_PROVIDER=openai and TENDERMIND_ENABLE_LLM=1 and use OpenAIMatcher (see docs)")
