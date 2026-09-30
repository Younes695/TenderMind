"""Stage 5E — extraction for images, archives (ZIP/RAR/7z), CAD and .bak files.

Before this, anything that was not PDF / Word / Excel / TXT was marked
UNSUPPORTED: scanned images, the RAR/ZIP packages tenders are often shipped
in, CAD drawings and AutoCAD ".bak" backups.

- Images (.jpg .jpeg .png .bmp .gif .tif .tiff .webp): Tesseract OCR,
  Arabic + English when installed; every TIFF/GIF frame is a page.
- Archives (.zip .rar .7z): extracted to a private temp folder (path-traversal
  and size/count limits enforced), every inner file is extracted with the same
  rules, nested archives up to MAX_DEPTH. Provenance keeps the inner path:
  "Tender document.rar/Vol 1.pdf" page 12.
- CAD: .dxf text (TEXT / MTEXT / ATTRIB) is read directly. .dwg needs the free
  ODA File Converter on the server (TENDERMIND_ODA_CONVERTER); without it the
  file is reported UNSUPPORTED with that exact reason.
- ".bak" and unknown extensions: the real type is detected from the file's
  first bytes (a .bak is a backup of *something* — PDF, DWG, ZIP, ...).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z"}
CAD_EXTS = {".dwg", ".dxf"}
TEXT_EXTS = {".txt", ".log", ".csv", ".md"}
# Detected by content: backups keep the original data under a generic name.
BACKUP_EXTS = {".bak", ".old", ".backup", ".bk", ""}

MAX_DEPTH = 2                      # archive inside archive inside archive: stop
MAX_ARCHIVE_FILES = 2000
MAX_ARCHIVE_BYTES = 20 * 1024 ** 3  # uncompressed, per top-level archive
MAX_IMAGE_FRAMES = 300
ARCHIVE_TIMEOUT_S = 1800

Entry = Tuple[str, Dict[str, Any]]  # (display name, doc_results entry)


# ------------------------------------------------------------------ detection
def sniff(path: Path) -> str:
    """Real type from magic bytes: pdf, zip, docx, xlsx, rar, 7z, dwg, dxf,
    image, ole, text or unknown."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return "unknown"
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"Rar!\x1a\x07"):
        return "rar"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7z"
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06"):
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            if any(n.startswith("word/") for n in names):
                return "docx"
            if any(n.startswith("xl/") for n in names):
                return "xlsx"
        except zipfile.BadZipFile:
            return "unknown"
        return "zip"
    if re.match(rb"AC10\d\d", head[:6]):
        return "dwg"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "ole"  # legacy .doc / .xls
    if (head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG") or head[:6] in (b"GIF87a", b"GIF89a")
            or head.startswith(b"BM") or head[:4] in (b"II*\x00", b"MM\x00*")
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")):
        return "image"
    sample = head.lstrip()
    if sample.startswith(b"0\r\nSECTION") or sample.startswith(b"0\nSECTION") or b"\nSECTION" in head[:200]:
        return "dxf"
    try:
        head.decode("utf-8")
        printable = sum(32 <= b < 127 or b in (9, 10, 13) for b in head) / max(len(head), 1)
        if printable > 0.9:
            return "text"
    except UnicodeDecodeError:
        pass
    return "unknown"


def kind_for(path: Path) -> str:
    """Extraction kind for a file: by extension, or by content for .bak/unknown."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".doc", ".docx"):
        return "doc"
    if ext in (".xls", ".xlsx"):
        return "xls"
    if ext in TEXT_EXTS:
        return "text"
    # Binary containers must really be what their name says (a renamed text
    # file called ".rar" is not an archive).
    if ext in IMAGE_EXTS:
        return "image" if sniff(path) == "image" else "unknown"
    if ext == ".zip":
        return "zip" if sniff(path) in ("zip", "docx", "xlsx") else "unknown"
    if ext in (".rar", ".7z"):
        return ext[1:] if sniff(path) == ext[1:] else "unknown"
    if ext == ".dxf":
        return "dxf"
    if ext == ".dwg":
        return "dwg"
    if ext in BACKUP_EXTS:
        # A backup of *something*: the real type is in the content.
        s = sniff(path)
        return {"docx": "doc", "xlsx": "xls", "ole": "doc"}.get(s, s)
    return "unknown"


def upload_doc_type(path: Path) -> str:
    """doc_type shown at upload time (UNSUPPORTED only when we really can't read it)."""
    k = kind_for(path)
    if k == "dwg" and not oda_converter():
        return "UNSUPPORTED"
    return {"pdf": "PDF", "doc": "DOC", "xls": "XLS", "text": "TXT", "image": "IMAGE",
            "zip": "ARCHIVE", "rar": "ARCHIVE", "7z": "ARCHIVE", "dxf": "CAD", "dwg": "CAD"}.get(k, "UNSUPPORTED")


# ----------------------------------------------------------------- tool lookup
def _first_existing(candidates: List[Optional[str]]) -> Optional[str]:
    for c in candidates:
        if c and (Path(c).is_file() or shutil.which(c)):
            return shutil.which(c) or c
    return None


def unrar_tool() -> Optional[Tuple[str, str]]:
    """(kind, executable) able to extract RAR: unrar, 7z or bsdtar."""
    pf = os.environ.get("ProgramFiles")  # Windows only; never a literal path
    exe = _first_existing([os.environ.get("TENDERMIND_UNRAR_PATH"), "unrar",
                           str(Path(pf) / "WinRAR" / "UnRAR.exe") if pf else None])
    if exe:
        return "unrar", exe
    exe = _first_existing([os.environ.get("TENDERMIND_7Z_PATH"), "7z", "7za",
                           str(Path(pf) / "7-Zip" / "7z.exe") if pf else None])
    if exe:
        return "7z", exe
    sysroot = os.environ.get("SystemRoot")
    exe = _first_existing(["bsdtar", os.path.join(sysroot, "System32", "tar.exe") if sysroot else None])
    if exe:
        return "bsdtar", exe
    return None


def oda_converter() -> Optional[str]:
    env = os.environ.get("TENDERMIND_ODA_CONVERTER")
    if env and (Path(env).is_file() or shutil.which(env)):
        return shutil.which(env) or env
    pf = os.environ.get("ProgramFiles")
    if pf:
        for c in sorted(Path(pf).glob("ODA/ODAFileConverter*/ODAFileConverter.exe"), reverse=True):
            return str(c)
    return shutil.which("ODAFileConverter")


# ------------------------------------------------------------------ extractors
def _entry(pages: List[Dict[str, Any]], status: Optional[str] = None, error: Optional[str] = None) -> Dict[str, Any]:
    chars = sum(len(p.get("text", "")) for p in pages)
    if status is None:
        if chars > 50:
            status = "COMPLETE"
        elif not pages or any(str(p.get("method", "")).startswith("scanned") for p in pages):
            status = "FAILED"  # scanned pages that OCR could not read
        else:
            status = "PARTIAL"
    e = {"pages": pages, "page_count": len(pages), "total_text_chars": chars, "status": status}
    if error:
        e["error"] = error
    return e


def extract_image(path: Path) -> List[Dict[str, Any]]:
    import pytesseract
    from PIL import Image, ImageSequence
    from evaluation.tesseract_local_ocr import _resolve_tesseract_cmd
    pytesseract.pytesseract.tesseract_cmd = _resolve_tesseract_cmd()
    try:
        langs = set(pytesseract.get_languages(config=""))
    except Exception:
        langs = {"eng"}
    lang = "+".join(l for l in ("ara", "eng") if l in langs) or "eng"
    Image.MAX_IMAGE_PIXELS = 400_000_000  # large scanned drawings are legitimate
    pages = []
    with Image.open(path) as img:
        for i, frame in enumerate(ImageSequence.Iterator(img)):
            if i >= MAX_IMAGE_FRAMES:
                break
            fr = frame.convert("RGB")
            if min(fr.size) < 1000:  # small scans OCR much better upscaled
                scale = 1000 / max(min(fr.size), 1)
                fr = fr.resize((int(fr.width * scale), int(fr.height * scale)))
            text = pytesseract.image_to_string(fr, lang=lang)
            pages.append({"page_number": i + 1, "text": text, "method": f"tesseract_image_{lang}",
                          "ocr_applied": True})
    return pages


def extract_dxf(path: Path) -> List[Dict[str, Any]]:
    """Text entities from an ASCII DXF (TEXT, MTEXT, ATTRIB, ATTDEF)."""
    raw = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    texts: List[str] = []
    entity, buf = None, []
    for i in range(0, len(raw) - 1, 2):
        code, value = raw[i].strip(), raw[i + 1]
        if code == "0":
            if entity in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF") and buf:
                texts.append("".join(buf))
            entity, buf = value.strip(), []
        elif entity in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF") and code in ("1", "3"):
            buf.append(value)
    if entity in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF") and buf:
        texts.append("".join(buf))
    # strip MTEXT formatting codes like \P (new paragraph) and {\fArial;...}
    clean = [re.sub(r"\\[A-Za-z][^;\\]*;|[{}]", "", t).replace("\\P", "\n").strip() for t in texts]
    body = "\n".join(t for t in clean if t)
    return [{"page_number": 1, "text": body, "method": "dxf_text", "ocr_applied": False}] if body else []


def extract_dwg(path: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    conv = oda_converter()
    if not conv:
        return [], ("AutoCAD drawing (DWG): text extraction needs the free ODA File Converter "
                    "on the server (set TENDERMIND_ODA_CONVERTER)")
    with tempfile.TemporaryDirectory(prefix="tm_dwg_") as tmp:
        src, out = Path(tmp) / "in", Path(tmp) / "out"
        src.mkdir()
        out.mkdir()
        shutil.copy(path, src / (path.stem + ".dwg"))  # .bak -> .dwg so the converter accepts it
        # ODAFileConverter <in dir> <out dir> <version> <type> <recurse> <audit>
        subprocess.run([conv, str(src), str(out), "ACAD2018", "DXF", "0", "1"],
                       capture_output=True, timeout=600, check=False)
        dxfs = list(out.glob("*.dxf"))
        if not dxfs:
            return [], "DWG conversion produced no DXF"
        return extract_dxf(dxfs[0]), None


def _safe_members_zip(z: zipfile.ZipFile, dest: Path) -> None:
    total = 0
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > MAX_ARCHIVE_FILES:
        raise ValueError(f"archive has {len(infos)} files (limit {MAX_ARCHIVE_FILES})")
    root = dest.resolve()
    for info in infos:
        total += info.file_size
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError("archive expands beyond the size limit")
        target = (dest / info.filename).resolve()
        if root not in target.parents:
            raise ValueError(f"unsafe path in archive: {info.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out, 8 * 1024 * 1024)


def _extract_archive(path: Path, kind: str, dest: Path) -> None:
    if kind == "zip":
        with zipfile.ZipFile(path) as z:
            _safe_members_zip(z, dest)
        return
    tool = unrar_tool() if kind == "rar" else None
    if kind == "7z":
        pf = os.environ.get("ProgramFiles")
        exe = _first_existing([os.environ.get("TENDERMIND_7Z_PATH"), "7z", "7za",
                               str(Path(pf) / "7-Zip" / "7z.exe") if pf else None])
        tool = ("7z", exe) if exe else None
        if tool is None:  # libarchive's bsdtar reads 7z too (Linux images)
            bsd = _first_existing(["bsdtar"])
            tool = ("bsdtar", bsd) if bsd else None
    if not tool:
        raise RuntimeError(f"no {kind.upper()} extractor on the server (install unrar, 7-Zip or bsdtar)")
    name, exe = tool
    if name == "unrar":
        cmd = [exe, "x", "-y", "-o+", "-inul", str(path), str(dest) + os.sep]
    elif name == "7z":
        cmd = [exe, "x", "-y", f"-o{dest}", str(path)]
    else:
        cmd = [exe, "-xf", str(path), "-C", str(dest)]
    r = subprocess.run(cmd, capture_output=True, timeout=ARCHIVE_TIMEOUT_S, check=False)
    if r.returncode not in (0, 1):  # unrar: 1 = warnings
        raise RuntimeError(f"{name} failed (exit {r.returncode}): {r.stderr[:200]!r}")
    # The tools refuse "../" paths themselves; verify anyway and enforce limits.
    root = dest.resolve()
    files = [p for p in dest.rglob("*") if p.is_file()]
    if len(files) > MAX_ARCHIVE_FILES:
        raise ValueError(f"archive has {len(files)} files (limit {MAX_ARCHIVE_FILES})")
    if sum(p.stat().st_size for p in files) > MAX_ARCHIVE_BYTES:
        raise ValueError("archive expands beyond the size limit")
    for p in files:
        if root not in p.resolve().parents:
            raise ValueError(f"unsafe path in archive: {p}")


def extract_any(path: Path, name: str, pdf_extractor: Callable, depth: int = 0,
                pdf_hint: Optional[bool] = None) -> List[Entry]:
    """Extract one file. Archives return one entry per inner file."""
    kind = kind_for(path)
    try:
        if kind == "pdf":
            return [(name, _entry(pdf_extractor(path, pdf_hint)))]
        if kind == "doc":
            from evaluation.run_real_benchmark import extract_docx_text
            return [(name, _entry(extract_docx_text(str(path))))]
        if kind == "xls":
            from evaluation.run_real_benchmark import extract_xls_text
            return [(name, _entry(extract_xls_text(str(path))))]
        if kind == "text":
            text = path.read_text(encoding="utf-8", errors="ignore")
            return [(name, _entry([{"page_number": 1, "text": text, "method": "txt", "ocr_applied": False}]))]
        if kind == "image":
            return [(name, _entry(extract_image(path)))]
        if kind == "dxf":
            return [(name, _entry(extract_dxf(path)))]
        if kind == "dwg":
            pages, why = extract_dwg(path)
            return [(name, _entry(pages) if pages else _entry([], "UNSUPPORTED", why))]
        if kind in ("zip", "rar", "7z"):
            if depth >= MAX_DEPTH:
                return [(name, _entry([], "UNSUPPORTED", "archive nested too deeply"))]
            out: List[Entry] = []
            with tempfile.TemporaryDirectory(prefix="tm_arc_") as tmp:
                dest = Path(tmp)
                _extract_archive(path, kind, dest)
                inner = sorted(p for p in dest.rglob("*") if p.is_file())
                if not inner:
                    return [(name, _entry([], "FAILED", "archive is empty"))]
                for p in inner:
                    rel = p.relative_to(dest).as_posix()
                    out.extend(extract_any(p, f"{name}/{rel}", pdf_extractor, depth + 1))
            return out
        return [(name, _entry([], "UNSUPPORTED", f"file type not recognised ({path.suffix or 'no extension'})"))]
    except Exception as e:  # one bad file never stops the others
        return [(name, _entry([], "FAILED", f"{type(e).__name__}: {e}"[:200]))]
