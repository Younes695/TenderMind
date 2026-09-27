"""Stage 4A — structured-data adapter boundary.

Context: a Data Engineering contributor produced exploratory Excel/notebook
outputs (price-schedule rows, form fields, equipment, delivery, experience).
That work is REFERENCE/INPUT ONLY: it is never copied into production, never
imported, its hardcoded paths and exploratory assumptions never inherited.

This module defines the clean boundary future extraction pipelines feed
through: StructuredTable / FormRecord / CommercialLineItem /
ProjectExperienceRecord (see contracts.py), plus ONE low-risk generic adapter
covering the safe subset of what the repo already parses with openpyxl
(data_only values, all sheets, |-joined text, per-sheet caps).

Explicitly out of scope: domain-specific FORM-D reconstruction, styling /
formula / chart / merged-cell interpretation, ground-truth claims about any
contributor spreadsheet.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.pipeline.contracts import CommercialLineItem, FormRecord, StructuredTable

MAX_CELL_CHARS = 5000  # mirrors the current production per-sheet text cap
MAX_ROWS_PER_SHEET = 5000


class StructuredDataAdapter(ABC):
    """Interface for feeding normalized structured facts into TenderMind."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def can_handle(self, source: Union[str, Path]) -> bool: ...

    @abstractmethod
    def read_tables(self, source: Union[str, Path]) -> List[StructuredTable]:
        """Return normalized tables. Never raises on bad content: returns []."""


class GenericXlsxAdapter(StructuredDataAdapter):
    """Generic .xlsx ingestion: values only, no styling/formula interpretation.

    Accepts a filesystem path OR a binary stream (tests use in-memory
    workbooks — no temp files, no hardcoded paths).
    """

    @property
    def name(self) -> str:
        return "generic-xlsx-1"

    def can_handle(self, source: Union[str, Path]) -> bool:
        name = getattr(source, "name", None) or str(source)
        return str(name).lower().endswith(".xlsx")

    def read_tables(self, source: Union[str, Path]) -> List[StructuredTable]:
        try:
            from openpyxl import load_workbook
        except Exception:
            return []
        label = getattr(source, "name", None) or str(source)
        try:
            if hasattr(source, "read"):
                wb = load_workbook(source, data_only=True, read_only=True)
                doc = str(label)
            else:
                p = Path(str(source))
                if not p.is_file():
                    return []
                wb = load_workbook(p, data_only=True, read_only=True)
                doc = p.name
        except Exception:
            return []
        tables: List[StructuredTable] = []
        try:
            for ws in wb.worksheets:
                columns: List[str] = []
                rows: List[Dict[str, Any]] = []
                for i, row in enumerate(ws.iter_rows(values_only=True)):
                    if i >= MAX_ROWS_PER_SHEET:
                        break
                    vals = [("" if v is None else str(v))[:500] for v in row]
                    if not any(v.strip() for v in vals):
                        continue
                    if not columns:
                        columns = [v.strip() or f"col_{n}" for n, v in enumerate(vals)]
                        continue
                    record = {columns[n] if n < len(columns) else f"col_{n}": v
                              for n, v in enumerate(vals)}
                    rows.append(record)
                if rows:
                    tables.append(StructuredTable(
                        source_document=doc, sheet=ws.title,
                        columns=columns, rows=rows, row_count=len(rows)))
        finally:
            try:
                wb.close()
            except Exception:
                pass
        return tables


def read_structured(source: Union[str, Path],
                    adapters: Optional[List[StructuredDataAdapter]] = None) -> List[StructuredTable]:
    """Read via the first capable adapter; [] when nothing can handle the source."""
    for adapter in adapters or [GenericXlsxAdapter()]:
        try:
            if adapter.can_handle(source):
                return adapter.read_tables(source)
        except Exception:
            continue
    return []


# Generic bilingual BOQ header aliases (EN + AR commercial terms observed in
# source price schedules). Generic vocabulary only — NO tender-specific rules.
BOQ_ALIASES = {
    "item": {"item", "no", "no.", "s.no", "sr", "s/n", "البند", "م"},
    "description": {"description", "desc", "details", "particulars", "الوصف", "البيان"},
    "unit": {"unit", "uom", "الوحدة"},
    "quantity": {"quantity", "qty", "amount", "الكمية"},
    "unit_price": {"unit price", "material unit price", "rate", "unit rate",
                   "سعر الوحدة", "الفئة"},
    "total_price": {"total", "total price", "total material price", "amount total",
                    "السعر الاجمالى", "الاجمالى", "الجملة"},
}


def _norm_header(h: str) -> str:
    return " ".join(str(h or "").lower().replace("\n", " ").split())


_ARABIC_RE = None


