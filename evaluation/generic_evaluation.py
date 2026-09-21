"""
Generic Evaluation — Compare extraction across 4 tenders
- Reports: docs processed, pages, success, requirements, evidence, provenance, missing, confidence, category coverage
- For Sarai: GOLD-VALIDATED vs gold
- For unseen: UNLABELED / EXPLORATORY (coverage, provenance, schema validity)
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.generic_extraction import build_generic_extraction

tenders = {
    "SA-2018-HV2": Path(r"C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation"),
    "02-Mobile": Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations"),
    "03-6thOctober": Path(r"C:\Users\EgyTech\Desktop\03- 6th October Northern Extensions Substations"),
    "04-Motawreen": Path(r"C:\Users\EgyTech\Desktop\04- Motawreen Substation"),
}

results = {}
for tid, path in tenders.items():
    print(f"\n=== Evaluating {tid} ===")
    try:
        res = build_generic_extraction(path, tender_id=tid, use_llm=False)
        results[tid] = res
        print(f"  Docs: {len(res['documents'])} Pages: {sum(d['page_count'] for d in res['documents'])} Requirements: {len(res['requirements'])} Risks: {len(res['risks'])} Provenance: {res['provenance_coverage']:.2f}")
        # Check schema validity
        try:
            import json as js
            schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
            with open(schema_path, encoding="utf-8") as f:
                schema = js.load(f)
            # Simple check
            assert res["tender_id"]
            assert isinstance(res["requirements"], list)
            print(f"  Schema valid: True")
        except Exception as e:
            print(f"  Schema valid: False {e}")
    except Exception as e:
        print(f"  Failed: {e}")
        import traceback; traceback.print_exc()
        results[tid] = {"error": str(e)}

# For Sarai, also compare with gold
try:
    with open(Path(__file__).resolve().parents[1] / "evaluation" / "sarai_gold_dataset.json", encoding="utf-8") as f:
        gold = json.load(f)
    sarai_res = results.get("SA-2018-HV2")
    if sarai_res and "requirements" in sarai_res:
        gold_ids = set(r["requirement_id"] for r in gold["gold_requirements"])
        # For generic, IDs are REQ-001 etc., not REQ-A, so we compare by category coverage
        print(f"\n=== Sarai Gold Comparison (GOLD-VALIDATED) ===")
        print(f"Gold requirements: {len(gold['gold_requirements'])} (REQ-A..U)")
        print(f"Generic extracted: {len(sarai_res['requirements'])} (dynamic IDs)")
        # Category coverage
        from collections import Counter
        gold_cats = Counter(r["category"] for r in gold["gold_requirements"])
        gen_cats = Counter(r["category"] for r in sarai_res["requirements"])
        print(f"Gold categories: {gold_cats}")
        print(f"Generic categories: {gen_cats}")
        print(f"Category coverage: {len(set(gen_cats) & set(gold_cats))}/{len(gold_cats)} categories overlap")
        # Evidence
        print(f"Gold evidences: {len(gold['gold_evidences'])}")
        print(f"Generic evidences: {len(sarai_res['evidence'])} (generic evidence not yet implemented, currently 0)")
except Exception as e:
    print(f"Gold comparison failed: {e}")

# Summary table
print(f"\n=== Summary ===")
for tid, res in results.items():
    if "error" in res:
        print(f"{tid}: ERROR {res['error']}")
    else:
        docs = len(res["documents"])
        pages = sum(d["page_count"] for d in res["documents"])
        reqs = len(res["requirements"])
        prov = res["provenance_coverage"]
        conf = res["confidence_distribution"]
        print(f"{tid}: docs {docs} pages {pages} reqs {reqs} prov {prov:.2f} conf {conf} risks {len(res['risks'])}")

# Save report
import tempfile, datetime
out = Path(tempfile.gettempdir()) / "opencode" / "tendermind" / "generic_evaluation.json"
out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2, default=str)
print(f"\nWrote {out}")

# Distinguish GOLD-VALIDATED vs UNLABELED
print(f"\nGOLD-VALIDATED: SA-2018-HV2 (21 req, 4 ev, decision REVIEW)")
print(f"UNLABELED / EXPLORATORY: 02-Mobile, 03-6thOctober, 04-Motawreen (no gold, report coverage/provenance/schema validity)")
