"""
Stage 3B — LLM Semantic Normalization Validation
Compares deterministic baseline vs deterministic + LLM (qwen2.5:3b Variant B) on same Mobile fixture.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding='utf-8', errors='ignore')

import json
import time
import tempfile
import shutil
import re
from pathlib import Path
import fitz

# Setup paths
MOBILE_ROOT = Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations")
GOLD_PATH = Path(__file__).resolve().parents[1] / "gold" / "mobile_representative_gold.json"
# Use same 5-file subset as Stage 3A
SUBSET_FILES = [
    MOBILE_ROOT / "Commercial forms.txt",
    MOBILE_ROOT / "Price schedules of 6th October northern Extention 22-22-22 KV GIS SS.xlsx",
    MOBILE_ROOT / "Drawings.pdf",
    MOBILE_ROOT / "Tender Price Schedule- التوسعات الشمالية.pdf",
]

def create_subset_tender(tmp_root: Path, tender_id: str):
    # Create temp tender dir with subset files, including Vol I subset 20 pages
    tender_dir = tmp_root / tender_id
    tender_dir.mkdir(parents=True, exist_ok=True)
    for p in SUBSET_FILES:
        if p.exists():
            shutil.copy2(str(p), str(tender_dir / p.name))
    # Add Vol I subset 20 pages
    vol1 = MOBILE_ROOT / "Vol I - Tender Document.pdf"
    if vol1.exists():
        doc = fitz.open(str(vol1))
        new = fitz.open()
        for i in range(min(20, len(doc))):
            new.insert_pdf(doc, from_page=i, to_page=i)
        subset_path = tender_dir / "Vol I subset 20pages.pdf"
        new.save(str(subset_path))
        new.close()
        doc.close()
    return tender_dir

# Create temp tender
tmp_root = Path(tempfile.mkdtemp(prefix="stage3b_"))
tender_id = "Mobile-Stage3B-LLM-001"
tender_path = create_subset_tender(tmp_root, tender_id)
print(f"Tender path: {tender_path}")
print(f"Files: {list(tender_path.glob('*'))}")

# Load gold
gold = json.loads(GOLD_PATH.read_text(encoding='utf-8'))
gold_reqs = gold["gold_requirements"]
print(f"Gold: {len(gold_reqs)} requirements")

# Deterministic baseline
from evaluation.generic_extraction import build_generic_extraction, ingest_tender
from evaluation.llm_generic_extraction import chunk_documents as llm_chunk, get_ollama_model, get_ollama_base_url, check_ollama_available, call_ollama_for_chunk, parse_llm_json, validate_requirement, validate_evidence, deduplicate_requirements, assign_canonical_ids, llm_extract_requirements_for_tender

print("\n=== A) DETERMINISTIC BASELINE ===")
t0 = time.time()
det_result = build_generic_extraction(tender_path, tender_id=tender_id, use_llm=False)
det_time = time.time() - t0
det_reqs = det_result["requirements"]
det_docs = det_result["documents"]
print(f"Deterministic: {len(det_reqs)} reqs in {det_time:.1f}s")
for r in det_reqs:
    print(f"  {r['requirement_id']} {r['category']} {r['summary'][:50]} src {r.get('source_document')}:{r.get('page_number')}")

# Also get doc_results for chunking
ingested = ingest_tender(tender_path, tender_id)
doc_results = ingested["doc_results"]
chunks = llm_chunk(doc_results, max_chars=3000)
print(f"Chunks: {len(chunks)} (max 5 for LLM)")
for c in chunks[:5]:
    print(f"  {c['chunk_id']} {c['source_document']}:{c['page_number']} len {len(c['text'])}")

# Check Ollama
model = get_ollama_model()
base = get_ollama_base_url()
ok, msg = check_ollama_available()
print(f"\n=== Ollama ===")
print(f"Model: {model} Base: {base} Available: {ok} {msg}")
if not ok:
    print("Ollama not available — cannot run LLM, will report and exit")
    # Still produce deterministic baseline artifact
    out_dir = Path(__file__).parent
    det_path = out_dir / "deterministic_baseline.json"
    det_path.write_text(json.dumps(det_result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Deterministic baseline saved to {det_path}")
    sys.exit(0)

# LLM path
print(f"\n=== B) DETERMINISTIC + LLM (qwen2.5:3b Variant B) ===")
# Use the same chunks (first 5) as deterministic, feed to LLM
# We will call llm_extract_requirements_for_tender which internally does ingest_tender + chunking + LLM per chunk
# To isolate LLM contribution, we use the same tender_path and max_chunks=5, same as deterministic's doc_results
t0_llm = time.time()
llm_reqs, llm_evs = llm_extract_requirements_for_tender(tender_path, tender_id=tender_id, max_chunks=5)
llm_time = time.time() - t0_llm
print(f"LLM: {len(llm_reqs)} reqs, {len(llm_evs)} evs in {llm_time:.1f}s")
for r in llm_reqs:
    summ = r['summary'][:60].encode('ascii', errors='ignore').decode()
    print(f"  {r['requirement_id']} {r['category']} {summ} src {r.get('source_document')}:{r.get('page_number')} conf {r.get('confidence')} method {r.get('extraction_method')}")
for e in llm_evs:
    print(f"  EV {e['evidence_id']} -> {e.get('requirement_id')} {e.get('fact')[:50]} src {e.get('source_document')}:{e.get('page_number')}")

# Save artifacts
out_dir = Path(__file__).parent
det_path = out_dir / "deterministic_baseline.json"
llm_path = out_dir / "llm_normalized.json"
det_path.write_text(json.dumps(det_result, ensure_ascii=False, indent=2), encoding='utf-8')
llm_data = {"requirements": llm_reqs, "evidence": llm_evs, "model": model, "base": base, "prompt_version": "Variant B", "chunks": chunks[:5]}
llm_path.write_text(json.dumps(llm_data, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\nSaved deterministic to {det_path}")
print(f"Saved LLM to {llm_path}")

# Also save per-requirement comparison
# For each gold, check if deterministic and LLM matched
def is_category_match(g_cat, e_cat):
    return g_cat == e_cat

# Build comparison
import re
def find_match(gold_req, extracted_list):
    g_cat = gold_req["category"]
    # Check if any extracted has same category and summary contains key terms (lenient)
    for e in extracted_list:
        if e["category"] == g_cat:
            # Check if summary is not generic candidate?
            # For LLM, summary should be specific, not generic
            e_sum_low = e["summary"].lower()
            # If LLM summary is specific, it should contain some gold summary keywords
            # For now, just category match is lenient
            return e
    return None

comparison = []
for g in gold_reqs:
    det_match = find_match(g, det_reqs)
    llm_match = find_match(g, llm_reqs)
    comparison.append({
        "gold_id": g["gold_id"],
        "gold_category": g["category"],
        "gold_summary": g["summary"],
        "det_matched": det_match["requirement_id"] if det_match else None,
        "det_category": det_match["category"] if det_match else None,
        "llm_matched": llm_match["requirement_id"] if llm_match else None,
        "llm_category": llm_match["category"] if llm_match else None,
        "source_document": g["source_document"],
    })

comparison_path = out_dir / "per_requirement_comparison.json"
comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Saved comparison to {comparison_path}")

# Latency telemetry
telemetry = {
    "deterministic_time": det_time,
    "llm_time": llm_time,
    "chunks": len(chunks[:5]),
    "model": model,
    "base": base,
    "det_reqs": len(det_reqs),
    "llm_reqs": len(llm_reqs),
    "llm_evs": len(llm_evs),
}
telemetry_path = out_dir / "latency_telemetry.json"
telemetry_path.write_text(json.dumps(telemetry, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Saved telemetry to {telemetry_path}")

# Cleanup
shutil.rmtree(tmp_root, ignore_errors=True)
print("\n=== Stage 3B LLM validation done ===")
