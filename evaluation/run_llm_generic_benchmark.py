"""
LLM Generic Benchmark — TenderMind — Phase 2A Experiment
- Requires Ollama explicitly (local qwen2.5:3b)
- Small controlled sample (Mobile tender, 1-2 chunks)
- Reports: latency, valid JSON rate, schema-valid rate, provenance coverage, requirements/evidence counts, deterministic vs LLM conflicts
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time
import json
from evaluation.llm_generic_extraction import chunk_documents, parse_llm_json, validate_requirement, deduplicate_requirements, check_ollama_available, get_ollama_model
from evaluation.generic_extraction import ingest_tender

def main():
    print("=== LLM Generic Benchmark — Phase 2A ===")
    ok, msg = check_ollama_available()
    print(f"Ollama: {msg}")
    if not ok:
        print("Benchmark requires Ollama qwen2.5:3b — run: ollama pull qwen2.5:3b && ollama serve")
        print("Skipping benchmark (deterministic fallback remains)")
        return

    # Controlled fixture — 2-4 chunks from Mobile, no OCR, no ingestion
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "mobile_llm_sample.json"
    if not fixture_path.exists():
        print(f"Fixture not found: {fixture_path}")
        return
    with open(fixture_path, encoding="utf-8") as f:
        chunks = json.load(f)
    print(f"Fixture: {fixture_path} — {len(chunks)} chunks (no OCR)")
    for c in chunks:
        print(f"  {c['chunk_id']} {c['source_document']} p{c['page_number']} len={len(c['text'])}")
    # Use fixture directly — no ingestion/OCR
    sample_chunks = chunks  # All 3 chunks from fixture
    # For deterministic comparison, still need doc_results for deterministic extraction — create minimal mock
    doc_results = {c["source_document"]: {"pages": [{"page_number": c["page_number"], "text": c["text"]}]} for c in chunks}
    from evaluation.llm_generic_extraction import call_ollama_for_chunk

    latencies = []
    valid_json = 0
    schema_valid = 0
    provenance_ok = 0
    all_reqs = []
    all_evs = []
    failed_calls = 0
    duplicate_candidates = 0

    for chunk in sample_chunks:
        t0 = time.time()
        result = call_ollama_for_chunk(chunk)
        lat = time.time() - t0
        latencies.append(lat * 1000)  # ms
        if not result:
            failed_calls += 1
            print(f"  {chunk['chunk_id']}: no response")
            continue
        parsed, status = parse_llm_json(result["raw"])
        print(f"  {chunk['chunk_id']}: parse {status} len={len(result['raw'])}")
        if parsed and "requirements" in parsed:
            valid_json += 1
            for req in parsed["requirements"]:
                # Handle candidate_id vs requirement_id
                if "candidate_id" in req and "requirement_id" not in req:
                    req["requirement_id"] = req.pop("candidate_id")
                # Check schema via validate_requirement
                ok_v, msg_v = validate_requirement(req, chunk)
                if ok_v:
                    schema_valid += 1
                    if req.get("source_document") and req.get("page_number"):
                        provenance_ok += 1
                    all_reqs.append(req)
                else:
                    print(f"    Requirement invalid: {msg_v} {req.get('requirement_id')}")
                    # Count as failed validation, not provenance
            # Evidence
            for ev in parsed.get("evidence", []):
                if "candidate_id" in ev and "evidence_id" not in ev:
                    ev["evidence_id"] = ev.pop("candidate_id")
                # Validate evidence
                from evaluation.llm_generic_extraction import validate_evidence
                ok_e, msg_e = validate_evidence(ev, chunk)
                if ok_e:
                    all_evs.append(ev)
                else:
                    print(f"    Evidence invalid: {msg_e} {ev.get('evidence_id')}")
        else:
            failed_calls += 1
            print(f"    Invalid JSON: {status}")

    # Deduplication
    from evaluation.llm_generic_extraction import deduplicate_requirements
    before_dedup = len(all_reqs)
    deduped = deduplicate_requirements(all_reqs)
    merged = before_dedup - len(deduped)
    duplicate_candidates = before_dedup - len(deduped)
    print(f"\nDeduped: {before_dedup} -> {len(deduped)} (merged {merged})")

    # Deterministic vs LLM conflicts
    from evaluation.generic_extraction import extract_requirements_generic
    det_reqs = extract_requirements_generic(doc_results, "BENCHMARK-001")
    print(f"Deterministic reqs: {len(det_reqs)}")
    print(f"LLM reqs (deduped): {len(deduped)}")
    # Deterministic facts vs LLM
    from evaluation.generic_extraction import extract_voltage_levels, extract_mva_values
    # Build combined text for deterministic facts
    combined = "\n".join(c["text"] for c in sample_chunks)
    det_voltages = extract_voltage_levels(combined)
    # Check LLM requirements for voltage mention
    llm_voltages = []
    for req in deduped:
        if "voltage" in req.get("summary","").lower() or "220kV" in req.get("summary",""):
            llm_voltages.append(req["summary"])
    conflicts = []
    # Simple conflict: check if deterministic voltage not in LLM
    for det in det_reqs:
        for llm in deduped:
            if det["category"] == llm["category"] and det["mandatory"] != llm["mandatory"]:
                conflicts.append({"type": "deterministic_llm_conflict", "category": det["category"], "deterministic_mandatory": det["mandatory"], "llm_mandatory": llm["mandatory"]})
                break
    # Also check deterministic voltage vs LLM
    if det_voltages and not any("220kV" in r.get("summary","") or "voltage" in r.get("summary","").lower() for r in deduped):
        conflicts.append({"type": "deterministic_llm_conflict", "fact": "voltage", "deterministic_value": det_voltages, "llm_value": None})

    print(f"Deterministic vs LLM conflicts: {len(conflicts)}")
    for c in conflicts[:3]:
        print(f"  {c}")

    # Report
    import statistics
    avg_lat = sum(latencies)/len(latencies) if latencies else 0
    p95_lat = sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0
    print(f"\n=== Benchmark Report ===")
    print(f"Chunks processed: {len(sample_chunks)}")
    print(f"LLM calls: {len(sample_chunks) - failed_calls}")
    print(f"Valid JSON rate: {valid_json}/{len(sample_chunks)}={valid_json/len(sample_chunks) if sample_chunks else 0:.2f}")
    print(f"Schema-valid rate: {schema_valid}/{valid_json if valid_json else 1:.2f}")
    print(f"Provenance coverage: {provenance_ok}/{schema_valid if schema_valid else 1:.2f}")
    print(f"Requirements extracted: {len(deduped)}")
    print(f"Evidence items extracted: {len(all_evs)}")
    print(f"Evidence with valid provenance: {sum(1 for ev in all_evs if ev.get('source_document') and ev.get('page_number'))}/{len(all_evs) if all_evs else 1:.2f}")
    print(f"Duplicate candidates: {duplicate_candidates}")
    print(f"Merged requirements: {merged}")
    print(f"Deterministic vs LLM conflicts: {len(conflicts)}")
    print(f"Average latency ms: {avg_lat:.0f}")
    print(f"P95 latency ms: {p95_lat:.0f}")
    print(f"Failed calls: {failed_calls}")

    # Save
    import tempfile
    out = Path(tempfile.gettempdir()) / "opencode" / "tendermind" / "llm_benchmark.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "chunks_processed": len(sample_chunks),
            "llm_calls": len(sample_chunks) - failed_calls,
            "valid_json_rate": valid_json/len(sample_chunks) if sample_chunks else 0,
            "schema_valid_rate": schema_valid/max(valid_json,1),
            "provenance_coverage": provenance_ok/max(schema_valid,1),
            "requirements_extracted": len(deduped),
            "evidence_items_extracted": len(all_evs),
            "evidence_with_valid_provenance": sum(1 for ev in all_evs if ev.get("source_document") and ev.get("page_number")),
            "duplicate_candidates": duplicate_candidates,
            "merged_requirements": merged,
            "deterministic_llm_conflicts": len(conflicts),
            "average_latency_ms": avg_lat,
            "p95_latency_ms": p95_lat,
            "failed_calls": failed_calls,
        }, f, indent=2)
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
