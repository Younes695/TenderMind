"""Stage 4A — format-specific extraction layer (audit + policy, pure functions).

No behavior change: classifies by extension and documents the mandated tool per
format, mirroring the current production behavior in
evaluation/run_real_benchmark.py + app/processing.py.

Policy (load-bearing):
- Text PDF -> direct fitz extraction. NEVER force OCR on text PDFs.
- Scanned/garbled PDF -> local Tesseract routing (ara+eng). Azure/Sarai OCR is
  offline-evaluation only and must never run in the production path.
- Arabic/English/mixed -> source text preserved verbatim (utf-8, errors ignored).
- Tiny/empty/OCR-garbage -> explicit FAILED / PARTIAL / UNSUPPORTED, never silent.
- Images, archives, CAD and unknown binaries -> UNSUPPORTED (truthful, counted).
"""
from __future__ import annotations

from enum import Enum
from typing import Dict


class FormatKind(str, Enum):
    PDF = "PDF"
    DOC = "DOC"
    DOCX = "DOCX"
    XLS = "XLS"
    XLSX = "XLSX"
    TXT = "TXT"
    CSV = "CSV"
    LOG = "LOG"
    IMAGE = "IMAGE"
    ARCHIVE = "ARCHIVE"
    CAD = "CAD"
    UNSUPPORTED = "UNSUPPORTED"


_EXTENSION_MAP: Dict[str, FormatKind] = {
    ".pdf": FormatKind.PDF,
    ".doc": FormatKind.DOC,
    ".docx": FormatKind.DOCX,
    ".xls": FormatKind.XLS,
    ".xlsx": FormatKind.XLSX,
    ".txt": FormatKind.TXT,
    ".csv": FormatKind.CSV,
    ".log": FormatKind.LOG,
    ".png": FormatKind.IMAGE,
    ".jpg": FormatKind.IMAGE,
    ".jpeg": FormatKind.IMAGE,
    ".tif": FormatKind.IMAGE,
    ".tiff": FormatKind.IMAGE,
    ".bmp": FormatKind.IMAGE,
    ".zip": FormatKind.ARCHIVE,
    ".rar": FormatKind.ARCHIVE,
    ".7z": FormatKind.ARCHIVE,
    ".dwg": FormatKind.CAD,
    ".dxf": FormatKind.CAD,
}

# Mandated tool per format (documents current behavior; the runner modules own it).
FORMAT_TOOL: Dict[FormatKind, str] = {
    FormatKind.PDF: "pymupdf-fitz-direct + local-tesseract-routing-if-scanned",
    FormatKind.DOC: "libreoffice-headless-to-txt, fallback olefile WordDocument stream",
    FormatKind.DOCX: "python-docx paragraphs",
    FormatKind.XLS: "xlrd, first 50 rows/sheet, |-joined",
    FormatKind.XLSX: "openpyxl data_only, all sheets, |-joined, 5000-char cap/sheet",
    FormatKind.TXT: "utf-8 read, errors ignored",
    FormatKind.CSV: "utf-8 read, errors ignored",
    FormatKind.LOG: "utf-8 read, errors ignored",
    FormatKind.IMAGE: "unsupported: image-only input has no production extractor",
    FormatKind.ARCHIVE: "unsupported: archives are not traversed",
    FormatKind.CAD: "unsupported: no CAD extractor",
    FormatKind.UNSUPPORTED: "unsupported binary",
}

# Formats the production pipeline extracts (everything else -> UNSUPPORTED).
EXTRACTABLE = frozenset({
    FormatKind.PDF, FormatKind.DOC, FormatKind.DOCX,
    FormatKind.XLS, FormatKind.XLSX,
    FormatKind.TXT, FormatKind.CSV, FormatKind.LOG,
})


def classify_format(filename: str) -> FormatKind:
    """Pure extension classification. Unknown/missing extension -> UNSUPPORTED."""
    name = (filename or "").lower()
    dot = name.rfind(".")
    ext = name[dot:] if dot != -1 else ""
    return _EXTENSION_MAP.get(ext, FormatKind.UNSUPPORTED)


def is_extractable(filename: str) -> bool:
    return classify_format(filename) in EXTRACTABLE


def format_matrix() -> Dict[str, str]:
    """Human/machine-readable format -> tool mapping for docs and UIs."""
    return {kind.value: FORMAT_TOOL[kind] for kind in FormatKind}
