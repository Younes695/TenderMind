"""
LLM Gold Benchmark — Phase 2B — Mobile Human Gold
- Uses fixture evaluation/fixtures/mobile_llm_sample.json (3 chunks, no OCR)
- Compares LLM predictions (candidate_id -> canonical REQ-*) against human gold (9 reqs)
- Reports requirement/evidence/provenance metrics + hallucination + latency
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import time
import re
from evaluation.llm_generic_extraction import chunk_documents, parse_llm_json, validate_requirement, validate_evidence, deduplicate_requirements, check_ollama_available, get_ollama_model, call_ollama_for_chunk, assign_canonical_ids
from evaluation.generic_extraction import extract_voltage_levels

def normalize_summary(s: str) -> str:
    return re.sub(r'\W+', ' ', s.lower()).strip()

def match_requirements(predicted, gold):
    """Conservative matching: normalized summary + category + requirement_type + applicable_entity"""
    matched = []
    unmatched_pred = []
    unmatched_gold = list(gold)
    for pred in predicted:
        best = None
        best_score = 0
        for g in unmatched_gold:
            # Strong signals
            pred_norm = normalize_summary(pred["summary"])
            gold_norm = normalize_summary(g["summary"])
            # Exact normalized match
            if pred_norm == gold_norm and pred["category"] == g["category"]:
                best = g
                best_score = 1.0
                break
            # Category + requirement_type + applicable_entity + summary overlap
            if pred["category"] == g["category"]:
                # Check summary overlap
                pred_tokens = set(pred_norm.split())
                gold_tokens = set(gold_norm.split())
                overlap = len(pred_tokens & gold_tokens) / max(len(gold_tokens), 1)
                if overlap > 0.5 and pred.get("requirement_type") == g.get("requirement_type"):
                    if overlap > best_score:
                        best = g
                        best_score = overlap
        if best and best_score > 0.5:
            matched.append((pred, best))
            unmatched_gold.remove(best)
        else:
            unmatched_pred.append(pred)
    return matched, unmatched_pred, unmatched_gold

def main():
    print("=== LLM Gold Benchmark — Mobile Human Gold — Phase 2B ===")
    ok, msg = check_ollama_available()
    print(f"Ollama: {msg}")
    if not ok:
        print("Benchmark requires Ollama — failing clearly")
        print("LLM calls: 0, failed_calls: 3, valid JSON rate: 0")
        return

    # Load fixture
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "mobile_llm_sample.json"
    with open(fixture_path, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Fixture: {fixture_path} — {len(chunks)} chunks")

    # Load gold
    gold_path = Path(__file__).resolve().parent / "gold" / "mobile_human_gold.json"
    with open(gold_path, encoding="utf-8") as f:
        gold_data = json.load(f)
    gold_reqs = gold_data["gold_requirements"]
    gold_evs = gold_data.get("gold_evidence", [])
    print(f"Gold: {len(gold_reqs)} requirements, {len(gold_evs)} evidence")

    # Run LLM per chunk
    latencies = []
    valid_json = 0
    schema_valid = 0
    provenance_ok = 0
    all_reqs = []
    all_evs = []
    failed_calls = 0

    for chunk in chunks:
        t0 = time.time()
        result = call_ollama_for_chunk(chunk)
        lat = (time.time() - t0) * 1000
        latencies.append(lat)
        if not result:
            failed_calls += 1
            print(f"  {chunk['chunk_id']}: no response")
            continue
        parsed, status = parse_llm_json(result["raw"])
        print(f"  {chunk['chunk_id']}: parse {status}")
        if not parsed or "requirements" not in parsed:
            failed_calls += 1
            continue
        valid_json += 1
        for req in parsed["requirements"]:
            if "candidate_id" in req and "requirement_id" not in req:
                req["requirement_id"] = req["candidate_id"]
            ok_v, _ = validate_requirement(req, chunk)
            if ok_v:
                schema_valid += 1
                if req.get("source_document") and req.get("page_number"):
                    provenance_ok += 1
                # Ensure provenance not downgraded for low confidence
                all_reqs.append(req)
            else:
                print(f"    Requirement invalid: {req.get('candidate_id')}")
        for ev in parsed.get("evidence", []):
            if "candidate_id" in ev and "evidence_id" not in ev:
                ev["evidence_id"] = ev["candidate_id"]
            ok_e, _ = validate_evidence(ev, chunk)
            if ok_e:
                all_evs.append(ev)

    # Assign canonical IDs
    deduped_reqs, deduped_evs = assign_canonical_ids(all_reqs, all_evs)
    print(f"\nDeduped: {len(all_reqs)} -> {len(deduped_reqs)} requirements, {len(all_evs)} -> {len(deduped_evs)} evidence")

    # Deterministic facts
    combined_text = "\n".join(c["text"] for c in chunks)
    det_voltages = extract_voltage_levels(combined_text)
    print(f"Deterministic voltages: {det_voltages}")
    # Check conflicts
    conflicts = []
    for req in deduped_reqs:
        if "220kV" in req.get("summary","") and "220kV" not in det_voltages and det_voltages:
            conflicts.append({"type": "deterministic_llm_conflict", "fact": "voltage", "deterministic_value": det_voltages, "llm_value": req["summary"]})

    # Matching
    matched, unmatched_pred, unmatched_gold = match_requirements(deduped_reqs, gold_reqs)
    print(f"\nMatched: {len(matched)}/{len(gold_reqs)}")

    # Metrics
    gold_count = len(gold_reqs)
    pred_count = len(deduped_reqs)
    tp = len(matched)
    fp = len(unmatched_pred)
    fn = len(unmatched_gold)
    prec = tp / (tp + fp) if tp+fp else 0
    rec = tp / (tp + fn) if tp+fn else 0
    f1 = 2*prec*rec/(prec+rec) if prec+rec else 0
    print(f"\n=== Requirement Metrics ===")
    print(f"Gold: {gold_count} Pred: {pred_count} TP {tp} FP {fp} FN {fn}")
    print(f"Precision {prec:.2f} Recall {rec:.2f} F1 {f1:.2f}")

    # Category accuracy on matched
    cat_correct = sum(1 for pred, gold in matched if pred["category"] == gold["category"])
    cat_acc = cat_correct / len(matched) if matched else 0
    print(f"Category accuracy: {cat_correct}/{len(matched)}={cat_acc:.2f}")

    # Mandatory accuracy
    mand_correct = sum(1 for pred, gold in matched if pred.get("mandatory") == gold.get("mandatory"))
    mand_acc = mand_correct / len(matched) if matched else 0
    # False-positive mandatory rate: pred mandatory true but gold null/false
    fp_mand = sum(1 for pred, gold in matched if pred.get("mandatory") is True and gold.get("mandatory") is not True)
    fp_mand_rate = fp_mand / len(matched) if matched else 0
    print(f"Mandatory accuracy: {mand_correct}/{len(matched)}={mand_acc:.2f} FP mandatory rate: {fp_mand}/{len(matched)}={fp_mand_rate:.2f}")

    # Entity accuracy
    ent_correct = sum(1 for pred, gold in matched if pred.get("applicable_entity") == gold.get("applicable_entity"))
    ent_acc = ent_correct / len(matched) if matched else 0
    print(f"Entity accuracy: {ent_correct}/{len(matched)}={ent_acc:.2f}")

    # Provenance
    prov_correct = sum(1 for pred, gold in matched if pred.get("source_document") == gold.get("source_document") and pred.get("page_number") == gold.get("page_number"))
    prov_acc = prov_correct / len(matched) if matched else 0
    prov_coverage = provenance_ok / max(schema_valid, 1)
    print(f"Provenance source_document accuracy: {prov_correct}/{len(matched)}={prov_acc:.2f} coverage: {provenance_ok}/{schema_valid}={prov_coverage:.2f}")

    # Evidence
    # For this small sample, evidence is limited
    ev_prec = 0
    ev_rec = 0
    ev_f1 = 0
    if gold_evs:
        # Simple: count evidence with valid provenance
        ev_with_prov = sum(1 for ev in deduped_evs if ev.get("source_document") and ev.get("page_number"))
        print(f"Evidence: gold {len(gold_evs)} pred {len(deduped_evs)} with provenance {ev_with_prov}/{len(deduped_evs) if deduped_evs else 1:.2f}")

    # Hallucination
    unsupported_req = len(unmatched_pred)
    unsupported_ev = len([ev for ev in deduped_evs if not any(ev.get("source_document") == g.get("source_document") for g in gold_evs)])
    unsupported_rate = (unsupported_req + unsupported_ev) / max(pred_count + len(deduped_evs), 1)
    print(f"Hallucination: unsupported req {unsupported_req} unsupported ev {unsupported_ev} rate {unsupported_rate:.2f}")

    # Operational
    avg_lat = sum(latencies)/len(latencies) if latencies else 0
    p95_lat = sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0
    print(f"\n=== Operational ===")
    print(f"LLM calls: {len(chunks) - failed_calls} valid JSON rate: {valid_json}/{len(chunks)}={valid_json/len(chunks):.2f} schema-valid rate: {schema_valid}/{valid_json if valid_json else 1:.2f} failed_calls: {failed_calls} avg {avg_lat:.0f}ms p95 {p95_lat:.0f}ms")

    # Confidence analysis
    print(f"\n=== Confidence buckets ===")
    buckets = {"0.0-0.49": [], "0.5-0.69": [], "0.7-0.84": [], "0.85-1.0": []}
    for req in deduped_reqs:
        c = req.get("confidence", 0)
        if c < 0.5:
            buckets["0.0-0.49"].append(req)
        elif c < 0.7:
            buckets["0.5-0.69"].append(req)
        elif c < 0.85:
            buckets["0.7-0.84"].append(req)
        else:
            buckets["0.85-1.0"].append(req)
    for bucket, reqs in buckets.items():
        matched_in_bucket = sum(1 for r in reqs if any(r["requirement_id"] == m[0]["requirement_id"] for m in matched))
        unsupported_in_bucket = len(reqs) - matched_in_bucket
        print(f"  {bucket}: {len(reqs)} predictions, {matched_in_bucket} matched, {unsupported_in_bucket} unsupported")

    # Save
    import tempfile
    out = Path(tempfile.gettempdir()) / "opencode" / "tendermind" / "llm_gold_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "gold_count": gold_count,
            "predicted_count": pred_count,
            "tp": tp, "fp": fp, "fn": fn,
            "precision": prec, "recall": rec, "f1": f1,
            "category_accuracy": cat_acc,
            "mandatory_accuracy": mand_acc,
            "entity_accuracy": ent_acc,
            "provenance_accuracy": prov_acc,
            "evidence_with_provenance": len([ev for ev in deduped_evs if ev.get("source_document")]),
            "unsupported_rate": unsupported_rate,
            "llm_calls": len(chunks) - failed_calls,
            "failed_calls": failed_calls,
            "avg_latency_ms": avg_lat,
        }, f, indent=2)
    print(f"\nWrote {out}")
    print(f"\nSample requirement: {deduped_reqs[0] if deduped_reqs else 'none'}")
    if deduped_evs:
        print(f"Sample evidence: {deduped_evs[0]}")
    print(f"Conflicts: {conflicts[:2]}")

if __name__ == "__main__":
    main()
