"""
Stage 3D — Larger-sample (12-15 chunks) LLM behavior confirmation + tiny-input guard.
Same fixture, same Variant B, same evidence fix. No prompt tuning.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding='utf-8', errors='ignore')

import json
import time
import tempfile
import shutil
from pathlib import Path
import fitz

MOBILE_ROOT = Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations")
GOLD_PATH = Path(__file__).resolve().parents[1] / "gold" / "mobile_representative_gold.json"

SUBSET_FILES = [
    MOBILE_ROOT / "Commercial forms.txt",
    MOBILE_ROOT / "Price schedules of 6th October northern Extention 22-22-22 KV GIS SS.xlsx",
    MOBILE_ROOT / "Drawings.pdf",
    MOBILE_ROOT / "Tender Price Schedule- التوسعات الشمالية.pdf",
]


def build_subset_tender(tmp_root: Path, tender_id: str) -> Path:
    tender_dir = tmp_root / tender_id
    tender_dir.mkdir(parents=True, exist_ok=True)
    for p in SUBSET_FILES:
        if p.exists():
            shutil.copy2(str(p), str(tender_dir / p.name))
    vol1 = MOBILE_ROOT / "Vol I - Tender Document.pdf"
    if vol1.exists():
        doc = fitz.open(str(vol1))
        new = fitz.open()
        for i in range(min(20, len(doc))):
            new.insert_pdf(doc, from_page=i, to_page=i)
        new.save(str(tender_dir / "Vol I subset 20pages.pdf"))
        new.close()
        doc.close()
    return tender_dir


def main():
    from evaluation.generic_extraction import build_generic_extraction, ingest_tender
    from evaluation.llm_generic_extraction import (
        chunk_documents, get_ollama_model, get_ollama_base_url, check_ollama_available,
        call_ollama_for_chunk, parse_llm_json, validate_requirement, validate_evidence,
        deduplicate_requirements, assign_canonical_ids,
    )
    from evaluation.stage3c.representative_selector import select_representative_chunks
    from evaluation.stage3d.tiny_guard import tiny_guard_status, SKIPPED_TINY_INPUT

    tmp_root = Path(tempfile.mkdtemp(prefix="stage3d_"))
    tender_id = "Mobile-Stage3D-001"
    tender_path = build_subset_tender(tmp_root, tender_id)
    print(f"Tender: {tender_path}")

    gold = json.loads(GOLD_PATH.read_text(encoding='utf-8'))
    print(f"Gold: {len(gold['gold_requirements'])} reqs (not modified)")

    t0 = time.time()
    det = build_generic_extraction(tender_path, tender_id=tender_id, use_llm=False)
    det_time = time.time() - t0
    print(f"Deterministic: {len(det['requirements'])} reqs in {det_time:.1f}s")
    for r in det["requirements"]:
        print(f"  {r['requirement_id']} {r['category']} src {r.get('source_document')}:{r.get('page_number')}")

    ingested = ingest_tender(tender_path, tender_id)
    doc_results = ingested["doc_results"]
    all_chunks = chunk_documents(doc_results, max_chars=3000)
    print(f"Total chunks: {len(all_chunks)}")
    selected, rationale = select_representative_chunks(all_chunks, doc_results, max_total=14, max_per_doc=3)
    # Depth pass (generic, evaluation-only): if category coverage yields <12, add longest
    # remaining chunks per document (page/location diversity) up to max_total/max_per_doc.
    # This preserves the generic selector (no tender-specific rules) while meeting the 12-15 bound.
    if len(selected) < 12:
        by_id = {c["chunk_id"]: c for c in all_chunks}
        selected_ids = {c["chunk_id"] for c in selected}
        per_doc = {}
        for c in selected:
            per_doc[c["source_document"]] = per_doc.get(c["source_document"], 0) + 1
        # Remaining sorted by text length (substantive) then early page
        remaining = [c for c in all_chunks if c["chunk_id"] not in selected_ids and len((c.get("text") or "").strip()) > 0]
        remaining.sort(key=lambda c: (-len((c.get("text") or "").strip()), c.get("page_number", 9999)))
        for c in remaining:
            if len(selected) >= 14:
                break
            if per_doc.get(c["source_document"], 0) >= 3:
                continue
            selected.append(c)
            per_doc[c["source_document"]] = per_doc.get(c["source_document"], 0) + 1
            # Compute deterministic categories for rationale (generic, same patterns)
            from evaluation.generic_extraction import GENERIC_PATTERNS
            import re as _re
            low = (c.get("text") or "").lower()
            hits = sorted({cat for pat, cat, _ in GENERIC_PATTERNS if _re.search(pat.lower(), low)})
            rationale.append({
                "chunk_id": c["chunk_id"], "source_document": c["source_document"],
                "page_number": c.get("page_number"), "text_len": len((c.get("text") or "").strip()),
                "deterministic_categories": hits, "reason": "document depth (page/location diversity, longest remaining)",
            })
    print(f"Selected {len(selected)} chunks (target 12-15):")
    for r in rationale:
        print(f"  {r['chunk_id']} {r['source_document']}:{r['page_number']} len {r['text_len']} cats {r['deterministic_categories']} — {r['reason']}")

    model = get_ollama_model()
    base = get_ollama_base_url()
    ok, msg = check_ollama_available()
    print(f"Ollama {model} {base} available={ok} {msg}")

    out_dir = Path(__file__).parent
    out_dir.joinpath("deterministic_baseline_3d.json").write_text(json.dumps(det, ensure_ascii=False, indent=2), encoding='utf-8')
    out_dir.joinpath("selected_chunks_3d.json").write_text(json.dumps(
        [{"chunk_id": c["chunk_id"], "source_document": c["source_document"], "page_number": c["page_number"], "text_len": len(c["text"]), "text": c["text"][:2000]} for c in selected],
        ensure_ascii=False, indent=2), encoding='utf-8')
    out_dir.joinpath("selection_rationale_3d.json").write_text(json.dumps(rationale, ensure_ascii=False, indent=2), encoding='utf-8')

    if not ok:
        print("Ollama unavailable — saving deterministic only, no fabrication")
        out_dir.joinpath("latency_telemetry_3d.json").write_text(json.dumps(
            {"deterministic_time": det_time, "llm_available": False, "llm_msg": msg, "selected": len(selected)},
            ensure_ascii=False, indent=2), encoding='utf-8')
        shutil.rmtree(tmp_root, ignore_errors=True)
        return

    all_reqs = []
    all_evs = []
    per_chunk = []
    latencies = []
    skipped = 0
    for chunk in selected:
        guard = tiny_guard_status(chunk)
        if guard != "OK":
            per_chunk.append({
                "chunk_id": chunk["chunk_id"], "source_document": chunk["source_document"],
                "page_number": chunk["page_number"], "latency": 0, "status": guard,
                "requirements": [], "evidence": [], "validation": "tiny-guard",
                "deterministic_signals": next((r["deterministic_categories"] for r in rationale if r["chunk_id"] == chunk["chunk_id"]), []),
            })
            print(f"Chunk {chunk['chunk_id']} {guard} (len {(len((chunk.get('text') or '').strip()))}) — skipped, no LLM call")
            skipped += 1
            continue
        t0c = time.time()
        res = call_ollama_for_chunk(chunk)
        lat = time.time() - t0c
        latencies.append(lat)
        entry = {"chunk_id": chunk["chunk_id"], "source_document": chunk["source_document"], "page_number": chunk["page_number"], "latency": lat, "status": None,
                 "deterministic_signals": next((r["deterministic_categories"] for r in rationale if r["chunk_id"] == chunk["chunk_id"]), [])}
        if not res:
            entry["status"] = "failure (no response/timeout)"
            entry["requirements"] = []
            entry["evidence"] = []
            per_chunk.append(entry)
            print(f"Chunk {chunk['chunk_id']} FAILED after {lat:.1f}s")
            continue
        parsed, status = parse_llm_json(res["raw"])
        entry["parse_status"] = status
        if not parsed:
            entry["status"] = f"failure (parse {status})"
            entry["requirements"] = []
            entry["evidence"] = []
            per_chunk.append(entry)
            print(f"Chunk {chunk['chunk_id']} parse failed {status}")
            continue
        # Same strict per-chunk logic as Stage 3C (preserved evidence fix)
        chunk_reqs = []
        chunk_evs = []
        seen_req_ids = set()
        orig_to_corrected = {}
        for idx_r, req in enumerate(parsed.get("requirements", [])):
            provided_cid = req.get("candidate_id") or req.get("requirement_id")
            if provided_cid and not provided_cid.startswith(chunk["chunk_id"]):
                corrected = f"{chunk['chunk_id']}-item-{idx_r+1:02d}"
                req["_original_candidate_id"] = provided_cid
                req["candidate_id"] = corrected
                req["requirement_id"] = corrected
                orig_to_corrected[provided_cid] = corrected
            elif "candidate_id" in req and "requirement_id" not in req:
                req["requirement_id"] = req["candidate_id"]
            elif "candidate_id" not in req and "requirement_id" not in req:
                gen_id = f"{chunk['chunk_id']}-item-{idx_r+1:02d}"
                req["candidate_id"] = gen_id
                req["requirement_id"] = gen_id
            if req.get("candidate_id") in seen_req_ids:
                dup_orig = req.get("candidate_id")
                corrected = f"{chunk['chunk_id']}-item-{idx_r+1:02d}-d{len(seen_req_ids)+1:02d}"
                req["_duplicate_candidate_id"] = dup_orig
                req["candidate_id"] = corrected
                req["requirement_id"] = corrected
            seen_req_ids.add(req.get("candidate_id"))
            if provided_cid and provided_cid.startswith(chunk["chunk_id"]):
                orig_to_corrected.setdefault(provided_cid, req.get("candidate_id"))
            req["extraction_method"] = "llm"
            ok_v, msg_v = validate_requirement(req, chunk)
            if not ok_v:
                req["confidence"] = 0.3
                req["provenance"] = None
                if "missing source_document" in msg_v:
                    continue
            if not req.get("source_document"):
                req["source_document"] = chunk["source_document"]
            if not req.get("page_number"):
                req["page_number"] = chunk["page_number"]
            chunk_reqs.append(req)
            all_reqs.append(req)

        chunk_req_ids = {r.get("candidate_id") for r in parsed.get("requirements", []) if r.get("candidate_id")}
        chunk_req_ids |= set(orig_to_corrected.keys()) | set(orig_to_corrected.values())
        chunk_req_ids |= {f"{chunk['chunk_id']}-item-{i+1:02d}" for i in range(len(parsed.get("requirements", [])))}
        seen_ev_ids = set()
        for idx_e, ev in enumerate(parsed.get("evidence", [])):
            if "candidate_id" in ev and "evidence_id" not in ev:
                provided_eid = ev["candidate_id"]
                if not provided_eid.startswith(chunk["chunk_id"]):
                    ev["_original_candidate_id"] = provided_eid
                    ev["candidate_id"] = f"{chunk['chunk_id']}-ev-{idx_e+1:02d}"
                    ev["evidence_id"] = ev["candidate_id"]
                else:
                    ev["evidence_id"] = ev["candidate_id"]
            elif "evidence_id" not in ev and "candidate_id" not in ev:
                gen_eid = f"{chunk['chunk_id']}-ev-{idx_e+1:02d}"
                ev["candidate_id"] = gen_eid
                ev["evidence_id"] = gen_eid
            if ev.get("candidate_id") in seen_ev_ids:
                ev["_duplicate_candidate_id"] = ev.get("candidate_id")
                ev["candidate_id"] = f"{chunk['chunk_id']}-ev-{idx_e+1:02d}-d{len(seen_ev_ids)+1:02d}"
                ev["evidence_id"] = ev["candidate_id"]
            seen_ev_ids.add(ev.get("candidate_id"))
            req_cand = ev.get("requirement_candidate_id")
            if not req_cand:
                ev["_rejected"] = "missing requirement_candidate_id"
                continue
            if req_cand in orig_to_corrected:
                ev["_original_requirement_candidate_id"] = req_cand
                req_cand = orig_to_corrected[req_cand]
                ev["requirement_candidate_id"] = req_cand
            if not req_cand.startswith(chunk["chunk_id"]):
                ev["_original_requirement_candidate_id"] = ev.get("_original_requirement_candidate_id", req_cand)
                ev["_rejected"] = f"cross-chunk hallucination {req_cand} not in {chunk['chunk_id']}"
                continue
            if req_cand not in chunk_req_ids:
                ev["_rejected"] = f"unknown candidate {req_cand} not in chunk {chunk['chunk_id']}"
                continue
            ok_e, msg_e = validate_evidence(ev, chunk)
            if not ok_e:
                continue
            if not ev.get("source_document"):
                ev["source_document"] = chunk["source_document"]
            if not ev.get("page_number"):
                ev["page_number"] = chunk["page_number"]
            if ev.get("source_document") != chunk["source_document"]:
                ev["_rejected"] = "source_document mismatch after validation"
                continue
            chunk_evs.append(ev)
            all_evs.append(ev)

        entry["status"] = "success"
        entry["requirements"] = [{"candidate_id": r.get("candidate_id"), "category": r.get("category"), "summary": (r.get("summary") or "")[:80]} for r in chunk_reqs]
        entry["evidence"] = [{"candidate_id": e.get("candidate_id"), "requirement_candidate_id": e.get("requirement_candidate_id"), "fact": (e.get("fact") or "")[:60]} for e in chunk_evs]
        entry["validation"] = "strict source-local"
        per_chunk.append(entry)
        print(f"Chunk {chunk['chunk_id']} success {len(chunk_reqs)} reqs {len(chunk_evs)} evs in {lat:.1f}s")

    deduped_reqs = deduplicate_requirements(all_reqs)
    seen = set()
    deduped_evs = []
    for ev in all_evs:
        key = (ev["fact"].lower().strip(), ev["source_document"], ev["page_number"])
        if key not in seen:
            seen.add(key)
            deduped_evs.append(ev)
    final_reqs, final_evs = assign_canonical_ids(deduped_reqs, deduped_evs)
    print(f"LLM final: {len(final_reqs)} reqs, {len(final_evs)} evs")
    for r in final_reqs:
        print(f"  {r['requirement_id']} {r['category']} {(r.get('summary') or '')[:60]} src {r.get('source_document')}:{r.get('page_number')}")

    out_dir.joinpath("llm_normalized_3d.json").write_text(json.dumps({"requirements": final_reqs, "evidence": final_evs, "model": model, "prompt_version": "Variant B"}, ensure_ascii=False, indent=2), encoding='utf-8')
    out_dir.joinpath("per_chunk_3d.json").write_text(json.dumps(per_chunk, ensure_ascii=False, indent=2), encoding='utf-8')
    gold_reqs = gold["gold_requirements"]
    comp = []
    for g in gold_reqs:
        det_match = next((e for e in det["requirements"] if e["category"] == g["category"]), None)
        llm_match = next((e for e in final_reqs if e["category"] == g["category"]), None)
        comp.append({"gold_id": g["gold_id"], "gold_category": g["category"], "gold_summary": g["summary"], "det_matched": det_match["requirement_id"] if det_match else None, "llm_matched": llm_match["requirement_id"] if llm_match else None, "source_document": g["source_document"]})
    out_dir.joinpath("per_requirement_comparison_3d.json").write_text(json.dumps(comp, ensure_ascii=False, indent=2), encoding='utf-8')
    lat_sorted = sorted(latencies)
    p95 = lat_sorted[int(len(lat_sorted)*0.95)] if lat_sorted else 0
    telemetry = {"deterministic_time": det_time, "llm_total": sum(latencies), "llm_avg": sum(latencies)/len(latencies) if latencies else 0, "llm_p95": p95, "llm_calls": len([p for p in per_chunk if p["status"] in ("success",) or "failure" in p["status"]]), "llm_successes": sum(1 for p in per_chunk if p["status"] == "success"), "llm_failures": sum(1 for p in per_chunk if "failure" in p["status"]), "llm_skipped": skipped, "det_reqs": len(det["requirements"]), "llm_reqs": len(final_reqs), "llm_evs": len(final_evs), "model": model, "base": base, "selected": len(selected)}
    out_dir.joinpath("latency_telemetry_3d.json").write_text(json.dumps(telemetry, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved 3D artifacts to {out_dir}")
    shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
