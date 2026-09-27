"""
Stage 3C — Generic document-aware representative chunk selector (evaluation-only).

Must remain generic: no Mobile/Sarai filenames, no hardcoded category-to-file
mappings, no tender-specific chunk IDs.

Uses only generic metadata:
- document identity (doc_results keys, not filenames)
- document type (extension, classification)
- page/chunk location
- extracted text length
- deterministic candidate categories/signals (GENERIC_PATTERNS)

Goal: small bounded sample with broad document + category coverage.
"""
import re
from typing import List, Dict, Any
from collections import OrderedDict


def _pattern_hits_for_text(text: str, patterns) -> List[str]:
    low = (text or "").lower()
    hits = []
    for pat, cat, _ in patterns:
        try:
            if re.search(pat.lower(), low):
                hits.append(cat)
        except Exception:
            continue
    return sorted(set(hits))


def select_representative_chunks(
    chunks: List[Dict[str, Any]],
    doc_results: Dict[str, Any] = None,
    max_total: int = 10,
    max_per_doc: int = 2,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Select a small bounded sample covering documents and deterministic categories.

    Strategy (generic):
    1. Group chunks by source_document (document identity, not filename value).
    2. Score each chunk by: number of distinct deterministic categories it triggers
       (via GENERIC_PATTERNS), text length (prefer substantive, not empty), and
       early page position (prefer first occurrence per document for stability).
    3. Greedily cover uncovered categories while ensuring every document gets
       at least one chunk (document coverage), bounded by max_total/max_per_doc.

    Returns (selected, rationale) where rationale is a list of dicts explaining
    why each chunk was selected (document coverage vs category coverage).
    """
    from evaluation.generic_extraction import GENERIC_PATTERNS

    if not chunks:
        return [], []

    # Group by document (preserve insertion order)
    by_doc: OrderedDict[str, List[Dict[str, Any]]] = OrderedDict()
    for c in chunks:
        by_doc.setdefault(c.get("source_document", "UNKNOWN"), []).append(c)

    # Score chunks: (num_categories, text_len, -page) — more categories first
    scored = []
    for doc, clist in by_doc.items():
        for c in clist:
            hits = _pattern_hits_for_text(c.get("text", ""), GENERIC_PATTERNS)
            scored.append({
                "chunk": c,
                "doc": doc,
                "hits": hits,
                "num_hits": len(hits),
                "text_len": len((c.get("text") or "").strip()),
                "page": c.get("page_number", 9999),
            })

    selected = []
    rationale = []
    covered_cats: set = set()
    covered_docs: set = set()
    per_doc_count: dict = {}

    # Pass 1: ensure every document gets its best chunk (document coverage)
    for doc in by_doc.keys():
        if len(selected) >= max_total:
            break
        candidates = [s for s in scored if s["doc"] == doc and s["chunk"] not in selected]
        if not candidates:
            continue
        # Best = most categories, then longest text, then earliest page
        candidates.sort(key=lambda s: (-s["num_hits"], -s["text_len"], s["page"]))
        best = candidates[0]
        # Skip empty text chunks
        if best["text_len"] == 0:
            continue
        selected.append(best["chunk"])
        covered_docs.add(doc)
        covered_cats.update(best["hits"])
        per_doc_count[doc] = per_doc_count.get(doc, 0) + 1
        rationale.append({
            "chunk_id": best["chunk"]["chunk_id"],
            "source_document": doc,
            "page_number": best["chunk"].get("page_number"),
            "text_len": best["text_len"],
            "deterministic_categories": best["hits"],
            "reason": "document coverage (best chunk per document)",
        })

    # Pass 2: greedily add chunks that cover new categories, respecting max_per_doc
    # Iterate by most new categories first
    remaining = [s for s in scored if s["chunk"] not in selected and s["text_len"] > 0]
    # Sort by new-category contribution
    while len(selected) < max_total and remaining:
        best_gain = -1
        best_item = None
        for s in remaining:
            if per_doc_count.get(s["doc"], 0) >= max_per_doc:
                continue
            gain = len(set(s["hits"]) - covered_cats)
            # Tie-break: more hits, longer text, earlier page
            score = (gain, s["num_hits"], s["text_len"], -s["page"])
            if best_item is None or score > (best_gain if isinstance(best_gain, tuple) else (-1, -1, -1, 0)):
                # Compare properly
                if best_item is None:
                    best_gain = score
                    best_item = s
                elif score > best_gain:
                    best_gain = score
                    best_item = s
        if best_item is None:
            break
        # Only add if it contributes a new category or we still have room and docs need depth?
        # To keep bounded, only add if gain > 0, unless we have fewer than max_total and want depth?
        # For Stage 3C, we want broad coverage, so require gain > 0 for pass 2.
        if best_gain[0] <= 0:
            break
        selected.append(best_item["chunk"])
        covered_cats.update(best_item["hits"])
        per_doc_count[best_item["doc"]] = per_doc_count.get(best_item["doc"], 0) + 1
        rationale.append({
            "chunk_id": best_item["chunk"]["chunk_id"],
            "source_document": best_item["doc"],
            "page_number": best_item["chunk"].get("page_number"),
            "text_len": best_item["text_len"],
            "deterministic_categories": best_item["hits"],
            "reason": f"category coverage (adds {sorted(set(best_item['hits']) - covered_cats) if False else 'new categories'})",
        })
        remaining = [s for s in remaining if s["chunk"] not in selected]

    # Fix rationale reason for pass 2 (compute gain before update)
    # Recompute reasons accurately
    seen_cats: set = set()
    for r in rationale:
        if r["reason"].startswith("category coverage"):
            new_cats = sorted(set(r["deterministic_categories"]) - seen_cats)
            r["reason"] = f"category coverage (adds {new_cats})" if new_cats else "category coverage"
        seen_cats.update(r["deterministic_categories"])

    return selected, rationale
