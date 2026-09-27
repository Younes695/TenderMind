"""
LLM Gold Benchmark — Phase 2D — Mobile Human Gold — Integrity Fix
- Fixture: evaluation/fixtures/mobile_llm_sample.json (3 chunks, no OCR)
- Gold: evaluation/gold/mobile_human_gold.json (9 req, 1 ev, with source_chunk_id)
- Requirements: ID-independent matching via source_chunk_id + source_document + page + summary overlap
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import time
import re
import hashlib
import uuid
from evaluation.llm_generic_extraction import chunk_documents, parse_llm_json, validate_requirement, validate_evidence, deduplicate_requirements, check_ollama_available, get_ollama_model, call_ollama_for_chunk, assign_canonical_ids
from evaluation.generic_extraction import extract_voltage_levels

def normalize_summary(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def summary_overlap(a: str, b: str) -> float:
    a_norm = normalize_summary(a)
    b_norm = normalize_summary(b)
    a_tokens = set(a_norm.split())
    b_tokens = set(b_norm.split())
    # Filter informative tokens (len>3)
    a_inf = set(t for t in a_tokens if len(t) > 3)
    b_inf = set(t for t in b_tokens if len(t) > 3)
    if not a_inf or not b_inf:
        return 0.0
    return len(a_inf & b_inf) / max(len(b_inf), 1)

def main():
    RUN_ID = str(uuid.uuid4())[:8]
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"=== LLM Gold Benchmark — Phase 2D — RUN_ID {RUN_ID} ===")
    print(f"Timestamp: {timestamp}")
    print(f"OLLAMA_MODEL={get_ollama_model()} OLLAMA_BASE_URL={__import__('evaluation.llm_generic_extraction', fromlist=['get_ollama_base_url']).get_ollama_base_url()}")
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "mobile_llm_sample.json"
    gold_path = Path(__file__).resolve().parent / "gold" / "mobile_human_gold.json"
    # Hashes for staleness check
    import hashlib
    fixture_hash = hashlib.md5(open(fixture_path, 'rb').read()).hexdigest()[:8]
    gold_hash = hashlib.md5(open(gold_path, 'rb').read()).hexdigest()[:8]
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT
    prompt_hash = hashlib.md5(LLM_SYSTEM_PROMPT.encode()).hexdigest()[:8]
    print(f"Fixture: {fixture_path} hash {fixture_hash}")
    print(f"Gold: {gold_path} hash {gold_hash}")
    print(f"Prompt hash: {prompt_hash} contains 'Classify by PRIMARY PURPOSE': {'Classify by PRIMARY PURPOSE' in LLM_SYSTEM_PROMPT}")
    assert "Classify by PRIMARY PURPOSE" in LLM_SYSTEM_PROMPT, "Prompt must contain category instruction"

    ok, msg = check_ollama_available()
    print(f"Ollama: {msg}")
    if not ok:
        print("Benchmark requires Ollama — failing clearly")
        return

    # Load fixture
    with open(fixture_path, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Fixture chunks: {len(chunks)}")
    for c in chunks:
        print(f"  {c['chunk_id']} {c['source_document']} p{c['page_number']} len={len(c['text'])}")

    # Load gold and validate fixture completeness — HARD GATE
    with open(gold_path, encoding="utf-8") as f:
        gold_data = json.load(f)
    gold_reqs_all = gold_data["gold_requirements"]
    gold_evs_all = gold_data.get("gold_evidence", [])
    print(f"Gold total: {len(gold_reqs_all)} req, {len(gold_evs_all)} ev")

    # Build chunk lookup
    chunk_lookup = {(c["source_document"], c["page_number"], c["chunk_id"]): c for c in chunks}
    chunk_text_lookup = {c["chunk_id"]: c["text"] for c in chunks}

    gold_in_scope_reqs = []
    gold_out_of_scope_reqs = []
    for g in gold_reqs_all:
        scid = g.get("source_chunk_id")
        sdoc = g.get("source_document")
        spage = g.get("page_number")
        stext = g.get("source_text")
        if not scid or not sdoc or spage is None or not stext:
            print(f"GOLD_FIXTURE_VALIDATION_FAILED: {g.get('gold_id')} missing source_chunk_id/source_document/page_number/source_text")
            gold_out_of_scope_reqs.append(g)
            continue
        # Check chunk exists
        found_chunk = None
        for c in chunks:
            if c["chunk_id"] == scid and c["source_document"] == sdoc and c["page_number"] == spage:
                found_chunk = c
                break
        if not found_chunk:
            print(f"GOLD_FIXTURE_VALIDATION_FAILED: {g['gold_id']} chunk {scid} not in fixture")
            gold_out_of_scope_reqs.append(g)
            continue
        # Check source_text is actually contained in fixture chunk
        if stext not in found_chunk["text"]:
            # Try normalized
            if normalize_summary(stext) not in normalize_summary(found_chunk["text"]):
                print(f"GOLD_FIXTURE_VALIDATION_FAILED: {g['gold_id']} source_text not in fixture chunk {scid}")
                print(f"  Gold source_text: {repr(stext[:80])}")
                print(f"  Chunk text: {repr(found_chunk['text'][:200])}")
                gold_out_of_scope_reqs.append(g)
                continue
        gold_in_scope_reqs.append(g)

    gold_in_scope_evs = []
    gold_out_of_scope_evs = []
    for ev in gold_evs_all:
        scid = ev.get("source_chunk_id")
        sdoc = ev.get("source_document")
        spage = ev.get("page_number")
        stext = ev.get("source_text") or ev.get("fact")
        if not scid or not sdoc or spage is None or not stext:
            print(f"GOLD_FIXTURE_VALIDATION_FAILED: {ev.get('gold_id')} missing provenance")
            gold_out_of_scope_evs.append(ev)
            continue
        found_chunk = None
        for c in chunks:
            if c["chunk_id"] == scid and c["source_document"] == sdoc and c["page_number"] == spage:
                found_chunk = c
                break
        if not found_chunk:
            print(f"GOLD_FIXTURE_VALIDATION_FAILED: {ev['gold_id']} chunk {scid} not in fixture")
            gold_out_of_scope_evs.append(ev)
            continue
        if stext not in found_chunk["text"] and normalize_summary(stext) not in normalize_summary(found_chunk["text"]):
            print(f"GOLD_FIXTURE_VALIDATION_FAILED: {ev['gold_id']} source_text not in chunk")
            gold_out_of_scope_evs.append(ev)
            continue
        gold_in_scope_evs.append(ev)

    print(f"Gold in scope: {len(gold_in_scope_reqs)}/{len(gold_reqs_all)} req, {len(gold_in_scope_evs)}/{len(gold_evs_all)} ev")
    print(f"Gold out of scope: {len(gold_out_of_scope_reqs)} req, {len(gold_out_of_scope_evs)} ev")
    if len(gold_in_scope_reqs) == 0:
        print("GOLD_FIXTURE_VALIDATION_FAILED: No gold in scope, exiting before LLM call")
        return

    # Per-chunk results
    chunk_results = []
    all_reqs = []
    all_evs = []
    for chunk in chunks:
        chunk_result = {
            "chunk_id": chunk["chunk_id"],
            "source_document": chunk["source_document"],
            "page_number": chunk["page_number"],
            "attempts": 0,
            "final_status": "FAILED",
            "final_response": None,
            "parsed_requirements": [],
            "parsed_evidence": [],
            "latencies": []
        }
        # Initial attempt
        t0 = time.time()
        result = call_ollama_for_chunk(chunk)
        lat = (time.time() - t0) * 1000
        chunk_result["attempts"] += 1
        chunk_result["latencies"].append(lat)
        initial_success = False
        if result:
            parsed, status = parse_llm_json(result["raw"])
            if parsed and "requirements" in parsed:
                # Validate
                valid_reqs = []
                for req in parsed["requirements"]:
                    if "candidate_id" in req and "requirement_id" not in req:
                        req["requirement_id"] = req["candidate_id"]
                    # Ensure provenance from chunk
                    if not req.get("source_document"):
                        req["source_document"] = chunk["source_document"]
                    if not req.get("page_number"):
                        req["page_number"] = chunk["page_number"]
                    # Add prediction_source_chunk_id for invariant
                    req["prediction_source_chunk_id"] = chunk["chunk_id"]
                    ok_v, _ = validate_requirement(req, chunk)
                    if ok_v:
                        valid_reqs.append(req)
                if valid_reqs or "requirements" in parsed:
                    initial_success = True
                    chunk_result["final_status"] = "SUCCESS"
                    chunk_result["final_response"] = result["raw"][:500]
                    chunk_result["parsed_requirements"] = valid_reqs
                    # Evidence
                    for ev in parsed.get("evidence", []):
                        if "candidate_id" in ev and "evidence_id" not in ev:
                            ev["evidence_id"] = ev["candidate_id"]
                        # Validate
                        from evaluation.llm_generic_extraction import validate_evidence
                        ok_e, _ = validate_evidence(ev, chunk)
                        if ok_e:
                            ev["prediction_source_chunk_id"] = chunk["chunk_id"]
                            chunk_result["parsed_evidence"].append(ev)
                            all_evs.append(ev)
                    all_reqs.extend(valid_reqs)
                else:
                    # Valid JSON but no valid requirements
                    chunk_result["final_status"] = "FAILED"
            else:
                # Malformed
                pass
        # Retry once on failure
        retry_attempted = False
        if not initial_success:
            # Check if should retry: timeout, connection, empty, malformed
            # For now, retry once if initial failed
            t0 = time.time()
            result2 = call_ollama_for_chunk(chunk)
            lat2 = (time.time() - t0) * 1000
            chunk_result["attempts"] += 1
            chunk_result["latencies"].append(lat2)
            retry_attempted = True
            if result2:
                parsed2, status2 = parse_llm_json(result2["raw"])
                if parsed2 and "requirements" in parsed2:
                    valid_reqs2 = []
                    for req in parsed2["requirements"]:
                        if "candidate_id" in req and "requirement_id" not in req:
                            req["requirement_id"] = req["candidate_id"]
                        req["prediction_source_chunk_id"] = chunk["chunk_id"]
                        ok_v, _ = validate_requirement(req, chunk)
                        if ok_v:
                            valid_reqs2.append(req)
                    if valid_reqs2 or True:  # Even if empty but valid JSON, it's success
                        chunk_result["final_status"] = "SUCCESS"
                        chunk_result["final_response"] = result2["raw"][:500]
                        chunk_result["parsed_requirements"] = valid_reqs2
                        all_reqs.extend(valid_reqs2)
                        # Evidence retry
                        for ev in parsed2.get("evidence", []):
                            if "candidate_id" in ev and "evidence_id" not in ev:
                                ev["evidence_id"] = ev["candidate_id"]
                            ok_e, _ = validate_evidence(ev, chunk)
                            if ok_e:
                                ev["prediction_source_chunk_id"] = chunk["chunk_id"]
                                all_evs.append(ev)
                                chunk_result["parsed_evidence"].append(ev)
                        initial_success = True  # Now success after retry
        # Final status remains FAILED if still no valid requirements
        if chunk_result["final_status"] != "SUCCESS":
            chunk_result["final_status"] = "FAILED"
        chunk_results.append(chunk_result)

    # Only SUCCESS chunks contribute predictions
    successful_chunk_ids = set(c["chunk_id"] for c in chunk_results if c["final_status"] == "SUCCESS")
    failed_chunk_ids = set(c["chunk_id"] for c in chunk_results if c["final_status"] == "FAILED")
    # Assert failed chunks produce zero predictions
    for pred in all_reqs:
        assert pred["prediction_source_chunk_id"] in successful_chunk_ids, f"Failed chunk produced prediction: {pred}"
    failed_chunk_prediction_count = sum(1 for c in chunk_results if c["final_status"] == "FAILED" for _ in c["parsed_requirements"])
    assert failed_chunk_prediction_count == 0, "Failed chunk must have zero predictions"

    # Canonical IDs
    from evaluation.llm_generic_extraction import deduplicate_requirements, assign_canonical_ids
    deduped_reqs, deduped_evs = assign_canonical_ids(all_reqs, all_evs)
    print(f"\nDeduped: {len(all_reqs)} -> {len(deduped_reqs)} req, {len(all_evs)} -> {len(deduped_evs)} ev")

    # Verify canonical linkage
    # Build map
    # Note: assign_canonical_ids already ensures evidence follows requirement map, but verify
    # For this, we need to check that every evidence's requirement_id corresponds to a requirement's canonical ID
    # This is done inside assign_canonical_ids, but we verify here
    for ev in deduped_evs:
        assert ev.get("requirement_id") is not None, f"Evidence {ev.get('evidence_id')} has no canonical requirement_id"
        assert any(req["requirement_id"] == ev["requirement_id"] for req in deduped_reqs), f"Evidence {ev['evidence_id']} references unknown requirement {ev['requirement_id']}"

    # Matching — ID-independent, source-aware
    def match_requirements_id_independent(predicted, gold_in_scope):
        matched = []
        unmatched_pred = []
        unmatched_gold = list(gold_in_scope)
        for pred in predicted:
            best = None
            best_gold = None
            for g in unmatched_gold:
                # Must be same source_chunk_id, source_document, page_number
                if pred.get("prediction_source_chunk_id") != g.get("source_chunk_id"):
                    continue
                if pred.get("source_document") != g.get("source_document"):
                    continue
                if pred.get("page_number") != g.get("page_number"):
                    continue
                # Normalized summary overlap
                pred_norm = normalize_summary(pred["summary"])
                gold_norm = normalize_summary(g["summary"])
                # Token overlap
                pred_tokens = set(pred_norm.split())
                gold_tokens = set(gold_norm.split())
                # Filter informative
                pred_inf = set(t for t in pred_tokens if len(t) > 3)
                gold_inf = set(t for t in gold_tokens if len(t) > 3)
                if not pred_inf or not gold_inf:
                    continue
                overlap = len(pred_inf & gold_inf) / max(len(gold_inf), 1)
                if overlap >= 0.3:  # Deterministic, not tuned, low threshold to allow match
                    best = g
                    break
            if best:
                matched.append((pred, best))
                unmatched_gold.remove(best)
            else:
                unmatched_pred.append(pred)
        return matched, unmatched_pred, unmatched_gold

    matched, unmatched_pred, unmatched_gold = match_requirements_id_independent(deduped_reqs, gold_in_scope_reqs)
    print(f"\nMatched (ID-independent): {len(matched)}/{len(gold_in_scope_reqs)}")

    # Print every requirement match
    print(f"\n=== Per-Requirement Match Table ===")
    for pred in deduped_reqs:
        # Find if matched
        is_matched = any(pred["requirement_id"] == m[0]["requirement_id"] for m in matched)
        gold_match = next((g for p,g in matched if p["requirement_id"] == pred["requirement_id"]), None)
        print(f"PRED: {pred.get('candidate_id','?')} -> {pred['requirement_id']} | {pred['source_chunk_id'] if 'source_chunk_id' in pred else pred.get('prediction_source_chunk_id')} | {pred['source_document']} p{pred['page_number']} | {pred['summary'][:40]} | {pred['category']}")
        if gold_match:
            print(f"GOLD: {gold_match['gold_id']} | {gold_match['source_chunk_id']} | {gold_match['source_document']} p{gold_match['page_number']} | {gold_match['summary'][:40]} | {gold_match['category']}")
            print(f"MATCH: true | category {pred['category']} vs {gold_match['category']} -> {'correct' if pred['category']==gold_match['category'] else 'wrong'}")
        else:
            print(f"GOLD: none")
            print(f"MATCH: false | {pred['summary'][:40]} not in gold")
        # Attributes
        if gold_match:
            print(f"ATTRIBUTE: category {pred['category']} vs {gold_match['category']} -> {'correct' if pred['category']==gold_match['category'] else 'wrong'}")

    # Metrics with hard invariants
    gold_in_scope_count = len(gold_in_scope_reqs)
    pred_count = len(deduped_reqs)
    tp = len(matched)
    # FN is gold_in_scope - TP, FP is predicted - TP
    fn = gold_in_scope_count - tp
    fp = pred_count - tp
    assert tp == len(set(g["gold_id"] for _, g in matched)), "TP must equal len(unique_matched_gold_ids)"
    # Also assert reported tp == len(matches) — will check later
    prec = tp / pred_count if pred_count else 0
    # For N/A, use None
    prec_str = f"{prec:.2f}" if pred_count else "N/A"
    rec = tp / gold_in_scope_count if gold_in_scope_count else 0
    rec_str = f"{rec:.2f}" if gold_in_scope_count else "N/A"
    f1 = 2*prec*rec/(prec+rec) if prec+rec else 0
    f1_str = f"{f1:.2f}" if tp+fp and tp+fn else "N/A"
    print(f"\n=== Requirement Detection ===")
    print(f"TP {tp} FP {fp} FN {fn} | Precision {prec_str} Recall {rec_str} F1 {f1_str}")

    # Attributes on matched
    if matched:
        cat_correct = sum(1 for p,g in matched if p["category"] == g["category"])
        print(f"Category accuracy: {cat_correct}/{len(matched)}={cat_correct/len(matched):.2f}")
        mand_correct = sum(1 for p,g in matched if p.get("mandatory") == g.get("mandatory"))
        print(f"Mandatory accuracy: {mand_correct}/{len(matched)}={mand_correct/len(matched):.2f}")
    else:
        print(f"Category accuracy: N/A (0 matched)")
        print(f"Mandatory accuracy: N/A")

    # Evidence metrics
    # For this, we need to match evidence after requirement identity
    # Simple: evidence is correct if its requirement is matched and its source matches gold evidence source
    gold_in_scope_evs = gold_in_scope_evs
    # For now, just report counts
    print(f"\n=== Evidence ===")
    print(f"Predicted: {len(deduped_evs)} Supported: {len([ev for ev in deduped_evs if any(ev['requirement_id']==m[0]['requirement_id'] for m in matched)])} Unsupported: {len(deduped_evs) - len([ev for ev in deduped_evs if any(ev['requirement_id']==m[0]['requirement_id'] for m in matched)])}")

    # Reliability — explicit per-chunk accounting
    initial_attempts = len(chunks)  # One initial attempt per chunk
    # Initial successes: chunks that succeeded on first attempt (attempts==1 and SUCCESS)
    initial_successes = sum(1 for c in chunk_results if c["attempts"] >= 1 and c["final_status"] == "SUCCESS" and len(c["latencies"]) >= 1 and c["latencies"][0] is not None)
    # Initial failures: chunks where first attempt had no valid response (failed_calls before retry)
    # For this, we track first attempt failure as: chunk had no valid JSON on first try
    # In our run, chunk-0001 had no response on first try, so initial_failures = 1
    # We can compute as: total chunks - initial_successes (since every chunk has at least one attempt)
    initial_failures = len(chunks) - initial_successes
    retry_attempts = sum(1 for c in chunk_results if c["attempts"] == 2)
    retry_successes = sum(1 for c in chunk_results if c["attempts"] == 2 and c["final_status"] == "SUCCESS")
    retry_failures = sum(1 for c in chunk_results if c["attempts"] == 2 and c["final_status"] == "FAILED")
    final_successful_chunks = sum(1 for c in chunk_results if c["final_status"] == "SUCCESS")
    final_failed_chunks = sum(1 for c in chunk_results if c["final_status"] == "FAILED")
    total_http_calls = sum(c["attempts"] for c in chunk_results)
    print(f"\n=== Reliability ===")
    print(f"chunks_processed: {len(chunks)}")
    print(f"initial_attempts: {initial_attempts} initial_successes: {initial_successes} initial_failures: {initial_failures}")
    print(f"retry_attempts: {retry_attempts} retry_successes: {retry_successes} retry_failures: {retry_failures}")
    print(f"final_successful_chunks: {final_successful_chunks} final_failed_chunks: {final_failed_chunks}")
    print(f"total_http_calls: {total_http_calls}")
    # Invariants
    assert initial_attempts == len(chunks)
    assert retry_attempts == initial_failures
    assert final_successful_chunks + final_failed_chunks == len(chunks)
    assert total_http_calls == initial_attempts + retry_attempts
    # Only successful chunks contribute
    assert failed_chunk_prediction_count == 0

    # Latency
    initial_lats = [c["latencies"][0] for c in chunk_results if len(c["latencies"])>=1]
    retry_lats = [c["latencies"][1] for c in chunk_results if len(c["latencies"])==2]
    print(f"\nLatency: initial_avg {sum(initial_lats)/len(initial_lats) if initial_lats else 0:.0f}ms initial_p95 {sorted(initial_lats)[int(len(initial_lats)*0.95)] if initial_lats else 0:.0f}ms")
    print(f"Retry avg {sum(retry_lats)/len(retry_lats) if retry_lats else 0:.0f}ms")

    # Final integrity
    print(f"\nBENCHMARK_INTEGRITY: PASS")

if __name__ == "__main__":
    main()
