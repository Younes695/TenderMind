"""Measure full-Mobile segmentation scale (no LLM) to plan Experiment B."""
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
from evaluation.generic_extraction import ingest_tender
from evaluation.stage3k.two_stage_pipeline import discover_candidates

MOBILE_ROOT = Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations")
files = [p for p in MOBILE_ROOT.rglob("*") if p.is_file()]
print(f"Mobile files: {len(files)}")
for f in files:
    print(f"  {f.name} {f.suffix} {f.stat().st_size/1024/1024:.1f}MB")

t0 = time.time()
ing = ingest_tender(MOBILE_ROOT, "Mobile-Full-Scale")
dt_ing = time.time() - t0
print(f"Ingestion: {dt_ing:.1f}s")
t0 = time.time()
acc, rej, skipped = discover_candidates(doc_results=ing["doc_results"])
dt_seg = time.time() - t0
print(f"Candidates accepted: {len(acc)}, rejected: {len(rej)}, tiny-skipped chunks: {len(skipped)}, seg time {dt_seg:.1f}s")
from collections import Counter
print("Accepted signal cats:", Counter(tuple(sorted(a.get('deterministic_signal_categories', []))) for a in acc))
print("Rejected reasons:", Counter(r["rejection_reason"] for r in rej))
Path(__file__).parent.joinpath("scale_measurement_3k.json").write_text(json.dumps({
    "files": len(files), "ingestion_s": dt_ing, "accepted": len(acc),
    "rejected": len(rej), "skipped_tiny": len(skipped),
    "rejection_reasons": dict(Counter(r["rejection_reason"] for r in rej)),
}, indent=2))
print("saved scale_measurement_3k.json")
