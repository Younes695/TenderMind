"""
Stage 3B v2 — LLM validation with representative chunks (one per document)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
import json, time, tempfile, shutil, re
from pathlib import Path
import fitz

MOBILE_ROOT = Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations")
GOLD_PATH = Path(__file__).resolve().parents[1] / "gold" / "mobile_representative_gold.json"

def create_tender_with_chunks(tmp_root, tender_id):
    tender_dir = tmp_root / tender_id
    tender_dir.mkdir(parents=True, exist_ok=True)
    for p in [MOBILE_ROOT / "Commercial forms.txt", MOBILE_ROOT / "Price schedules of 6th October northern Extention 22-22-22 KV GIS SS.xlsx", MOBILE_ROOT / "Drawings.pdf", MOBILE_ROOT / "Tender Price Schedule- التوسعات الشمالية.pdf"]:
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

tmp_root = Path(tempfile.mkdtemp(prefix="stage3b_v2_"))
tender_id = "Mobile-Stage3B-LLM-002"
tender_path = create_tender_with_chunks(tmp_root, tender_id)
print(f"Tender: {tender_path}")

from evaluation.generic_extraction import build_generic_extraction, ingest_tender
from evaluation.llm_generic_extraction import chunk_documents as llm_chunk, get_ollama_model, get_ollama_base_url, check_ollama_available, llm_extract_requirements_for_tender
import json

# Deterministic
t0 = time.time()
det = build_generic_extraction(tender_path, tender_id=tender_id, use_llm=False)
det_time = time.time() - t0
print(f"Deterministic: {len(det['requirements'])} reqs in {det_time:.1f}s")
for r in det["requirements"]:
    print(f"  {r['requirement_id']} {r['category']} {r['summary'][:50]}")

# For LLM, use representative chunks: one per document, up to 8
ingested = ingest_tender(tender_path, tender_id)
doc_results = ingested["doc_results"]
chunks_all = llm_chunk(doc_results, max_chars=3000)
print(f"Total chunks: {len(chunks_all)}")
# Group by source_document, pick first chunk per doc, up to 8
from collections import OrderedDict
by_doc = OrderedDict()
for c in chunks_all:
    by_doc.setdefault(c["source_document"], []).append(c)
selected = []
for doc, clist in by_doc.items():
    selected.append(clist[0])
    if len(selected) >= 8:
        break
print(f"Selected {len(selected)} representative chunks (one per doc):")
for c in selected:
    print(f"  {c['chunk_id']} {c['source_document']}:{c['page_number']} len {len(c['text'])}")

# Now run LLM on these selected chunks via direct calls (to avoid re-chunking inside llm_extract... which would use first 5)
# Instead, we will call llm_extract... with max_chunks=15 to cover all, but to keep time we use our selected
# For this v2, we will manually call the LLM per selected chunk and collect

from evaluation.llm_generic_extraction import call_ollama_for_chunk, parse_llm_json, validate_requirement, validate_evidence, deduplicate_requirements, assign_canonical_ids
import time

model = get_ollama_model()
base = get_ollama_base_url()
ok, msg = check_ollama_available()
print(f"Ollama {model} {base} {ok} {msg}")
if not ok:
    print("No LLM, exit")
    sys.exit(0)

all_reqs = []
all_evs = []
latencies = []
for chunk in selected:
    t0c = time.time()
    res = call_ollama_for_chunk(chunk)
    lat = time.time() - t0c
    latencies.append(lat)
    if not res:
        print(f"Chunk {chunk['chunk_id']} no response after {lat:.1f}s")
        continue
    parsed, status = parse_llm_json(res["raw"])
    print(f"Chunk {chunk['chunk_id']} {status} len {len(res['raw'])} in {lat:.1f}s")
    if not parsed:
        print(f"  Failed parse: {status}")
        continue
    for idx_r, req in enumerate(parsed.get("requirements", [])):
        # Ensure candidate_id
        cid = req.get("candidate_id") or req.get("requirement_id") or f"{chunk['chunk_id']}-item-{idx_r+1:02d}"
        if not cid.startswith(chunk["chunk_id"]):
            cid = f"{chunk['chunk_id']}-item-{idx_r+1:02d}"
        req["candidate_id"] = cid
        req["requirement_id"] = cid
        req["extraction_method"] = "llm"
        ok_v, msg_v = validate_requirement(req, chunk)
        if not ok_v:
            print(f"  Req {cid} invalid: {msg_v}")
            continue
        all_reqs.append(req)
    for idx_e, ev in enumerate(parsed.get("evidence", [])):
        eid = ev.get("candidate_id") or ev.get("evidence_id") or f"{chunk['chunk_id']}-ev-{idx_e+1:02d}"
        if not eid.startswith(chunk["chunk_id"]):
            eid = f"{chunk['chunk_id']}-ev-{idx_e+1:02d}"
        ev["candidate_id"] = eid
        ev["evidence_id"] = eid
        ok_e, msg_e = validate_evidence(ev, chunk)
        if not ok_e:
            print(f"  Ev {eid} invalid: {msg_e}")
            continue
        all_evs.append(ev)

print(f"LLM raw: {len(all_reqs)} reqs, {len(all_evs)} evs")
# Deduplicate and assign canonical
from evaluation.llm_generic_extraction import deduplicate_requirements, assign_canonical_ids
deduped = deduplicate_requirements(all_reqs)
# Dedup evidence
seen = set()
deduped_evs = []
for ev in all_evs:
    key = (ev["fact"].lower().strip(), ev["source_document"], ev["page_number"])
    if key not in seen:
        seen.add(key)
        deduped_evs.append(ev)
final_reqs, final_evs = assign_canonical_ids(deduped, deduped_evs)
print(f"After dedup/canonical: {len(final_reqs)} reqs, {len(final_evs)} evs")
for r in final_reqs:
    summ = r['summary'][:70].encode('ascii', errors='ignore').decode()
    print(f"  {r['requirement_id']} {r['category']} {summ} src {r.get('source_document')}:{r.get('page_number')} conf {r.get('confidence')}")
for e in final_evs:
    print(f"  EV {e['evidence_id']} -> {e.get('requirement_id')} {e.get('fact')[:50]}")

# Save
out_dir = Path(__file__).parent
out_dir.joinpath("llm_v2_reqs.json").write_text(json.dumps(final_reqs, ensure_ascii=False, indent=2), encoding='utf-8')
out_dir.joinpath("llm_v2_evs.json").write_text(json.dumps(final_evs, ensure_ascii=False, indent=2), encoding='utf-8')
out_dir.joinpath("llm_v2_det.json").write_text(json.dumps(det, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"Avg latency {sum(latencies)/len(latencies):.1f}s total {sum(latencies):.1f}s p95 {sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0:.1f}s calls {len(latencies)}")

shutil.rmtree(tmp_root, ignore_errors=True)
