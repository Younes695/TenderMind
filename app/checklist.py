"""Stage 7 — bid submission checklist.

Items are the tender's own requirements that ask the bidder to submit, attach, sign, stamp or
fill something WITH THE BID — not submittals due later during execution (manuals, as-built,
schedules for approval). Each keeps its quote, file and page. The team marks each item
READY / NOT_APPLICABLE and assigns it (state in SubmissionItem, keyed by a stable hash).
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List

_VERB = r"(submit|provide|include|attach|enclose|furnish|sign|stamp|fill|accompan|complete)\w*"
# an explicit ask of the bidder: "Bidder shall provide ...", "submitted with the bid",
# "Proposal shall be accompanied with ...", "duly filled-in / signed"
_ASK = re.compile(
    rf"\b(bidders?|tenderers?|proposals?|offers?|bids?)\b[^.=]{{0,80}}\b(shall|must|should|is\s+required\s+to|are\s+required\s+to|"
    rf"to\s+be)\b[^.=]{{0,40}}\b{_VERB}|"
    rf"\b{_VERB}\s+(?:\w+\s+){{0,6}}(with|in|as\s+(?:an\s+)?attachment\s+to)\s+(the|his|their|this|its)\s+(bid|proposal|offer)\b|"
    rf"\bduly\s+(filled|signed|stamped|completed)", re.IGNORECASE)
_NOT_ITEM = re.compile(r"[\"\u201c][^\"\u201d]{2,40}[\"\u201d]\s+means\b|=|\bmay\s+submit\b|\bonly\s+firms\b",
                       re.IGNORECASE)
_EXECUTION = re.compile(r"\b(during\s+(the\s+)?(construction|execution|project|installation)|as-?built|manuals?|"
                        r"before\s+(energi[sz]ation|commissioning|mechanical\s+completion|delivery|shipment)|"
                        r"for\s+(company\s+)?(review\s+and\s+)?approval|after\s+(award|contract\s+(award|signature))|"
                        r"within\s+\d+\s+(days|weeks)\s+(after|from|of)\s+(the\s+)?(award|effective|contract))",
                        re.IGNORECASE)
SIMILAR = 0.7


def _tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2}


def item_key(text: str) -> str:
    return hashlib.sha1(" ".join(sorted(_tokens(text))).encode("utf-8")).hexdigest()[:16]


def is_bid_item(text: str) -> bool:
    t = text or ""
    return bool(_ASK.search(t) and not _NOT_ITEM.search(t) and not _EXECUTION.search(t))


def build(requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Checklist items from the analysis requirements, near-duplicates merged."""
    out: List[Dict[str, Any]] = []
    toks: List[set] = []
    for r in requirements or []:
        quote = " ".join(str(r.get("source_text") or r.get("summary") or "").split())
        if not quote or not is_bid_item(quote):
            continue
        tk = _tokens(quote)
        if any(tk and o and len(tk & o) / len(tk | o) >= SIMILAR for o in toks):
            continue
        toks.append(tk)
        out.append({"key": item_key(quote), "title": (r.get("summary") or quote)[:200], "quote": quote[:400],
                    "file": r.get("source_document"), "page": r.get("page_number"),
                    "mandatory": r.get("mandatory")})
    return out


STATUSES = ("TODO", "READY", "NOT_APPLICABLE")


def progress(items: List[Dict[str, Any]]) -> Dict[str, int]:
    c = {s: sum(1 for i in items if i.get("status") == s) for s in STATUSES}
    c["total"] = len(items)
    return c
