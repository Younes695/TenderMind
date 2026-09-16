# Tesseract Local OCR — TenderMind — $0, Offline

**Validated 2026-09-16 on real Sarai tender `C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation` (34 PDFs, 1354 pages).**

## Setup (Windows, verified)
- **Tesseract 5.4.0** at `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Languages: `ara`, `eng`, `osd` (`tesseract --list-langs`)
- Python: `pytesseract 0.3.13`, `Pillow`, `pymupdf` (fitz)
- No PATH required — code sets `pytesseract.pytesseract.tesseract_cmd` explicitly.

**Install (if not present):**
```powershell
winget install --id UB-Mannheim.TesseractOCR -e
Invoke-WebRequest -Uri https://github.com/tesseract-ocr/tessdata/raw/main/ara.traineddata -OutFile "C:\Program Files\Tesseract-OCR\tessdata\ara.traineddata"
tesseract --version
tesseract --list-langs  # must show ara, eng
```

## Module
`evaluation/tesseract_local_ocr.py` — local replacement for `evaluation/azure_doc_intel.py`:
- `is_scanned_or_garbled()` mirrors `azure_doc_intel.py:228` (`len<100 or garbled>0.3`)
- `ocr_page_with_tesseract(pdf_path, page_number, dpi=300, lang="ara+eng")` → `{source_filename, source_page_number, text, confidence, ocr_applied, method}` with `--psm 6 --oem 1`, fallback dpi 200/150 for large drawings (>120M px).
- `extract_pdf_with_tesseract_routing(pdf_path)` — only OCRs scanned/garbled pages, keeps native text otherwise, preserves `source_page_number` provenance.

## Benchmark Results (measurement only)
- **Full tender:** 1354 pages, 946 routed to Tesseract, 408 kept native, 0 failures, `total 7919.6s avg 8.37s median 7.91s avg_conf 0.786`, 807 Arabic pages, `page_number_accuracy 1.0` — saved to `C:\Users\EgyTech\AppData\Local\Temp\opencode\tendermind\tesseract_full\tesseract_full.json` (excluded from git via `.gitignore`).
- **Smoke (3 pages):** Sarai RFP p1 `len 3106 conf 0.89 Arabic True`, Part 1 p1 `len 166 conf 0.76`, volume p4 `len 30 conf 0.93` — all with provenance.
- **Requirement extraction (full Tesseract):** 19/21 `F1 0.950` (missing `REQ-L`, `REQ-S`), `page provenance 1.0` (was 0.48), REQ-A now correctly `Sarai RFP.pdf Page 2` via OCR `first category` (was `FORM D.xls`).
- **HybridMatcher comparison:** 84 pairs `macro 0.638` (was 0.245 baseline), `evidence-supported 0.727`, `LLM calls 6/84 7.1%`, `MISSING→REVIEW 2` (was 72) — gate fixes over-prediction, not OCR directly.

## Usage
```python
from evaluation.tesseract_local_ocr import extract_pdf_with_tesseract_routing
from pathlib import Path
pages = extract_pdf_with_tesseract_routing(Path(r"C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation\Part 1 of 2.pdf"))
# pages[0] -> {source_filename, source_page_number, text, confidence, ocr_applied, method}
```

## Cost
$0 — localhost Tesseract only, no Azure/OpenAI, no paid APIs. Full OCR corpora and benchmark JSONs stay in `Temp` and are git-ignored per `.gitignore:69-77`.

## See Also
- `evaluation/azure_doc_intel.py` — Azure wrapper (kept, not used in $0 mode)
- `evaluation/run_real_benchmark_v4.py:30` — Azure routing logic mirrored here
- `docs/AI_Evaluation_Contract_v1.md`, `docs/AI_Acceptance_Criteria.md`
