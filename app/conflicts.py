"""Stage 7 — conflicts inside the tender package.

Two kinds, both read from the tender's own words with file, page and quote:
  1. the same commercial / time fact stated with different values in different documents
     (bid validity, completion period, bid / performance bond %, advance payment %, retention %,
     liquidated-damages cap %, warranty period);
  2. a number written in words that disagrees with the digits next to it
     ("twenty six percent (13%)").
A conflict is never resolved here — each becomes a clarification question for the tender owner.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List

from app.eligibility import _sentence

_NUM = r"(\d{1,3}(?:\.\d{1,2})?)"
_SKIP = re.compile(r"\b(recover\w*|deduct\w*|per\s+(day|week)|each\s+(day|week))\b", re.IGNORECASE)
FACTS = {
    "bid_validity": ("Bid validity", "days", re.compile(
        rf"\b(?:bid|offer|proposal|tender)s?\b.{{0,40}}\bvalid(?:ity)?\b.{{0,40}}?\b(\d{{2,3}})\s*(?:\(\w+\)\s*)?(?:calendar\s+)?days\b",
        re.IGNORECASE)),
    "completion": ("Completion period", "days", re.compile(
        rf"\b(?:completion|execution|contract)\s+(?:period|time|duration)\b.{{0,40}}?\b(\d{{1,4}})\s*(?:\(\w+\)\s*)?"
        rf"(?:calendar\s+)?(days|weeks|months)\b", re.IGNORECASE)),
    "bid_bond": ("Bid bond", "%", re.compile(
        rf"\b(?:bid|tender)\s+(?:bond|security|guarantee)\b.{{0,60}}?\b{_NUM}\s*%", re.IGNORECASE)),
    "performance_bond": ("Performance bond", "%", re.compile(
        rf"\bperformance\s+(?:bond|security|guarantee)\b.{{0,60}}?\b{_NUM}\s*%", re.IGNORECASE)),
    "advance_payment": ("Advance payment", "%", re.compile(
        rf"\badvance\s+payment\s+(?:of|equal\s+to|shall\s+be|amounting\s+to)\b.{{0,30}}?\b{_NUM}\s*%", re.IGNORECASE)),
    "retention": ("Retention", "%", re.compile(rf"\bretention\b.{{0,50}}?\b{_NUM}\s*%", re.IGNORECASE)),
    "ld_cap": ("Liquidated damages cap", "%", re.compile(
        rf"\bliquidated\s+damages\b.{{0,120}}?\b(?:maximum|cap|not\s+exceed|limited\s+to)\b.{{0,40}}?\b{_NUM}\s*%",
        re.IGNORECASE)),
    "warranty": ("Warranty period", "months", re.compile(
        r"\b(?:warranty|guarantee|defects?\s+liability)\s+period\b.{0,40}?\b(\d{1,3})\s*(?:\(\w+\)\s*)?(months|years)\b",
        re.IGNORECASE)),
}
_UNIT_DAYS = {"days": 1, "weeks": 7, "months": 30}

_ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                    "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_WORDS_NUM = re.compile(r"\b((?:(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety)[\s-]?)?"
                        r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
                        r"fifteen|sixteen|seventeen|eighteen|nineteen)?|one hundred|hundred)\s*(percent|per\s*cent|days?|"
                        r"months?|weeks?|years?)?\s*\(\s*(\d{1,3})\s*(%|days?|months?|weeks?|years?)?\s*\)", re.IGNORECASE)


def words_to_int(words: str):
    w = words.lower().replace("-", " ").split()
    if not w:
        return None
    if w == ["one", "hundred"] or w == ["hundred"]:
        return 100
    total = 0
    for x in w:
        if x in _TENS:
            total += _TENS[x]
        elif x in _ONES:
            total += _ONES[x]
        else:
            return None
    return total


def _value(fact: str, m) -> float:
    v = float(m.group(1))
    if fact == "completion":
        return v * _UNIT_DAYS[m.group(2).lower()]
    if fact == "warranty":
        return v * (12 if m.group(2).lower().startswith("year") else 1)
    return v


def find(sources) -> List[Dict[str, Any]]:
    by_fact: Dict[str, Dict[float, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    out: List[Dict[str, Any]] = []
    seen_words = set()
    for s in sources:
        text = s.text or ""
        for fact, (_label, _unit, rx) in FACTS.items():
            for m in rx.finditer(text):
                sent = _sentence(text, m.start(), m.end())
                if _SKIP.search(sent):
                    continue
                v = _value(fact, m)
                ev = {"file": s.source_document, "page": s.page_number, "quote": " ".join(sent.split())[:300]}
                if len(by_fact[fact][v]) < 3:
                    by_fact[fact][v].append(ev)
        for m in _WORDS_NUM.finditer(text):
            words, digits = m.group(1).strip(), int(m.group(3))
            n = words_to_int(words)
            if n is None or n == digits or (m.group(2) is None and m.group(4) is None):
                continue
            quote = " ".join(_sentence(text, m.start(), m.end()).split())[:300]
            if quote in seen_words:
                continue
            seen_words.add(quote)
            out.append({"fact": "words_vs_digits", "label": "Number in words differs from the digits",
                        "values": [{"value": f"{words} ({n})", "file": s.source_document, "page": s.page_number,
                                    "quote": quote},
                                   {"value": str(digits), "file": s.source_document, "page": s.page_number,
                                    "quote": quote}]})
    for fact, values in by_fact.items():
        docs = {ev["file"] for evs in values.values() for ev in evs}
        if len(values) < 2 or len(docs) < 2:
            continue  # one value, or all mentions in one document (e.g. per-portion figures)
        label, unit, _ = FACTS[fact]
        out.append({"fact": fact, "label": label, "unit": unit,
                    "values": [dict(ev, value=f"{v:g} {unit}") for v, evs in sorted(values.items()) for ev in evs[:1]]})
    return out


_CACHE: Dict[str, Any] = {}


def tender_conflicts(tender_id: str) -> List[Dict[str, Any]]:
    """Memoised on the extraction cache, like the RFP sections."""
    from app.pipeline.checkpoint import cache_dir
    from app.sections import sources_from_cache
    d = cache_dir(tender_id)
    stamp = (tuple(sorted((f.name, f.stat().st_mtime) for f in d.glob("extract-v*.json"))) if d.is_dir() else ())
    hit = _CACHE.get(tender_id)
    if hit and hit[0] == stamp:
        return hit[1]
    res = find(sources_from_cache(tender_id)) if stamp else []
    _CACHE[tender_id] = (stamp, res)
    return res
