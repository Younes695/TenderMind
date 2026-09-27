"""
Stage 3I — Deterministic pre-segmentation splitter (evaluation-only adapter).

Reuses existing GENERIC_PATTERNS / deterministic category signals. Never calls
the LLM to decide the split. See segmentation_rules.md for the documented rules.
"""
import re
from typing import List, Dict, Any, Tuple

MIN_CANDIDATE_CHARS = 20
MAX_MIXED_CATEGORIES = 2  # >=3 distinct hits -> ambiguous, reject
MIN_PRINTABLE_RATIO = 0.7


def split_sentences(text: str) -> List[Tuple[str, int, int]]:
    """Split text into (sentence, start, end) spans.

    Rule: split on newlines first, then on sentence boundaries where a
    terminator (`.`, `;`, `?`, `!`) is followed by whitespace and an uppercase
    letter, digit, or opening quote. This keeps abbreviations like `No. (1)`
    intact (`.` followed by `(` does not split).
    """
    spans = []
    # First split on newlines to preserve list structure
    line_start = 0
    lines = []
    for m in re.finditer(r"\n", text):
        lines.append((text[line_start:m.start()], line_start, m.start()))
        line_start = m.end()
    lines.append((text[line_start:], line_start, len(text)))
    for line, base, _ in lines:
        if not line.strip():
            continue
        # Then split each line on sentence boundaries
        parts = re.split(r"(?<=[.;?!])\s+(?=[A-Z0-9\"\u201c\u201c])", line)
        offset = 0
        for part in parts:
            idx = line.find(part, offset)
            s, e = base + idx, base + idx + len(part)
            spans.append((part.strip(), s, e))
            offset = idx + len(part)
    return [(s, a, b) for (s, a, b) in spans if s]


def pattern_hits(sentence: str, patterns=None) -> List[str]:
    """Deterministic category signals for one sentence (production regexes)."""
    if patterns is None:
        from evaluation.generic_extraction import GENERIC_PATTERNS as patterns
    low = sentence.lower()
    hits = []
    for pat, cat, _ in patterns:
        try:
            if re.search(pat.lower(), low):
                hits.append(cat)
        except Exception:
            continue
    # Preserve pattern order, deduplicate
    seen = []
    for h in hits:
        if h not in seen:
            seen.append(h)
    return seen


def printable_ratio(text: str) -> float:
    if not text:
        return 0.0
    ok = sum(1 for c in text if c.isprintable() or c in "\n\r\t")
    return ok / max(len(text), 1)


def segment_parent_chunk(parent: Dict[str, Any], patterns=None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split one parent chunk into accepted / rejected single-purpose candidates.

    Accepted: non-empty, >=MIN_CANDIDATE_CHARS, printable, >=1 signal hit,
    at most MAX_MIXED_CATEGORIES distinct hits.
    """
    accepted, rejected = [], []
    seq = 0
    for sent, start, end in split_sentences(parent["text"]):
        stripped = sent.strip()
        if not stripped:
            rejected.append(_rej(parent, sent, start, end, "empty"))
            continue
        if len(stripped) < MIN_CANDIDATE_CHARS:
            rejected.append(_rej(parent, sent, start, end, "tiny"))
            continue
        if printable_ratio(stripped) < MIN_PRINTABLE_RATIO:
            rejected.append(_rej(parent, sent, start, end, "ocr_garbage"))
            continue
        hits = pattern_hits(stripped, patterns)
        if len(hits) == 0:
            rejected.append(_rej(parent, sent, start, end, "no_signal", hits))
            continue
        if len(hits) > MAX_MIXED_CATEGORIES:
            rejected.append(_rej(parent, sent, start, end, "mixed_multi_category", hits))
            continue
        seq += 1
        accepted.append({
            "candidate_id": f"{parent['chunk_id']}-seg-{seq:02d}",
            "parent_chunk_id": parent["chunk_id"],
            "source_document": parent["source_document"],
            "page": parent.get("page_number", parent.get("page", 1)),
            "source_text": stripped,
            "span": [start, end],
            "deterministic_signal_categories": hits,
        })
    return accepted, rejected


def _rej(parent, sent, start, end, reason, hits=None):
    return {
        "parent_chunk_id": parent["chunk_id"],
        "source_document": parent["source_document"],
        "page": parent.get("page_number", parent.get("page", 1)),
        "source_text": sent.strip()[:200],
        "span": [start, end],
        "deterministic_signal_categories": hits or [],
        "rejection_reason": reason,
    }
