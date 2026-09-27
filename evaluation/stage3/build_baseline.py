import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
import fitz

def inventory_tender(path: Path):
    path = Path(path)
    files = [p for p in path.rglob("*") if p.is_file()]
    info = {
        "path": str(path),
        "count": len(files),
        "files": [],
        "total_size_mb": sum(f.stat().st_size for f in files) / 1024 / 1024,
        "languages": set(),
        "has_scan": False,
        "has_text": False,
    }
    for f in files:
        ext = f.suffix.lower()
        size_kb = f.stat().st_size / 1024
        entry = {"name": f.name, "ext": ext, "size_kb": size_kb, "path": str(f)}
        if ext == ".pdf":
            try:
                doc = fitz.open(str(f))
                pages = len(doc)
                # Sample first 2 pages text length
                text_lens = []
                for i in range(min(2, pages)):
                    t = doc[i].get_text()
                    text_lens.append(len(t.strip()))
                    # Check for Arabic
                    if any('\u0600' <= c <= '\u06FF' for c in t):
                        info["languages"].add("AR")
                    if any(c.isalpha() and ord(c) < 128 for c in t):
                        info["languages"].add("EN")
                avg = sum(text_lens)/len(text_lens) if text_lens else 0
                entry["pages"] = pages
                entry["avg_text_len"] = avg
                entry["is_scanned"] = avg < 100
                if avg < 100:
                    info["has_scan"] = True
                else:
                    info["has_text"] = True
                doc.close()
            except Exception as e:
                entry["pages"] = "error"
                entry["error"] = str(e)[:200]
        elif ext in (".txt", ".log", ".xlsx", ".xls"):
            # Check languages via reading
            try:
                if ext in (".txt", ".log"):
                    txt = f.read_text(encoding='utf-8', errors='ignore')
                    if any('\u0600' <= c <= '\u06FF' for c in txt):
                        info["languages"].add("AR")
                    if any(c.isalpha() and ord(c) < 128 for c in txt):
                        info["languages"].add("EN")
                elif ext in (".xlsx", ".xls"):
                    import openpyxl
                    # just mark EN
                    info["languages"].add("EN")
            except: pass
            entry["pages"] = 1
        else:
            entry["pages"] = "N/A (unsupported)"
            if ext in (".dwg", ".bak", ".rar", ".zip", ".jpg", ".jpeg"):
                entry["is_unsupported"] = True
        info["files"].append(entry)
    if not info["languages"]:
        info["languages"] = {"Unknown"}
    return info

tenders = {
    "Mobile (02)": r"C:\Users\EgyTech\Desktop\02- Mobile substations",
    "6th October (03)": r"C:\Users\EgyTech\Desktop\03- 6th October Northern Extensions Substations",
    "Motawreen (04)": r"C:\Users\EgyTech\Desktop\04- Motawreen Substation",
    "Sarai (01) — reference only": r"C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation",
}

for name, p in tenders.items():
    print(f"\n=== {name} ===")
    inv = inventory_tender(Path(p))
    print(f"Path: {inv['path']}")
    print(f"Documents: {inv['count']}")
    print(f"Total size: {inv['total_size_mb']:.1f} MB")
    print(f"Languages detected: {', '.join(inv['languages'])}")
    print(f"Has scanned PDFs needing OCR: {inv['has_scan']}")
    print(f"Has text PDFs: {inv['has_text']}")
    print(f"{'Filename':50} | {'Ext':6} | {'Size KB':8} | {'Pages':6} | {'Avg Text':8} | {'Note'}")
    print("-"*110)
    for f in inv["files"]:
        note = ""
        if f.get("is_scanned"):
            note = "SCANNED -> OCR"
        elif f.get("is_unsupported"):
            note = "UNSUPPORTED"
        elif f.get("pages") == "error":
            note = "ERROR"
        print(f"{f['name'][:50]:50} | {f['ext']:6} | {f['size_kb']:8.1f} | {str(f.get('pages','')):6} | {str(int(f.get('avg_text_len',0))):8} | {note}")

# Also check existing fixtures
print("\n=== Existing Mobile Fixtures ===")
for fp in [Path(r"C:\Users\EgyTech\Desktop\TenderMind\evaluation\fixtures\mobile_llm_sample.json"), Path(r"C:\Users\EgyTech\Desktop\TenderMind\evaluation\gold\mobile_human_gold.json")]:
    if fp.exists():
        import json
        data = json.loads(fp.read_text(encoding='utf-8'))
        if isinstance(data, list):
            print(f"{fp.name}: {len(data)} chunks")
        elif isinstance(data, dict):
            print(f"{fp.name}: {fp} — tender_id {data.get('tender_id')}, gold_reqs {len(data.get('gold_requirements',[]))}")

