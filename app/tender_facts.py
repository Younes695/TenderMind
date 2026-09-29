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
    "Saudi Arabia": ("saudi", "ksa", "kingdom of saudi arabia", "riyadh", "jeddah", "dammam", "sec ", "maaden",
                     "ma'aden", "ma’aden", "السعودية"),
    "Egypt": ("egypt", "cairo", "egyptian electricity", "eetc", "مصر"),
    "United Arab Emirates": ("united arab emirates", "uae", "dubai", "abu dhabi", "dewa", "taqa", "الإمارات"),
    "Qatar": ("qatar", "doha", "kahramaa", "قطر"),
    "Kuwait": ("kuwait", "mew kuwait", "الكويت"),
    "Oman": ("oman", "muscat", "oetc", "عمان"),
    "Bahrain": ("bahrain", "manama", "ewa bahrain", "البحرين"),
    "Jordan": ("jordan", "amman", "nepco", "الأردن"),
    "Iraq": ("iraq", "baghdad", "العراق"),
}


def detect_country(texts: Iterable[str]) -> Optional[str]:
    """Most-mentioned known country across the texts (title/client first)."""
    counts = {}
    for i, t in enumerate(texts):
        low = f" {(t or '').lower()} "
        for country, keys in COUNTRIES.items():
            n = sum(low.count(k) for k in keys)
            if n:
                counts[country] = counts.get(country, 0) + n * (5 if i == 0 else 1)
    return max(counts, key=counts.get) if counts else None
