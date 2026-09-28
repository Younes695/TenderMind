"""Stage 5I — subcontractor RFQs: quotation comparison and RFQ drafting.

Best quotation = highest weighted score among quotations that meet the minimum
technical fit. Scores are relative to the other quotations of the same RFQ:
  technical fit 40% · price 35% (lowest = 1) · duration 15% (shortest = 1)
  · payment terms 10% (longest credit = 1, better for the main contractor's cash flow)
Every score comes with a plain-language reason; nothing is hidden.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

WEIGHTS = {"technical_fit": 0.40, "price": 0.35, "duration": 0.15, "terms": 0.10}
MIN_TECHNICAL_FIT = 60.0

DISCIPLINE_KEYWORDS = {
    "HVAC": r"hvac|air[- ]condition|chiller|ventilat|duct|fan coil|ahu\b",
    "Mechanical": r"mechanical|pump|piping|fire fighting|firefighting|plumbing|hvac|ventilat",
    "Electrical": r"electrical|cable|switchgear|transformer|lighting|earthing|panel|lv\b|mv\b",
    "Civil": r"civil|concrete|foundation|excavat|building|steel structure|road|fence",
    "Protection & Control": r"protection|relay|scada|control|telecom|communication",
}


def score_quotations(quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not quotes:
        return []
    prices = [q["price"] for q in quotes if q["price"] > 0]
    durs = [q["duration_weeks"] for q in quotes if q["duration_weeks"] > 0]
    terms = [q["payment_terms_days"] for q in quotes]
    min_price, min_dur, max_terms = (min(prices) if prices else 0), (min(durs) if durs else 0), (max(terms) or 1)
    out = []
    for q in quotes:
        parts = {
            "technical_fit": max(0.0, min(q["technical_fit"], 100.0)) / 100.0,
            "price": (min_price / q["price"]) if q["price"] > 0 else 0.0,
            "duration": (min_dur / q["duration_weeks"]) if q["duration_weeks"] > 0 else 0.0,
            "terms": (q["payment_terms_days"] / max_terms) if max_terms else 0.0,
        }
        score = round(100 * sum(WEIGHTS[k] * v for k, v in parts.items()), 1)
        eligible = q["technical_fit"] >= MIN_TECHNICAL_FIT
        out.append({**q, "score": score, "eligible": eligible, "is_best": False,
                    "score_parts": {k: round(v * 100, 1) for k, v in parts.items()}})
    ranked = sorted((o for o in out if o["eligible"]), key=lambda o: o["score"], reverse=True)
    if ranked:
        best = ranked[0]
        best["is_best"] = True
        reasons = []
        if best["price"] == min_price:
            reasons.append("lowest price")
        if best["technical_fit"] == max(o["technical_fit"] for o in out):
            reasons.append("highest technical fit")
        if best["duration_weeks"] == min_dur:
            reasons.append("shortest duration")
        if best["payment_terms_days"] == max_terms:
            reasons.append("longest payment terms")
        best["best_reason"] = ("Best overall score" + (f": {', '.join(reasons)}" if reasons else
                               " balancing price, technical fit, duration and payment terms"))
    for o in out:
        if not o["eligible"]:
            o["note"] = f"Technical fit below {MIN_TECHNICAL_FIT:.0f}% — not eligible for best"
    return out


def draft_rfq_text(rfq: Dict[str, Any], tender: Dict[str, Any], requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """RFQ document text from the tender's own requirements for this package.
    Requirements are picked by the package's scope keywords (or its discipline)."""
    pattern = (rfq.get("scope") or "").strip()
    if pattern:
        words = [re.escape(w.strip()) for w in re.split(r"[,;\n]+", pattern) if w.strip()]
        rx = re.compile("|".join(words), re.IGNORECASE) if words else None
    else:
        rx = re.compile(DISCIPLINE_KEYWORDS.get(rfq.get("discipline") or "", r"$^"), re.IGNORECASE)
    picked = [r for r in requirements if rx and rx.search(f"{r.get('summary', '')} {r.get('category', '')}")][:60]
    lines = [
        f"REQUEST FOR QUOTATION — {rfq['reference']}",
        f"Tender: {tender.get('id')} — {tender.get('title') or ''}".rstrip(" —"),
        f"Package: {rfq['package_name']}" + (f" ({rfq['discipline']})" if rfq.get("discipline") else ""),
        f"Quotation due: {rfq['closes_at'][:10]}" if rfq.get("closes_at") else "Quotation due: to be confirmed",
        "",
        "1. Scope and requirements (taken from the tender documents)",
    ]
    if picked:
        for i, r in enumerate(picked, 1):
            src = f" [{r.get('source_document')}, p.{r.get('page_number')}]" if r.get("source_document") else ""
            lines.append(f"  1.{i} {r.get('summary')}{src}")
    else:
        lines.append("  (No matching requirements found — add the scope manually.)")
    lines += [
        "",
        "2. Please quote",
        f"  - Lump-sum price ({rfq.get('currency') or 'SAR'}), excluding VAT",
        "  - Duration in weeks from award",
        "  - Statement of compliance with each requirement above (deviations listed)",
        "  - Payment terms (days)",
        "",
        "3. This RFQ is confidential and for pricing purposes only.",
    ]
    return {"text": "\n".join(lines), "requirements_used": len(picked)}
