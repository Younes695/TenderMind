"""
Local Tesseract OCR — TenderMind — $0, offline, no Azure/OpenAI
- Validated on 2026-09-16 with 1354 pages (946 OCR, avg_conf 0.786, 807 Arabic, 0 failures)
- pytesseract 0.3.13, lang="ara+eng", --psm 6 --oem 1, dpi 300 (fallback 200/150 for >120M px drawings)
- Tesseract binary resolved cross-platform: env var override, then PATH lookup, then common
  Windows/Linux/macOS install locations. Was hardcoded to a Windows-only path, which meant
  every OCR-routed page (any scanned page, or any page under ~100 chars of native text —
  see is_scanned_or_garbled) silently failed on Linux with TesseractNotFoundError and
  returned empty text, i.e. build_generic_extraction() could return 0 requirements for a
  perfectly valid tender document with no visible error anywhere in the pipeline.
- Reuses is_scanned_or_garbled() from evaluation/azure_doc_intel.py:228
- Preserves provenance: source_filename, source_page_number, text, confidence, ocr_applied, method
- No paid APIs, localhost only
"""
import io
import os
import shutil
import time
import warnings
from pathlib import Path
from typing import List, Dict, Any, Optional

import fitz
import pytesseract
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
warnings.filterwarnings("ignore")


def _resolve_tesseract_cmd() -> str:
    """Cross-platform tesseract binary resolution — mirrors the pattern already used
    for LibreOffice in evaluation/run_real_benchmark.py:_find_soffice_executable.
    1. Explicit env var override (works on any OS/container image).
    2. PATH lookup via shutil.which (covers Linux/macOS `apt/brew install tesseract-ocr`).
    3. Common fixed install locations (Windows dev boxes, Homebrew default).
    4. Fall back to the bare command name — lets pytesseract raise its own clear
       TesseractNotFoundError instead of silently pointing at a path that can't exist
       on this OS.
    """
    for env_key in ("TENDERMIND_TESSERACT_PATH", "TESSERACT_PATH", "TESSERACT_CMD"):
        env_val = os.environ.get(env_key)
        if env_val and Path(env_val).is_file():
            return env_val
    found = shutil.which("tesseract")
    if found:
        return found
    for cand in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/opt/homebrew/bin/tesseract",
    ):
        if Path(cand).is_file():
            return cand
    return "tesseract"


pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract_cmd()

TESS_LANG = "ara+eng"
TESS_CONFIG = "--psm 6 --oem 1"
DPI = 300
METHOD_TESS = "tesseract_5.4.0_ara+eng_psm6_dpi300"
METHOD_NATIVE = "fitz_direct_native"


def is_scanned_or_garbled(page_text: str, garbled_ratio: float) -> bool:
    """Mirrors evaluation/azure_doc_intel.py:228 — len<100 or garbled>0.3"""
    l = len((page_text or "").strip())
    return l < 100 or garbled_ratio > 0.3


