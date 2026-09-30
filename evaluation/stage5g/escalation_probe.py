"""Stage 5G: re-ask only qwen2.5:3b UNKNOWN/failed rows (stage5a v2 outputs) to a
second model and rescore. Usage: python evaluation/stage5g/escalation_probe.py qwen3:4b"""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from evaluation.stage5a.run_5a import call, load_set, PROMPTS
sys.stdout.reconfigure(encoding="utf-8")
esc_model = sys.argv[1]
tot_c = tot_n = 0
for s in ["primary", "secondary", "sarai"]:
    rows = {r["id"]: r for r in map(json.loads, open(REPO/f"evaluation/stage5a/qwen2.5-3b_v2_{s}.jsonl", encoding="utf-8"))}
    c = n = 0
    for cid, text, gold in load_set(s):
        r = rows[cid]; pred = r["pred"]
        if r["status"] != "ok" or pred in (None, "UNKNOWN"):
            req, st, lat, raw = call(esc_model, PROMPTS["v2"], text)
            ep = getattr(req, "category", None) if req is not None and not isinstance(req, dict) else (req or {}).get("category")
            print(f"  {s} {cid} gold={gold} qwen={pred} {esc_model}={ep} ({lat:.0f}s)")
            if st == "ok" and ep and ep != "UNKNOWN": pred = ep
        c += pred == gold; n += 1
    print(f"{s}: {c}/{n} = {c/n:.3f}"); tot_c += c; tot_n += n
print(f"TOTAL {tot_c}/{tot_n} = {tot_c/tot_n:.3f}")
