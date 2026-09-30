"""Deterministic facts about a tender used by the eligibility gate and the score:
work type (substation / line / cable ...), voltage (kV) and country.
(Kind and kV helpers moved here from the removed Stage 5J value estimate.)
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

_KV = re.compile(r"(\d{2,3})(?:/\d{1,3}){0,3}\s?kV", re.IGNORECASE)

WORK_TYPES = ("substation", "overhead line", "cable", "distribution", "generation", "renewables", "other")


def classify_kind(text: str) -> Optional[str]:
    """Main work type named in the text (the title is the best source)."""
    t = (text or "").lower()
    if "substation" in t or " gis" in t or "switchyard" in t or "محطة" in t:
        return "substation"
    if "transmission line" in t or "overhead line" in t or "ohtl" in t or "ohl" in t or "interconnect" in t:
        return "overhead line"
    if "underground cable" in t or "cable" in t:
        return "cable"
    if "distribution" in t or "switchgear" in t or "feeder" in t or "ring main" in t:
        return "distribution"
    if re.search(r"solar|photovoltaic|\bpv\b|wind farm|bess|battery energy", t):
        return "renewables"
    if re.search(r"power plant|power station|generation|turbine", t):
        return "generation"
    return None


def max_kv(text: str) -> Optional[int]:
    vals = [int(v) for v in _KV.findall(text or "") if 1 <= int(v) <= 800]
    return max(vals) if vals else None


def main_kv(title: str, body: str = "") -> Optional[int]:
    """The tender's own voltage: from its title when stated, otherwise the most
    frequent kV in the text (the maximum picked up stray 500 kV mentions)."""
    if max_kv(title):
        return max_kv(title)
    vals = [int(v) for v in _KV.findall(body or "") if 1 <= int(v) <= 800]
    return max(set(vals), key=vals.count) if vals else None


COUNTRIES = {
    "Saudi Arabia": ("saudi", "ksa", "kingdom of saudi arabia", "riyadh", "jeddah", "dammam", "maaden",
                     "ma'aden", "ma’aden", "السعودية"),
    "Egypt": ("egypt", "egyptian", "cairo", "egyptian electricity", "eetc", "مصر"),
    "United Arab Emirates": ("united arab emirates", "uae", "dubai", "abu dhabi", "dewa", "الإمارات"),
    "Qatar": ("qatar", "doha", "kahramaa", "قطر"),
    "Kuwait": ("kuwait", "mew kuwait", "الكويت"),
    "Oman": ("oman", "muscat", "oetc", "عمان"),
    "Bahrain": ("bahrain", "manama", "ewa bahrain", "البحرين"),
}


_WORDS = {}


def _word(key: str):
    if key not in _WORDS:
        _WORDS[key] = re.compile(rf"(?<![\w\u0600-\u06ff]){re.escape(key)}(?![\w\u0600-\u06ff])")
    return _WORDS[key]


def detect_country(texts: Iterable[str]) -> Optional[str]:
    """Most-mentioned known country across the texts (title/client first)."""
    counts = {}
    for i, t in enumerate(texts):
        low = (t or "").lower()
        for country, keys in COUNTRIES.items():
            n = sum(len(_word(k).findall(low)) for k in keys)  # whole words: "oman" is not in "roman"
            if n:
                counts[country] = counts.get(country, 0) + n * (5 if i == 0 else 1)
    return max(counts, key=counts.get) if counts else None


# Stage 8 — the client (tender owner). Known power-sector owners first (name as shown), then an
# explicit "Client / Owner / Employer: X" line. Returns (name, evidence) — evidence has file + page.
KNOWN_CLIENTS = {
    "Saudi Electricity Company (SEC)": ("saudi electricity company", "saudi electricity co", "sec "),
    "National Grid SA": ("national grid", "ngsa"),
    "Ma'aden": ("ma'aden", "maaden", "ma\u2019aden"),
    "NEOM": ("neom",),
    "Saudi Aramco": ("saudi aramco", "aramco"),
    "Egyptian Electricity Transmission Company (EETC)": ("egyptian electricity transmission", "eetc"),
    "Dubai Electricity and Water Authority (DEWA)": ("dewa", "dubai electricity"),
    "KAHRAMAA": ("kahramaa",),
    "OETC": ("oetc", "oman electricity transmission"),
}
_CLIENT_LINE = re.compile(r"\b(?:client|owner|employer|purchaser|contracting\s+authority)\s*[:\-]\s*"
                          r"([A-Z][A-Za-z&.,'\u2019() -]{3,70})", re.IGNORECASE)


def normalise_client(name: str) -> str:
    """For matching the same client across tenders: known name, else lower-case letters only."""
    low = f" {(name or '').lower()} "
    for canon, keys in KNOWN_CLIENTS.items():
        if any(k in low for k in keys):
            return canon
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def detect_client(sources, entered: str = ""):
    """(client name, evidence|None). The team's entry wins; otherwise the most-mentioned known owner."""
    if (entered or "").strip():
        return normalise_client(entered) if normalise_client(entered) in KNOWN_CLIENTS else entered.strip(), None
    counts, first = {}, {}
    for s in list(sources)[:400]:
        low = f" {(s.text or '').lower()} "
        for canon, keys in KNOWN_CLIENTS.items():
            n = sum(low.count(k) for k in keys)
            if n:
                counts[canon] = counts.get(canon, 0) + n
                first.setdefault(canon, {"file": s.source_document, "page": s.page_number})
    if counts:
        best = max(counts, key=counts.get)
        return best, first[best]
    for s in list(sources)[:60]:
        m = _CLIENT_LINE.search(s.text or "")
        if m:
            return m.group(1).strip(" .,-"), {"file": s.source_document, "page": s.page_number}
    return None, None
