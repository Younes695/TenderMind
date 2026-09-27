"""
Stage 3F — Controlled Variant B vs Variant D (structural multi-requirement instruction).
Same 12-chunk fixture as 3D/3E. Only system-prompt variant differs.
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

# Reuse 3E harness pieces (same strict evidence logic, same tiny guard, same selector)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage3e"))
from run_3e_ab import run_variant, build_subset_tender

MOBILE_ROOT = Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations")
GOLD_PATH = Path(__file__).resolve().parents[1] / "gold" / "mobile_representative_gold.json"
STAGE3D_RATIONALE = Path(__file__).resolve().parents[1] / "stage3d" / "selection_rationale_3d.json"


def main():
    from evaluation.generic_extraction import build_generic_extraction, ingest_tender
    from evaluation.llm_generic_extraction import (
        chunk_documents, get_ollama_model, get_ollama_base_url, check_ollama_available,
        LLM_SYSTEM_PROMPT, LLM_SYSTEM_PROMPT_VARIANT_D, prompt_hash,
        PROMPT_VERSION_B, PROMPT_VERSION_D,
    )
    from evaluation.stage3c.representative_selector import select_representative_chunks
    from evaluation.stage3d.tiny_guard import tiny_guard_status

    print(f"Variant B hash: {prompt_hash(LLM_SYSTEM_PROMPT)} version {PROMPT_VERSION_B}")
    print(f"Variant D hash: {prompt_hash(LLM_SYSTEM_PROMPT_VARIANT_D)} version {PROMPT_VERSION_D}")
    assert LLM_SYSTEM_PROMPT != LLM_SYSTEM_PROMPT_VARIANT_D
    assert LLM_SYSTEM_PROMPT_VARIANT_D.startswith(LLM_SYSTEM_PROMPT)

    only = sys.argv[1] if len(sys.argv) > 1 else "both"
    print(f"Mode: {only}")

    tmp_root = Path(tempfile.mkdtemp(prefix="stage3f_"))
    tender_id = "Mobile-Stage3F-001"
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
    print(f"Selected {len(selected)} chunks:")
    for r in rationale:
        print(f"  {r['chunk_id']} {r['source_document']}:{r['page_number']} len {r['text_len']}")

    expected_3d = [r["chunk_id"] for r in json.loads(STAGE3D_RATIONALE.read_text(encoding='utf-8'))]
    got = [c["chunk_id"] for c in selected]
    print(f"Stage 3D chunk_ids: {expected_3d}")
    print(f"Stage 3F chunk_ids: {got}")
    print(f"Match: {got == expected_3d}")

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
    out_dir.joinpath("prompt_hashes_3f.json").write_text(json.dumps({
        "variant_B": {"version": PROMPT_VERSION_B, "hash": prompt_hash(LLM_SYSTEM_PROMPT), "len": len(LLM_SYSTEM_PROMPT)},
        "variant_D": {"version": PROMPT_VERSION_D, "hash": prompt_hash(LLM_SYSTEM_PROMPT_VARIANT_D), "len": len(LLM_SYSTEM_PROMPT_VARIANT_D)},
    }, indent=2), encoding='utf-8')
    diff_text = LLM_SYSTEM_PROMPT_VARIANT_D[len(LLM_SYSTEM_PROMPT):]
    out_dir.joinpath("prompt_diff_3f.txt").write_text(
        f"Variant B len {len(LLM_SYSTEM_PROMPT)} hash {prompt_hash(LLM_SYSTEM_PROMPT)}\n"
        f"Variant D len {len(LLM_SYSTEM_PROMPT_VARIANT_D)} hash {prompt_hash(LLM_SYSTEM_PROMPT_VARIANT_D)}\n"
        f"--- Added line (Variant D only) ---\n{diff_text}\n", encoding='utf-8')
    out_dir.joinpath("deterministic_baseline_3f.json").write_text(json.dumps(det, ensure_ascii=False, indent=2), encoding='utf-8')
    out_dir.joinpath("selected_chunks_3f.json").write_text(json.dumps(
        [{"chunk_id": c["chunk_id"], "source_document": c["source_document"], "page_number": c["page_number"], "text_len": len(c["text"]), "text": c["text"][:2000]} for c in selected],
        ensure_ascii=False, indent=2), encoding='utf-8')
    out_dir.joinpath("selected_chunks_full_3f.json").write_text(json.dumps(
        [{"chunk_id": c["chunk_id"], "source_document": c["source_document"], "page_number": c["page_number"], "text": c["text"]} for c in selected],
        ensure_ascii=False, indent=2), encoding='utf-8')

    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT as SYS_B, LLM_SYSTEM_PROMPT_VARIANT_D as SYS_D

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
        out_dir.joinpath("variant_b_3f.json").write_text(json.dumps({"requirements": b_reqs, "evidence": b_evs}, ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("per_chunk_b_3f.json").write_text(json.dumps(b_per, ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("per_requirement_comparison_b_3f.json").write_text(json.dumps(comp(b_reqs), ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("latency_b_3f.json").write_text(json.dumps(tel(b_lat, b_per, b_reqs, b_evs), ensure_ascii=False, indent=2), encoding='utf-8')
        print("Saved Variant B artifacts (incremental)")
    if only in ("D", "both"):
        print("\n=== Variant D ===")
        d_reqs, d_evs, d_per, d_lat = run_variant(filtered, SYS_D, "D")
        print(f"D final: {len(d_reqs)} reqs, {len(d_evs)} evs")
        out_dir.joinpath("variant_d_3f.json").write_text(json.dumps({"requirements": d_reqs, "evidence": d_evs}, ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("per_chunk_d_3f.json").write_text(json.dumps(d_per, ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("per_requirement_comparison_d_3f.json").write_text(json.dumps(comp(d_reqs), ensure_ascii=False, indent=2), encoding='utf-8')
        out_dir.joinpath("latency_d_3f.json").write_text(json.dumps(tel(d_lat, d_per, d_reqs, d_evs), ensure_ascii=False, indent=2), encoding='utf-8')
        print("Saved Variant D artifacts")
    try:
        b_data = json.loads(out_dir.joinpath("variant_b_3f.json").read_text(encoding='utf-8'))
        d_data = json.loads(out_dir.joinpath("variant_d_3f.json").read_text(encoding='utf-8'))
        out_dir.joinpath("per_requirement_comparison_3f.json").write_text(json.dumps(
            {"B": comp(b_data["requirements"]), "D": comp(d_data["requirements"])}, ensure_ascii=False, indent=2), encoding='utf-8')
        b_lat = json.loads(out_dir.joinpath("latency_b_3f.json").read_text(encoding='utf-8'))
        d_lat = json.loads(out_dir.joinpath("latency_d_3f.json").read_text(encoding='utf-8'))
        out_dir.joinpath("latency_telemetry_3f.json").write_text(json.dumps(
            {"B": b_lat, "D": d_lat, "skipped": skipped, "model": model, "base": base, "deterministic_time": det_time},
            ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"Combined artifacts deferred (need both variants): {e}")
    print(f"Saved 3F artifacts to {out_dir}")
    shutil.rmtree(tmp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