def split_bilingual(text: str):
    """Split mixed EN/AR cell text into (latin_part, arabic_part).

    Generic script-range split; either part may be ''. No translation,
    no interpretation, no tender-specific rules.
    """
    import re
    global _ARABIC_RE
    if _ARABIC_RE is None:
        _ARABIC_RE = re.compile(r"[\u0600-\u06FF]+")
    s = str(text or "")
    ar = " ".join(_ARABIC_RE.findall(s)).strip()
    en = _ARABIC_RE.sub(" ", s)
    en = " ".join(en.split())
    return en, (ar or "")


def map_boq_columns(columns: List[str]) -> Dict[str, str]:
    """Map raw headers to canonical BOQ slots. Unknown headers stay unmapped.

    Two passes so specific multi-word headers win over single-token affixes
    (e.g. 'material unit price ...' must be unit_price, not unit).
    """
    mapping: Dict[str, str] = {}
    norms = {col: _norm_header(col) for col in columns}
    # Pass 1: exact or multi-word alias containment.
    for col, n in norms.items():
        for slot, aliases in BOQ_ALIASES.items():
            if n in aliases or any(" " in a and a in n for a in aliases):
                mapping[col] = slot
                break
    # Pass 2: single-token affix fallback for the rest.
    for col, n in norms.items():
        if col in mapping:
            continue
        for slot, aliases in BOQ_ALIASES.items():
            singles = [a for a in aliases if " " not in a]
            if any(n.startswith(a + " ") or n.endswith(" " + a) or n == a for a in singles):
                mapping[col] = slot
                break
    return mapping


def normalize_boq_table(table: StructuredTable) -> List[CommercialLineItem]:
    """Deterministic StructuredTable -> CommercialLineItem[] for BOQ-shaped sheets.

    Header-row detection: title rows precede the real header, so the adapter's
    first-row assumption is NOT trusted. The header is the first row (adapter
    columns, then up to 10 data rows by VALUE) mapping to a description slot
    plus at least one more BOQ slot. Data rows are re-keyed positionally to
    the detected header. Location preserves sheet + 1-based sheet-row number.
    """
    candidates = [list(table.columns)] + [list(r.values()) for r in table.rows[:10]]
    header, hidx, mapping = None, None, {}
    for idx, hvals in enumerate(candidates):
        hvals = [str(v) for v in hvals]
        m = map_boq_columns(hvals)
        if "description" in m.values() and len(set(m.values())) >= 2:
            header, hidx, mapping = hvals, idx, m
            break
    if header is None:
        return []  # not a BOQ-shaped table; refuse to guess
    if hidx == 0:
        data = [(j + 2, row) for j, row in enumerate(table.rows)]
        keyed = [{mapping.get(k, k): v for k, v in row.items()} for _, row in data]
    else:
        data = []
        keyed = []
        # candidates[hidx] == table.rows[hidx-1]; data starts AFTER it.
        for j in range(hidx, len(table.rows)):
            vals = list(table.rows[j].values())
            row = {header[n] if n < len(header) else f"col_{n}": vals[n]
                   for n in range(len(vals))}
            data.append((j + 2, row))
            keyed.append({mapping.get(k, k): v for k, v in row.items()})
    items: List[CommercialLineItem] = []
    for (sheet_row, _), inv in zip(data, keyed):
        desc = str(inv.get("description", "") or "").strip()
        if len(desc) < 8:
            # Ragged/merged headers can misalign columns; BOQ descriptions are
            # generically the longest text cell in a line-item row.
            long_cells = [str(v or "").strip() for k, v in inv.items()
                          if len(str(v or "").strip()) >= 20]
            if long_cells:
                desc = max(long_cells, key=len)
        if not desc or len(desc) < 3:
            continue
        loc = f"{table.sheet}!R{sheet_row}"
        en, ar = split_bilingual(desc)
        items.append(CommercialLineItem(
            source_document=table.source_document, location=loc,
            item=str(inv.get("item", "") or "").strip() or None,
            description=desc,
            description_ar=ar or None,
            unit=str(inv.get("unit", "") or "").strip() or None,
            quantity=str(inv.get("quantity", "") or "").strip() or None,
            unit_price=str(inv.get("unit_price", "") or "").strip() or None,
            total_price=str(inv.get("total_price", "") or "").strip() or None))
    return items


def _detect_boq_header(table: StructuredTable):
    """Legacy shim (kept for compatibility; detection now lives inline)."""
    m = map_boq_columns(table.columns)
    if "description" in m.values():
        return 0, m
    return None, {}
    for idx in range(min(10, len(table.rows))):
        trial_cols = list(table.rows[idx].keys())
        m = map_boq_columns(trial_cols)
        if "description" in m.values() and len(set(m.values())) >= 2:
            # remap subsequent rows onto the detected header
            return idx + 1, m
    # fallback: original columns
    m = map_boq_columns(table.columns)
    if "description" in m.values():
        return 0, m
    return None, {}
