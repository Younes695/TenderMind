import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation.stage3i.presegment import segment_parent_chunk

rep = json.loads(Path(r"C:\Users\EgyTech\Desktop\TenderMind\evaluation\fixtures\mobile_llm_representative.json").read_text(encoding="utf-8"))
by_id = {c["chunk_id"]: c for c in rep}

# (parent_chunk, seg_id, gold) — gold = obvious primary purpose (same mapping as 3G/3H)
PICKS = [
    ("chunk-0000", "chunk-0000-seg-01", "TECHNICAL"),
    ("chunk-0000", "chunk-0000-seg-02", "COMMERCIAL"),
    ("chunk-0000", "chunk-0000-seg-03", "EXPERIENCE"),
    ("chunk-0000", "chunk-0000-seg-04", "SCHEDULE"),
    ("chunk-0000", "chunk-0000-seg-05", "LEGAL"),
    ("chunk-0001", "chunk-0001-seg-03", "COMMERCIAL"),
    ("chunk-0001", "chunk-0001-seg-04", "FINANCIAL"),
    ("chunk-0002", "chunk-0002-seg-03", "FINANCIAL"),
    ("chunk-0004", "chunk-0004-seg-01", "EQUIPMENT"),
    ("chunk-0005", "chunk-0005-seg-03", "HSE"),
    ("chunk-0005", "chunk-0005-seg-04", "QA_QC"),
    ("chunk-0008", "chunk-0008-seg-01", "LEGAL"),
    ("chunk-0010", "chunk-0010-seg-01", "PERSONNEL"),
    ("chunk-0010", "chunk-0010-seg-02", "SUBCONTRACTOR"),
    ("chunk-0012", "chunk-0012-seg-02", "SCHEDULE"),
    ("chunk-0007", "chunk-0007-seg-01", "COMMERCIAL"),
]

# Regenerate segments deterministically and match
seg_index = {}
for pid in sorted(set(p for p, _, _ in PICKS)):
    acc, _ = segment_parent_chunk(by_id[pid])
    for a in acc:
        seg_index[(pid, a["candidate_id"])] = a

out = []
for i, (pid, seg, gold) in enumerate(PICKS, 1):
    a = seg_index[(pid, seg)]
    out.append({
        "candidate_id": f"3i-{i:02d}",
        "parent_chunk_id": pid,
        "parent_seg_id": seg,
        "source_document": a["source_document"],
        "page": a["page"],
        "source_text": a["source_text"],
        "span": a["span"],
        "deterministic_signal_categories": a["deterministic_signal_categories"],
        "category_gold": gold,
        "selection_reason": f"Accepted splitter candidate covering {gold}; signals={a['deterministic_signal_categories']}",
    })

Path(__file__).parent.joinpath("generated_candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(out)} candidates")
for c in out:
    print(f"  {c['candidate_id']} {c['parent_seg_id']} gold={c['category_gold']} signals={c['deterministic_signal_categories']} :: {c['source_text'][:80]}")
