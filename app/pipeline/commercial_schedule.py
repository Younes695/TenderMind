"""Stage 4F — commercial + schedule intelligence (deterministic first).

Deterministic extraction reuses the validated evaluation extractors through a
documented read-only seam (no behavior change there). AI/hybrid interpretation
of ambiguous clauses stays NOT_CONFIGURED; this module returns explicit
unknown/ambiguous states instead of guessing.

Relative dates are NEVER silently calendared: without an explicit anchor only
raw_expression + normalized_duration + anchor_type=unknown are returned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.pipeline.contracts import ScheduleRecord, SourceText

_RELATIVE = re.compile(
    r"within\s+(\d+)\s+(day|days|week|weeks|month|months|year|years)\s+(?:from|after|of)\s+([a-zA-Z /-]+)",
    re.IGNORECASE)
_DURATION = re.compile(r"(\d+)\s+(day|days|week|weeks|month|months|year|years)", re.IGNORECASE)
_CURRENCY = re.compile(r"\b(EGP|LE|USD|EUR|GBP|SAR|EGP|[\$€£])\b")
_MONEY = re.compile(r"(?:EGP|LE|USD|EUR|GBP|SAR|\$|€|£)\s?[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s?(?:EGP|LE|USD|EUR|million|billion|%)", re.IGNORECASE)


@dataclass
class CommercialFacts:
    currency: Optional[str] = None
    currency_source: Optional[str] = None
    payment_terms: Optional[str] = None
    payment_source: Optional[str] = None
    bid_security: Optional[str] = None
    bid_security_source: Optional[str] = None
    validity: Optional[str] = None
    validity_source: Optional[str] = None
    amounts: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ScheduleFacts:
    records: List[ScheduleRecord] = field(default_factory=list)


def extract_commercial_facts(sources: List[SourceText]) -> CommercialFacts:
    """Deterministic commercial slots from explicit patterns only."""
    out = CommercialFacts()
    for s in sources:
        text = s.text or ""
        if out.currency is None:
            m = _CURRENCY.search(text)
            if m:
                out.currency = m.group(1)
                out.currency_source = f"{s.source_document}#p{s.page_number}"
        low = text.lower()
        if out.payment_terms is None and any(k in low for k in ("payment", "payable", "paid within", "advance payment")):
            sent = next((ln.strip() for ln in text.split("\n") if "pay" in ln.lower()), "")
            if sent:
                out.payment_terms, out.payment_source = sent[:200], f"{s.source_document}#p{s.page_number}"
        if out.bid_security is None and any(k in low for k in ("bid security", "bid bond", "tender guarantee", "performance guarantee")):
            sent = next((ln.strip() for ln in text.split("\n") if "guarantee" in ln.lower() or "bond" in ln.lower() or "security" in ln.lower()), "")
            if sent:
                out.bid_security, out.bid_security_source = sent[:200], f"{s.source_document}#p{s.page_number}"
        if out.validity is None and ("valid" in low and "day" in low):
            m = re.search(r"valid[^.\n]{0,60}?\d+\s+days?", text, re.IGNORECASE)
            if m:
                out.validity, out.validity_source = m.group(0)[:200], f"{s.source_document}#p{s.page_number}"
        for m in _MONEY.finditer(text):
            out.amounts.append({"raw": m.group(0)[:60], "source": f"{s.source_document}#p{s.page_number}"})
            if len(out.amounts) >= 50:
                break
    return out


def _normalize_duration(num: str, unit: str) -> str:
    n = int(num)
    u = unit.lower()
    if u.startswith("week"):
        return f"P{n * 7}D"
    if u.startswith("month"):
        return f"P{n}M"
    if u.startswith("year"):
        return f"P{n}Y"
    return f"P{n}D"


def extract_schedule_facts(sources: List[SourceText],
                           anchors: Optional[Dict[str, str]] = None) -> ScheduleFacts:
    """Explicit dates stay raw; relative durations get anchor_type/value.

    anchors: e.g. {"award": "2026-03-01", "submission": "2026-02-01"} when an
    explicit anchor date exists. Without anchors: normalized_date stays None.
    """
    anchors = anchors or {}
    out = ScheduleFacts()
    for s in sources:
        loc = f"{s.source_document}#p{s.page_number}"
        for m in _RELATIVE.finditer(s.text or ""):
            num, unit, anchor_raw = m.group(1), m.group(2), m.group(3).strip()
            key = anchor_raw.lower()
            anchor_value = None
            for name, val in anchors.items():
                if name in key:
                    anchor_value = val
                    break
            out.records.append(ScheduleRecord(
                source_document=s.source_document, location=loc, kind="duration",
                value=m.group(0)[:200],
                normalized_date=(f"{anchor_value}+{_normalize_duration(num, unit)}"
                                 if anchor_value else None)))
        # explicit calendar dates (conservative ISO-like + common tender forms)
        for m in re.finditer(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", s.text or ""):
            out.records.append(ScheduleRecord(
                source_document=s.source_document, location=loc, kind="explicit-date",
                value=m.group(1), normalized_date=None))
    return out


def schedule_record_dict(r: ScheduleRecord) -> Dict[str, Any]:
    """Wire format: raw expression always preserved; anchor explicitness visible."""
    anchor_type, anchor_value, duration = "unknown", None, None
    if r.normalized_date and "+" in r.normalized_date:
        anchor_value, duration = r.normalized_date.split("+", 1)
        anchor_type = "explicit-anchor"
    elif r.kind == "duration":
        m = _DURATION.search(r.value or "")
        duration = _normalize_duration(m.group(1), m.group(2)) if m else None
    return {"source_document": r.source_document, "location": r.location, "kind": r.kind,
            "raw_expression": r.value, "normalized_duration": duration,
            "anchor_type": anchor_type, "anchor_value": anchor_value,
            "normalized_date": r.normalized_date if anchor_value else None}
