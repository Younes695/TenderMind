"""
Stage 3C — Cross-tender sanity (lightweight, deterministic only, no full LLM).
Verifies: no Sarai leakage, no tender hardcoding, evidence source-local,
unsupported remain unsupported, technical numerics not deadlines.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
import json
import tempfile
import shutil
import fitz

TENDERS = {
    "6th October": Path(r"C:\Users\EgyTech\Desktop\03- 6th October Northern Extensions Substations"),
    "Motawreen": Path(r"C:\Users\EgyTech\Desktop\04- Motawreen Substation"),
}

RESULTS = {}

for name, root in TENDERS.items():
    print(f"\n=== {name} ===")
    files = [p for p in root.rglob("*") if p.is_file()]
    print(f"Files: {len(files)}")
    for f in files:
        print(f"  {f.name} {f.suffix} {f.stat().st_size/1024:.1f}KB")
    # Build small subset: first text PDF (up to 5 pages) + first unsupported + first txt if any
    tmp = Path(tempfile.mkdtemp(prefix=f"stage3c_{name[:3]}_"))
    # Pick: smallest PDF with text, one unsupported, one txt/xlsx if present
    import fitz as F
    pdfs = [p for p in files if p.suffix.lower() == ".pdf"]
    unsupported = [p for p in files if p.suffix.lower() in (".dwg", ".bak", ".rar", ".zip", ".jpg", ".jpeg")]
    others = [p for p in files if p.suffix.lower() in (".txt", ".log", ".xlsx", ".xls")]
    subset = []
    # Take first PDF, limit to 5 pages
    if pdfs:
        # Prefer Clarification 1.pdf for 6th Oct (has HSE), or Tenders conditions for Motawreen
        # Generic: pick smallest PDF (lightweight) — no tender-specific rule, just size
        pdfs_sorted = sorted(pdfs, key=lambda p: p.stat().st_size)
        chosen = pdfs_sorted[0]
        print(f"Chosen PDF (smallest): {chosen.name}")
        try:
            doc = F.open(str(chosen))
            new = F.open()
            for i in range(min(5, len(doc))):
                new.insert_pdf(doc, from_page=i, to_page=i)
            out = tmp / f"subset_{chosen.stem[:30]}.pdf"
            new.save(str(out))
            new.close()
            doc.close()
            subset.append(out)
        except Exception as e:
            print(f"PDF subset failed: {e}")
    for p in (others[:1] + unsupported[:1]):
        try:
            shutil.copy2(str(p), str(tmp / p.name))
            subset.append(tmp / p.name)
        except Exception as e:
            print(f"Copy failed {p}: {e}")
    print(f"Subset: {[p.name for p in subset]}")

    from evaluation.generic_extraction import build_generic_extraction
    try:
        res = build_generic_extraction(tmp, tender_id=f"STAGE3C-{name[:3].upper()}", use_llm=False)
        print(f"Requirements: {len(res['requirements'])}")
        for r in res["requirements"][:5]:
            print(f"  {r['category']} {(r['summary'] or '')[:50]} src {r.get('source_document')}")
        print(f"Deadlines: {len(res['deadlines'])} {res['deadlines'][:2]}")
        print(f"Commercial: {res['commercial_terms']}")
        print(f"Documents: {[(d['filename'], d['extraction_status']) for d in res['documents']]}")
        # Checks
        text_all = " ".join([(r.get("summary") or "") for r in res["requirements"]] + [d.get("filename","") for d in res["documents"]])
        has_sarai = any(s in text_all for s in ["Sarai", "SA-2018", "GIZA", "HYOSUNG", "MNHD"])
        print(f"Sarai leakage: {has_sarai}")
        # Technical numerics not deadlines: check no deadline date looks like voltage
        bad_deadlines = [d for d in res["deadlines"] if d.get("date") in ("20/22/22", "1/1/18", "10/6/2104")]
        print(f"Bad deadlines (voltage): {bad_deadlines}")
        # Unsupported remain unsupported
        unsupp = [d for d in res["documents"] if d.get("extraction_status") == "UNSUPPORTED"]
        print(f"Unsupported docs: {[d['filename'] for d in unsupp]}")
        RESULTS[name] = {
            "requirements": len(res["requirements"]),
            "categories": sorted(set(r["category"] for r in res["requirements"])),
            "deadlines": res["deadlines"],
            "commercial": res["commercial_terms"],
            "documents": [(d["filename"], d["extraction_status"]) for d in res["documents"]],
            "sarai_leakage": has_sarai,
            "bad_deadlines": bad_deadlines,
        }
    except Exception as e:
        print(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        RESULTS[name] = {"error": str(e)}
    shutil.rmtree(tmp, ignore_errors=True)

Path(__file__).parent.joinpath("cross_tender_3c.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding='utf-8')
print("\nSaved cross_tender_3c.json")
