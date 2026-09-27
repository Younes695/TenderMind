"""Print accuracy tables from stage5a jsonl files (+ Stage 4B v1 baselines)."""
import json, glob, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")
D = os.path.dirname(os.path.abspath(__file__))
def acc(rows): return sum(r["pred"] == r["gold"] for r in rows), len(rows)
out = {}
for f in sorted(glob.glob(os.path.join(D, "*.jsonl"))):
    rows = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    c, n = acc(rows)
    lat = sum(r["latency"] for r in rows) / max(n, 1)
    print(f"{os.path.basename(f):40s} {c:3d}/{n:<3d} {c/max(n,1):.3f}  avg {lat:5.1f}s")
# Stage 4B stored v1 baselines (same scoring rules)
R = os.path.join(D, "..", "stage4b")
for tag in ["qwen25", "gemma", "phi", "qwen3"]:
    for ds in ["primary", "secondary"]:
        rows = [json.loads(l) for l in open(os.path.join(R, f"{tag}_{ds}_raw.jsonl"), encoding="utf-8") if l.strip()]
        if ds == "secondary":
            rows = [r for r in rows if not r["gold"].startswith("MULTI") and not r.get("arabic")]
        c = sum(r["predicted"] == r["gold"] for r in rows)
        print(f"4B baseline {tag}_v1_{ds:30s} {c:3d}/{len(rows):<3d} {c/len(rows):.3f}")
