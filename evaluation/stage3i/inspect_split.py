import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation.stage3i.presegment import segment_parent_chunk

parents = json.loads(Path(__file__).parent.joinpath("parent_chunks_3i.json").read_text(encoding="utf-8")) if Path(__file__).parent.joinpath("parent_chunks_3i.json").exists() else None
if parents is None:
    rep = json.loads(Path(r"C:\Users\EgyTech\Desktop\TenderMind\evaluation\fixtures\mobile_llm_representative.json").read_text(encoding="utf-8"))
    want = ["chunk-0000","chunk-0001","chunk-0002","chunk-0004","chunk-0005","chunk-0007","chunk-0008","chunk-0010","chunk-0011","chunk-0012","chunk-0003","chunk-0009"]
    parents = [c for c in rep if c["chunk_id"] in want]
    Path(__file__).parent.joinpath("parent_chunks_3i.json").write_text(json.dumps(parents, ensure_ascii=False, indent=2), encoding="utf-8")

import io
out = io.open(Path(__file__).parent.joinpath("split_preview.txt"), "w", encoding="utf-8")
for p in parents:
    out.write(f"=== {p['chunk_id']} {p['source_document']}:{p['page_number']} ===\n")
    acc, rej = segment_parent_chunk(p)
    for a in acc:
        out.write(f"  ACCEPT {a['candidate_id']} hits={a['deterministic_signal_categories']} :: {a['source_text'][:110]}\n")
    for r in rej:
        out.write(f"  REJECT [{r['rejection_reason']}] hits={r['deterministic_signal_categories']} :: {r['source_text'][:110]}\n")
out.close()
print("wrote split_preview.txt")
