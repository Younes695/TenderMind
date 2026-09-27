import sys
sys.stdout.reconfigure(encoding='utf-8', errors='ignore')
from pathlib import Path
import fitz
import openpyxl
import re

def search_tender(path):
    path = Path(path)
    files = [p for p in path.rglob('*') if p.is_file()]
    patterns = {
        'FINANCIAL': r'financial capacity|turnover|working capital|audited',
        'HSE': r'HSE|health.*safety|environment',
        'PERSONNEL': r'personnel|key personnel|project manager|qualified staff',
        'EXPERIENCE': r'experience|reference.*project',
    }
    for f in files:
        if f.suffix.lower() == '.pdf':
            try:
                doc = fitz.open(str(f))
                for i in range(len(doc)):
                    txt = doc[i].get_text()
                    low = txt.lower()
                    for cat, pat in patterns.items():
                        if re.search(pat, low):
                            snippet = txt[max(0, low.find(pat.split('|')[0][:8])-50):low.find(pat.split('|')[0][:8])+100]
                            snippet = snippet.replace('\n', ' ')[:120].encode('ascii', errors='ignore').decode()
                            print(f'{f.name} page {i+1} matches {cat}: snippet: {snippet}')
                            break
                doc.close()
            except Exception as e:
                print(f'Error {f}: {e}')
        elif f.suffix.lower() in ('.txt', '.log'):
            try:
                txt = f.read_text(encoding='utf-8', errors='ignore')
                low = txt.lower()
                for cat, pat in patterns.items():
                    if re.search(pat, low):
                        print(f'{f.name} matches {cat}')
            except: pass
        elif f.suffix.lower() in ('.xlsx', '.xls'):
            try:
                wb = openpyxl.load_workbook(str(f), data_only=True)
                for ws in wb.worksheets:
                    txt = ''
                    for row in ws.iter_rows(values_only=True):
                        if row and any(v is not None for v in row):
                            txt += ' '.join([str(v) for v in row if v is not None]) + ' '
                    low = txt.lower()
                    for cat, pat in patterns.items():
                        if re.search(pat, low):
                            print(f'{f.name} sheet {ws.title} matches {cat}')
            except: pass

search_tender(Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations"))