def ocr_png_text_and_confidence(png_bytes: bytes, lang: str = TESS_LANG, config: str = TESS_CONFIG):
    """One Tesseract run -> (text, mean word confidence 0..1 or None).

    Text and confidence used to come from two full OCR passes (image_to_string +
    image_to_data), doubling the time of every scanned page. Tesseract writes
    both outputs from one pass when given the `txt` and `tsv` configs. The text
    is byte-for-byte what image_to_string returned (same engine, same config).
    """
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory(prefix="tm_ocr_") as tmp:
        src = os.path.join(tmp, "page.png")
        base = os.path.join(tmp, "out")
        with open(src, "wb") as fh:
            fh.write(png_bytes)
        cmd = [pytesseract.pytesseract.tesseract_cmd, src, base, "-l", lang, *config.split(), "txt", "tsv"]
        env = dict(os.environ)
        # Pages run in parallel (one process each); stop each one from also
        # spawning a thread per core.
        env.setdefault("OMP_THREAD_LIMIT", "1")
        proc = subprocess.run(cmd, capture_output=True, env=env,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if proc.returncode != 0:
            raise RuntimeError(f"tesseract failed ({proc.returncode}): {proc.stderr[:300]!r}")
        with open(base + ".txt", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        confs = []
        try:
            with open(base + ".tsv", encoding="utf-8", errors="replace") as fh:
                header = fh.readline().rstrip("\n").split("\t")
                ci = header.index("conf")
                for line in fh:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) > ci:
                        try:
                            c = float(parts[ci])
                        except ValueError:
                            continue
                        if c >= 0:
                            confs.append(c)
        except (OSError, ValueError):
            confs = []
    return text, (sum(confs) / len(confs) / 100.0) if confs else None


def ocr_page_with_tesseract(pdf_path: Path, page_number: int, dpi: int = DPI, lang: str = TESS_LANG) -> Dict[str, Any]:
    """OCR a single PDF page via Tesseract, preserving provenance."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_number - 1]
    # Handle large drawings (139M px) — fallback dpi
    pix = None
    dpi_to_try = dpi
    method_used = METHOD_TESS
    for try_dpi in [300, 200, 150]:
        try:
            pix = page.get_pixmap(dpi=try_dpi)
            if pix.width * pix.height > 120_000_000:
                pix = None
                continue
            dpi_to_try = try_dpi
            method_used = f"tesseract_5.4.0_ara+eng_psm6_dpi{try_dpi}" if try_dpi != 300 else METHOD_TESS
            break
        except Exception:
            pix = None
            continue
    if pix is None:
        doc.close()
        raise RuntimeError(f"Could not render page {page_number} at any dpi")
    img_bytes = pix.tobytes("png")
    t0 = time.time()
    text, conf_norm = ocr_png_text_and_confidence(img_bytes, lang=lang, config=TESS_CONFIG)
    elapsed = time.time() - t0
    doc.close()
    return {
        "source_filename": str(pdf_path),
        "source_page_number": page_number,
        "text": text,
        "confidence": conf_norm,
        "ocr_applied": True,
        "method": method_used,
        "lang": lang,
        "config": TESS_CONFIG,
        "dpi": dpi_to_try,
        "ocr_time": elapsed,
    }


def ocr_workers() -> int:
    """Scanned pages OCR'd at the same time (TENDERMIND_OCR_WORKERS, default: cores - 2, max 6)."""
    raw = os.environ.get("TENDERMIND_OCR_WORKERS", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return max(1, min(6, (os.cpu_count() or 2) - 2))


def tesseract_available() -> bool:
    cmd = str(pytesseract.pytesseract.tesseract_cmd or "")
    return bool(cmd) and (Path(cmd).is_file() or shutil.which(cmd) is not None)


def _unread_page(pdf_path: Path, i: int, garbled: float, native_text: str, unread: bool,
                 method: str, why: str) -> Dict[str, Any]:
    """OCR did not read this page. Its text layer is kept when usable (it used to
    be dropped, so a short page lost the text it had). The page counts as unread
    ("error") when page_content_unread() said so: an image the text layer may not
    cover, a broken text layer, or drawings with no text. A short page whose text
    is all it holds, or a blank page, was read."""
    usable = bool((native_text or "").strip()) and garbled <= 0.3
    page = {
        "source_filename": str(pdf_path),
        "source_page_number": i + 1,
        "text": native_text if usable else "",
        "confidence": None,
        "ocr_applied": unread and not usable,  # kept text is the native layer, not OCR
        "method": method,
        "ocr_error": why[:500],
        "garbled_ratio": garbled,
    }
    if unread:
        page["error"] = why[:500]
    return page


def _unread_verdict(page, text: str, garbled: float) -> bool:
    """page_content_unread, and 'unread' when it cannot tell (a page MuPDF chokes on)."""
    from app.pipeline.file_extractors import page_content_unread
    try:
        return page_content_unread(page, text, garbled)
    except Exception:
        return True


def _ocr_scanned_page(pdf_path: Path, i: int, garbled: float, native_len: int,
                      native_text: str = "", unread: Optional[bool] = None) -> Dict[str, Any]:
    try:
        ocr_res = ocr_page_with_tesseract(pdf_path, i + 1)
        ocr_res["garbled_ratio"] = garbled
        ocr_res["native_len"] = native_len
        ocr_res["is_scanned"] = True
        return ocr_res
    except Exception as e:
        if unread is None:  # decided only now: most pages OCR fine and never need it
            try:
                with fitz.open(str(pdf_path)) as d:
                    unread = _unread_verdict(d[i], native_text, garbled)
            except Exception:
                unread = True
        return _unread_page(pdf_path, i, garbled, native_text, unread,
                            f"{METHOD_TESS}_failed_{type(e).__name__}", str(e))


def extract_pdf_with_tesseract_routing(pdf_path: Path) -> List[Dict[str, Any]]:
    """
    Scanned-page routing — mirrors evaluation/run_real_benchmark_v4.py:30 extract_pdf_with_azure_routing
    but swaps Azure for local Tesseract. Only routes scanned/garbled pages to OCR.

    Scanned pages are OCR'd in parallel (one Tesseract process each, see
    ocr_workers()); the result keeps page order. A 1,530-page tender with 285
    scanned pages used to OCR them one at a time on one core.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ocr_ok = tesseract_available()
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    pages: List[Any] = [None] * total
    scanned = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        l = len(text.strip())
        garbled = text.count("�") / max(len(text), 1) if text else 0
        if "�" in text:
            garbled = max(garbled, text.count("�") / max(len(text), 1))
        if is_scanned_or_garbled(text, garbled):
            # Whether the page holds unread content matters only if OCR does not read it.
            scanned.append((i, garbled, l, text, None if ocr_ok else _unread_verdict(page, text, garbled)))
            continue
        pages[i] = {
            "source_filename": str(pdf_path),
            "source_page_number": i + 1,
            "text": text,
            "confidence": 0.95 if l > 100 and garbled < 0.1 else 0.7,
            "ocr_applied": False,
            "method": METHOD_NATIVE,
            "garbled_ratio": garbled,
        }
    doc.close()
    done = total - len(scanned)
    if done:
        _report_page(done, total)
    if scanned and not ocr_ok:
        # Rendering a page for an OCR engine that is not there only burns time:
        # the Turaif tender spent ~5 of its 5.5 extraction minutes on this.
        for i, g, l, txt, unread in scanned:
            pages[i] = _unread_page(pdf_path, i, g, txt, unread, f"{METHOD_TESS}_unavailable",
                                    "OCR not available: Tesseract is not installed on this server")
        _report_page(total, total)
        return pages
    workers = min(ocr_workers(), len(scanned)) or 1
    if workers == 1:
        for i, garbled, l, txt, unread in scanned:
            pages[i] = _ocr_scanned_page(pdf_path, i, garbled, l, txt, unread)
            done += 1
            _report_page(done, total)
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_ocr_scanned_page, pdf_path, i, g, l, txt, u): i for i, g, l, txt, u in scanned}
            # Collected on this thread so the job's progress listener sees each page.
            for fut in as_completed(futs):
                pages[futs[fut]] = fut.result()
                done += 1
                _report_page(done, total)
    return pages


def _report_page(done: int, total: int) -> None:
    """Live per-page progress for the processing job (no-op outside the app)."""
    try:
        from app.pipeline.progress import report
    except ImportError:
        return
    report("pages", done, total)
