"""
Stage 3E — Controlled Variant B vs Variant C A/B on the exact Stage 3D 12-chunk fixture.
No model/architecture/schema/evidence-plumbing change. Only system-prompt variant differs.
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
STAGE3D_RATIONALE = Path(__file__).resolve().parents[1] / "stage3d" / "selection_rationale_3d.json"

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


def run_variant(chunks, system_prompt, label):
    from evaluation.llm_generic_extraction import (
        parse_llm_json, validate_requirement, validate_evidence,
        deduplicate_requirements, assign_canonical_ids, call_ollama_for_chunk,
    )
    all_reqs = []
    all_evs = []
    per_chunk = []
    latencies = []
    for chunk in chunks:
        t0c = time.time()
        res = call_ollama_for_chunk(chunk, system_prompt=system_prompt)
        lat = time.time() - t0c
        latencies.append(lat)
        entry = {"chunk_id": chunk["chunk_id"], "source_document": chunk["source_document"],
                 "page_number": chunk["page_number"], "latency": lat, "status": None}
        if not res:
            entry["status"] = "failure (no response/timeout)"
            entry["requirements"] = []
            entry["evidence"] = []
            per_chunk.append(entry)
            print(f"[{label}] Chunk {chunk['chunk_id']} FAILED after {lat:.1f}s")
            continue
        parsed, status = parse_llm_json(res["raw"])
        entry["parse_status"] = status
        entry["raw_len"] = len(res["raw"])
        if not parsed:
            entry["status"] = f"failure (parse {status})"
            entry["requirements"] = []
            entry["evidence"] = []
            per_chunk.append(entry)
            print(f"[{label}] Chunk {chunk['chunk_id']} parse failed {status}")
            continue
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
                corrected = f"{chunk['chunk_id']}-item-{idx_r+1:02d}-d{len(seen_req_ids)+1:02d}"
                req["_duplicate_candidate_id"] = req.get("candidate_id")
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
        entry["requirements"] = [{"candidate_id": r.get("candidate_id"), "category": r.get("category"), "summary": (r.get("summary") or "")[:100], "mandatory": r.get("mandatory"), "applicable_entity": r.get("applicable_entity")} for r in chunk_reqs]
        entry["evidence"] = [{"candidate_id": e.get("candidate_id"), "requirement_candidate_id": e.get("requirement_candidate_id"), "fact": (e.get("fact") or "")[:80]} for e in chunk_evs]
        entry["validation"] = "strict source-local"
        per_chunk.append(entry)
        print(f"[{label}] Chunk {chunk['chunk_id']} success {len(chunk_reqs)} reqs {len(chunk_evs)} evs in {lat:.1f}s")

    deduped_reqs = deduplicate_requirements(all_reqs)
    seen = set()
    deduped_evs = []
    for ev in all_evs:
        key = (ev["fact"].lower().strip(), ev["source_document"], ev["page_number"])
        if key not in seen:
            seen.add(key)
            deduped_evs.append(ev)
    final_reqs, final_evs = assign_canonical_ids(deduped_reqs, deduped_evs)
    return final_reqs, final_evs, per_chunk, latencies


def main():
    from evaluation.generic_extraction import build_generic_extraction, ingest_tender
    from evaluation.llm_generic_extraction import (
        chunk_documents, get_ollama_model, get_ollama_base_url, check_ollama_available,
        LLM_SYSTEM_PROMPT, LLM_SYSTEM_PROMPT_VARIANT_C, prompt_hash,
        PROMPT_VERSION_B, PROMPT_VERSION_C,
    )
    from evaluation.stage3c.representative_selector import select_representative_chunks
    from evaluation.stage3d.tiny_guard import tiny_guard_status

    print(f"Variant B hash: {prompt_hash(LLM_SYSTEM_PROMPT)} version {PROMPT_VERSION_B}")
    print(f"Variant C hash: {prompt_hash(LLM_SYSTEM_PROMPT_VARIANT_C)} version {PROMPT_VERSION_C}")
    assert LLM_SYSTEM_PROMPT != LLM_SYSTEM_PROMPT_VARIANT_C
    assert LLM_SYSTEM_PROMPT_VARIANT_C.startswith(LLM_SYSTEM_PROMPT)

    tmp_root = Path(tempfile.mkdtemp(prefix="stage3e_"))
    tender_id = "Mobile-Stage3E-001"
    tender_path = build_subset_tender(tmp_root, tender_id)

    gold = json.loads(GOLD_PATH.read_text(encoding='utf-8'))

    t0 = time.time()
    det = build_generic_extraction(tender_path, tender_id=tender_id, use_llm=False)
    det_time = time.time() - t0
    print(f"Deterministic: {len(det['requirements'])} reqs in {det_time:.1f}s")

    ingested = ingest_tender(tender_path, tender_id)
    doc_results = ingested["doc_results"]
    all_chunks = chunk_documents(doc_results, max_chars=3000)
    print(f"Total chunks: {len(all_chunks)}")
    selected, rationale = select_representative_chunks(all_chunks, doc_results, max_total=14, max_per_doc=3)
    if len(selected) < 12:
        by_id = {c["chunk_id"]: c for c in all_chunks}
        selected_ids = {c["chunk_id"] for c in selected}
        per_doc = {}
        for c in selected:
            per_doc[c["source_document"]] = per_doc.get(c["source_document"], 0) + 1
        remaining = [c for c in all_chunks if c["chunk_id"] not in selected_ids and len((c.get("text") or "").strip()) > 0]
        remaining.sort(key=lambda c: (-len((c.get("text") or "").strip()), c.get("page_number", 9999)))
        for c in remaining:
            if len(selected) >= 14:
                break
            if per_doc.get(c["source_document"], 0) >= 3:
                continue
            selected.append(c)
            per_doc[c["source_document"]] = per_doc.get(c["source_document"], 0) + 1
            from evaluation.generic_extraction import GENERIC_PATTERNS
            import re as _re
            low = (c.get("text") or "").lower()
            hits = sorted({cat for pat, cat, _ in GENERIC_PATTERNS if _re.search(pat.lower(), low)})
            rationale.append({"chunk_id": c["chunk_id"], "source_document": c["source_document"], "page_number": c.get("page_number"), "text_len": len((c.get("text") or "").strip()), "deterministic_categories": hits, "reason": "document depth (page/location diversity, longest remaining)"})
    print(f"Selected {len(selected)} chunks (must match Stage 3D 12):")
    for r in rationale:
        print(f"  {r['chunk_id']} {r['source_document']}:{r['page_number']} len {r['text_len']}")

    # Verify same 12 chunk_ids as Stage 3D
    expected_3d = [r["chunk_id"] for r in json.loads(STAGE3D_RATIONALE.read_text(encoding='utf-8'))]
    got = [c["chunk_id"] for c in selected]
    print(f"Stage 3D chunk_ids: {expected_3d}")
    print(f"Stage 3E chunk_ids: {got}")
    print(f"Match: {got == expected_3d}")

    # Tiny guard (same as 3D)
    filtered = []
    skipped = []
    for c in selected:
        g = tiny_guard_status(c)
        if g != "OK":
            skipped.append({"chunk_id": c["chunk_id"], "status": g})
            print(f"Chunk {c['chunk_id']} {g} — skipped, no LLM call")
        else:
            filtered.append(c)
    print(f"LLM chunks after tiny guard: {len(filtered)} (skipped {len(skipped)})")

    model = get_ollama_model()
    base = get_ollama_base_url()
    ok, msg = check_ollama_available()
    print(f"Ollama {model} {base} available={ok} {msg}")
    if not ok:
        print("Ollama unavailable — no fabrication")
        return

    out_dir = Path(__file__).parent
    out_dir.joinpath("prompt_hashes_3e.json").write_text(json.dumps({
        "variant_B": {"version": PROMPT_VERSION_B, "hash": prompt_hash(LLM_SYSTEM_PROMPT), "len": len(LLM_SYSTEM_PROMPT)},
        "variant_C": {"version": PROMPT_VERSION_C, "hash": prompt_hash(LLM_SYSTEM_PROMPT_VARIANT_C), "len": len(LLM_SYSTEM_PROMPT_VARIANT_C)},
    }, indent=2), encoding='utf-8')
    # Save exact diff (C additions only)
    diff_text = LLM_SYSTEM_PROMPT_VARIANT_C[len(LLM_SYSTEM_PROMPT):]
    out_dir.joinpath("prompt_diff_3e.txt").write_text(
        f"Variant B len {len(LLM_SYSTEM_PROMPT)} hash {prompt_hash(LLM_SYSTEM_PROMPT)}\n"
        f"Variant C len {len(LLM_SYSTEM_PROMPT_VARIANT_C)} hash {prompt_hash(LLM_SYSTEM_PROMPT_VARIANT_C)}\n"
        f"--- Added suffix (Variant C only) ---\n{diff_text}\n", encoding='utf-8')
    only = sys.argv[1] if len(sys.argv) > 1 else "both"  # B, C, or both
    print(f"Mode: {only}")
    out_dir.joinpath("deterministic_baseline_3e.json").write_text(json.dumps(det, ensure_ascii=False, indent=2), encoding='utf-8')
    out_dir.joinpath("selected_chunks_3e.json").write_text(json.dumps(
        [{"chunk_id": c["chunk_id"], "source_document": c["source_document"], "page_number": c["page_number"], "text_len": len(c["text"]), "text": c["text"][:2000]} for c in selected],
        ensure_ascii=False, indent=2), encoding='utf-8')
    # Save full chunk texts for exact reproducibility (not truncated)
    out_dir.joinpath("selected_chunks_full_3e.json").write_text(json.dumps(
        [{"chunk_id": c["chunk_id"], "source_document": c["source_document"], "page_number": c["page_number"], "text": c["text"]} for c in selected],
        ensure_ascii=False, indent=2), encoding='utf-8')

    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT as SYS_B, LLM_SYSTEM_PROMPT_VARIANT_C as SYS_C

    def comp(reqs):
        return [{"gold_id": g["gold_id"], "gold_category": g["category"], "matched": next((e["requirement_id"] for e in reqs if e["category"] == g["category"]), None)} for g in gold["gold_requirements"]]

    def tel(lat, per, reqs, evs):
        s = sorted(lat)
        return {"total": sum(lat), "avg": sum(lat)/len(lat) if lat else 0, "p95": s[int(len(s)*0.95)] if s else 0,
                "calls": len(per), "successes": sum(1 for p in per if p["status"] == "success"),
                "failures": sum(1 for p in per if "failure" in p["status"]), "reqs": len(reqs), "evs": len(evs)}

    if only in ("B", "both"):
        print("\n=== Variant B ===")
        b_reqs, b_evs, b_per, b_lat = run_variant(filtered, SYS_B, "B")
        print(f"B final: {len(b_reqs)} reqs, {len(b_evs)} evs")
        out_dir.joinpath("variant_b_3e.json").write_text(json.dumps({"requirements": b_reqs, "evidence": b_evs}, ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("per_chunk_b_3e.json").write_text(json.dumps(b_per, ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("per_requirement_comparison_b_3e.json").write_text(json.dumps(comp(b_reqs), ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("latency_b_3e.json").write_text(json.dumps(tel(b_lat, b_per, b_reqs, b_evs), ensure_ascii=False, indent=2), encoding='utf-8')
        print("Saved Variant B artifacts (incremental, safe if C times out)")
    if only in ("C", "both"):
        print("\n=== Variant C ===")
        c_reqs, c_evs, c_per, c_lat = run_variant(filtered, SYS_C, "C")
        print(f"C final: {len(c_reqs)} reqs, {len(c_evs)} evs")
        out_dir.joinpath("variant_c_3e.json").write_text(json.dumps({"requirements": c_reqs, "evidence": c_evs}, ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("per_chunk_c_3e.json").write_text(json.dumps(c_per, ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("per_requirement_comparison_c_3e.json").write_text(json.dumps(comp(c_reqs), ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("latency_c_3e.json").write_text(json.dumps(tel(c_lat, c_per, c_reqs, c_evs), ensure_ascii=False, indent=2), encoding='utf-8')
        print("Saved Variant C artifacts")
    # Combined comparison + telemetry (only if both present)
    try:
        b_data = json.loads(out_dir.joinpath("variant_b_3e.json").read_text(encoding='utf-8'))
        c_data = json.loads(out_dir.joinpath("variant_c_3e.json").read_text(encoding='utf-8'))
        out_dir.joinpath("per_requirement_comparison_3e.json").write_text(json.dumps(
            {"B": comp(b_data["requirements"]), "C": comp(c_data["requirements"])}, ensure_ascii=False, indent=2), encoding='utf-8')
        b_lat = json.loads(out_dir.joinpath("latency_b_3e.json").read_text(encoding='utf-8'))
        c_lat = json.loads(out_dir.joinpath("latency_c_3e.json").read_text(encoding='utf-8'))
        out_dir.joinpath("latency_telemetry_3e.json").write_text(json.dumps(
            {"B": b_lat, "C": c_lat, "skipped": skipped, "model": model, "base": base, "deterministic_time": det_time},
            ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"Combined artifacts deferred (need both variants): {e}")
    print(f"Saved 3E artifacts to {out_dir}")
    shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
