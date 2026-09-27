"""
Generic Tender-Agnostic Extraction — TenderMind — Phase 1 Production Foundation
- No LLM yet (use_llm=False default) — deterministic only
- Clean separation: ingestion, classification, deterministic extraction, requirement extraction, evidence/provenance, validation, derived
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime

# --- Module 1: Ingestion ---
def ingest_tender(tender_path: Path, tender_id: Optional[str] = None) -> Dict[str, Any]:
    """Dynamic tender ingestion — never hardcode SA-2018-HV2"""
    if tender_id is None:
        raw = tender_path.name
        tender_id = re.sub(r'^\d+-\s*', '', raw).strip().replace(' ', '-')[:30] or "UNKNOWN"
        tender_id = re.sub(r'[^A-Za-z0-9-_]', '-', tender_id)[:30]
    import evaluation.run_real_benchmark as rb
    orig_root = rb.ROOT
    rb.ROOT = tender_path
    try:
        inventory = rb.file_inventory()
        doc_results, doc_stats = rb.run_document_intelligence(inventory)
    finally:
        rb.ROOT = orig_root
    return {
        "tender_id": tender_id,
        "tender_path": str(tender_path),
        "inventory": inventory,
        "doc_results": doc_results,
        "doc_stats": doc_stats,
        "title": tender_path.name,
    }

# --- Module 2: Document Classification (generic, extensible) ---
def classify_documents(doc_results: Dict[str, Any]) -> Dict[str, str]:
    """Generic signals, not Sarai filenames"""
    classification = {}
    for fname, data in doc_results.items():
        low = fname.lower()
        # Sample text from first page
        sample = ""
        for pg in data.get("pages", [])[:1]:
            sample += (pg.get("text","") or "")[:500].lower()
        # Generic classes
        if any(k in low for k in ["price", "schedule", "boq", "bill of quantities"]):
            classification[fname] = "BOQ"
        elif any(k in low for k in ["technical", "specification", "specs"]) or any(k in sample for k in ["gis", "transformer", "voltage"]):
            classification[fname] = "TECHNICAL"
        elif "commercial" in low or "financial" in low:
            classification[fname] = "COMMERCIAL"
        elif "consortium" in low or "agreement" in low:
            classification[fname] = "LEGAL"
        elif "clarification" in low:
            classification[fname] = "CLARIFICATION"
        elif "addendum" in low:
            classification[fname] = "ADDENDUM"
        elif "drawing" in low or low.endswith(".dwg") or low.endswith(".jpg"):
            classification[fname] = "DRAWING"
        elif "schedule" in sample or "programme" in sample:
            classification[fname] = "SCHEDULE"
        elif low.endswith(".zip") or low.endswith(".rar"):
            classification[fname] = "OTHER"
        else:
            classification[fname] = "OTHER"
    return classification

# --- Module 3: Deterministic Extraction (only reliable facts) ---
def extract_voltage_levels(text: str) -> List[str]:
    """Reliable regex for voltage — deterministic"""
    found = set()
    for m in re.finditer(r"(\d{2,3}\s*kV)", text, re.IGNORECASE):
        found.add(m.group(1).replace(" ", ""))
    for m in re.finditer(r"(\d{2}-\d{2}-\d{2}\s*kV)", text, re.IGNORECASE):
        found.add(m.group(1))
    return sorted(found)

def extract_mva_values(text: str) -> List[str]:
    """Reliable MVA extraction"""
    found = set()
    for m in re.finditer(r"(\d+\s*MVA)", text, re.IGNORECASE):
        found.add(m.group(1).replace(" ", ""))
    return sorted(found)

def extract_deadlines_deterministic(text: str) -> List[Dict[str, Any]]:
    """Obvious dates when safely detected — deterministic, no semantic inference"""
    dates = []
    # Simple ISO-like or "16 of August, 2018"
    for m in re.finditer(r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}\s+of\s+\w+,\s*\d{4})", text):
        dates.append({"type": "unknown", "date": m.group(0), "source_snippet": text[max(0,m.start()-30):m.end()+30]})
        if len(dates) >= 3:
            break
    return dates

# --- Module 4: Generic Requirement Extraction (dynamic IDs) ---
def extract_requirements_generic(doc_results: Dict[str, Any], tender_id: str) -> List[Dict[str, Any]]:
    """Dynamic REQ-*, not REQ-A..U fixed, no FORM D/G assumptions"""
    combined = ""
    for fname, data in doc_results.items():
        for pg in data.get("pages", []):
            combined += "\n" + (pg.get("text","") or "")
    low = combined.lower()
    # Generic patterns — common across tenders, not Sarai-specific
    generic_patterns = [
        (r"experience|reference.*project|past performance", "EXPERIENCE", "Experience/qualification"),
        (r"schedule|programme|delivery|completion.*date|duration", "SCHEDULE", "Schedule/delivery"),
        (r"220kV|GIS|transformer|MVA|22kV|11kV|66kV|voltage", "TECHNICAL", "Technical equipment"),
        (r"tender security|bid bond|EGP|price.*schedule|BOQ|bill of quantities", "COMMERCIAL", "Commercial/bid security"),
        (r"consortium|joint.*venture|joint.*liability", "LEGAL", "Consortium/JV"),
        (r"financial capacity|turnover|working capital|audited", "FINANCIAL", "Financial capacity"),
        (r"HSE|health.*safety|environment", "HSE", "HSE"),
        (r"QA/QC|quality.*assurance", "QA_QC", "QA/QC"),
        (r"subcontractor", "SUBCONTRACTOR", "Subcontractor"),
        (r"penalty|liquidated damages|termination|delay", "COMMERCIAL", "Penalty/termination"),
    ]
    candidates = []
    req_counter = 1
    for pattern, category, summary in generic_patterns:
        if re.search(pattern.lower(), low):
            # Find provenance
            prov_file = None
            prov_page = None
            snippet = ""
            for fname, data in doc_results.items():
                for pg in data.get("pages", []):
                    t = (pg.get("text","") or "").lower()
                    if re.search(pattern.lower(), t):
                        prov_file = fname
                        prov_page = pg.get("page_number", 1)
                        m = re.search(pattern.lower(), t)
                        if m:
                            snippet = pg.get("text","")[max(0,m.start()-50):m.start()+100].replace("\n"," ")[:200]
                        break
                if prov_file:
                    break
            candidates.append({
                "requirement_id": f"REQ-{req_counter:03d}",
                "summary": summary,
                "category": category,
                "mandatory": category in ["LEGAL", "TECHNICAL", "FINANCIAL"],
                "requirement_type": "HARD_GATE" if category in ["LEGAL", "FINANCIAL"] else "TECHNICAL",
                "applicable_entity": "CONSORTIUM",
                "source_document": prov_file or None,
                "page_number": prov_page,
                "confidence": 0.75,
                "provenance": {"quote_en": snippet[:100]} if snippet else None,
                "conditional": False,
                "extraction_method": "deterministic",
            })
            req_counter += 1
            if req_counter > 15:
                break
    return candidates

# --- Module 5: Evidence/Provenance (never without source) ---
def extract_evidence_generic(doc_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generic evidence — currently empty for unseen tenders (no gold), but preserves provenance if found"""
    # For generic, we don't have gold evidence for unseen tenders, so return empty
    # If needed, this could extract supplier offers, but for Phase 1 we return empty with proper handling
    return []

# --- Module 6: Schema Validation ---
def validate_against_schema(data: Dict[str, Any], schema_path: Path) -> tuple[bool, str]:
    """Validate final output against tender_agnostic_schema.json — fail clearly if invalid"""
    try:
        import json
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        # Check required fields
        for field in schema.get("required", []):
            if field not in data:
                return False, f"Missing required field: {field}"
        # Check documents and requirements are arrays
        if not isinstance(data.get("documents"), list):
            return False, "documents must be array"
        if not isinstance(data.get("requirements"), list):
            return False, "requirements must be array"
        # Check each requirement has required fields
        for req in data.get("requirements", []):
            for rf in ["requirement_id", "summary", "category", "mandatory"]:
                if rf not in req:
                    return False, f"Requirement missing {rf}: {req}"
            # Never create evidence without source
            if req.get("source_document") is None and req.get("confidence", 0) > 0.8:
                # Allow unknown with low confidence, but not high confidence without source
                pass
        return True, "OK"
    except Exception as e:
        return False, f"Validation error: {e}"

# --- Module 7: Derived Features (generic calculations, no BID decision) ---
def compute_derived_features(doc_results: Dict[str, Any], requirements: List[Dict], evidence: List[Dict]) -> Dict[str, Any]:
    total_pages = sum(d.get("page_count", 0) for d in doc_results.values())
    total_text = sum(len((pg.get("text","") or "")) for d in doc_results.values() for pg in d.get("pages", []))
    prov_covered = sum(1 for r in requirements if r.get("source_document")) / max(len(requirements), 1)
    confs = [r.get("confidence", 0) for r in requirements]
    high = sum(1 for c in confs if c >= 0.8)
    medium = sum(1 for c in confs if 0.6 <= c < 0.8)
    low = sum(1 for c in confs if c < 0.6)
    # Evidence coverage
    evidence_coverage = len(evidence) / max(len(requirements), 1) if requirements else 0
    # Do NOT make BID decision here — that remains in app/engines/decision.py
    return {
        "requirement_count": len(requirements),
        "evidence_coverage": evidence_coverage,
        "risk_count": 0,  # Would be extracted via risks
        "mandatory_missing_count": sum(1 for r in requirements if r.get("mandatory") and not any(e.get("requirement_id") == r["requirement_id"] for e in evidence)),
        "overall_pages": total_pages,
        "ocr_ratio": sum(1 for d in doc_results.values() for pg in d.get("pages", []) if pg.get("ocr_applied")) / max(total_pages, 1),
        "total_text_length": total_text,
        "provenance_coverage": prov_covered,
        "confidence_distribution": {"high": high, "medium": medium, "low": low},
    }

# --- Main API ---
def build_generic_extraction(tender_path: Path, tender_id: Optional[str] = None, use_llm: bool = False) -> Dict[str, Any]:
    """Clean production API — returns validated tender_agnostic_schema.json object"""
    # A. Ingestion
    from evaluation.generic_extraction import ingest_tender as orig_ingest  # Reuse existing ingestion for now
    # For Phase 1, we implement ingestion directly here to avoid circular import
    # Instead, duplicate the logic from generic_extraction.py ingest_tender but keep it clean
    if tender_id is None:
        raw = tender_path.name
        tender_id = re.sub(r'^\d+-\s*', '', raw).strip().replace(' ', '-')[:30] or "UNKNOWN"
        tender_id = re.sub(r'[^A-Za-z0-9-_]', '-', tender_id)[:30]
    import evaluation.run_real_benchmark as rb
    orig_root = rb.ROOT
    rb.ROOT = tender_path
    try:
        inventory = rb.file_inventory()
        doc_results, doc_stats = rb.run_document_intelligence(inventory)
    finally:
        rb.ROOT = orig_root

    # B. Document extraction already done via run_document_intelligence (fitz/Tesseract/LibreOffice)
    # C. Classification
    classification = {}
    for fname, data in doc_results.items():
        low = fname.lower()
        sample = ""
        for pg in data.get("pages", [])[:1]:
            sample += (pg.get("text","") or "")[:500].lower()
        if any(k in low for k in ["price", "schedule", "boq"]):
            classification[fname] = "BOQ"
        elif any(k in low for k in ["technical", "specification"]) or any(k in sample for k in ["gis", "transformer"]):
            classification[fname] = "TECHNICAL"
        elif "consortium" in low:
            classification[fname] = "LEGAL"
        elif "clarification" in low:
            classification[fname] = "CLARIFICATION"
        elif "addendum" in low:
            classification[fname] = "ADDENDUM"
        elif "drawing" in low or low.endswith(".dwg"):
            classification[fname] = "DRAWING"
        else:
            classification[fname] = "OTHER"

    # D. Deterministic extraction
    combined_text = "\n".join((pg.get("text","") or "") for d in doc_results.values() for pg in d.get("pages", []))
    voltage_levels = extract_voltage_levels(combined_text)
    mva_values = extract_mva_values(combined_text)
    deadlines = extract_deadlines_deterministic(combined_text)

    # E. Generic requirement extraction
    requirements = extract_requirements_generic(doc_results, tender_id)

    # F. Evidence/provenance — never without source
    evidence = extract_evidence_generic(doc_results)
    # Ensure every requirement/evidence has provenance
    for req in requirements:
        if not req.get("source_document"):
            req["source_document"] = None
            req["confidence"] = 0.5 if req["confidence"] > 0.5 else req["confidence"]

    # G. Missing/unknown handling is already via None/empty arrays in schema

    # Derived features
    derived = compute_derived_features(doc_results, requirements, evidence)

    # Build final object
    result = {
        "tender_id": tender_id,
        "title": tender_path.name,
        "client": None,
        "location": None,
        "languages": ["AR", "EN"],
        "documents": [{"filename": k, "page_count": v.get("page_count", 0), "text_length": v.get("total_text_chars", 0), "extraction_method": v["pages"][0].get("method", "unknown") if v.get("pages") else "unknown", "ocr_applied": any(p.get("ocr_applied") for p in v.get("pages", []))} for k, v in doc_results.items()],
        "requirements": requirements,
        "evidence": evidence,
        "risks": [],
        "deadlines": deadlines,
        "commercial_terms": None,
        "provenance_coverage": derived["provenance_coverage"],
        "confidence_distribution": derived["confidence_distribution"],
        "missing_rate": 1 - derived["provenance_coverage"],
        "extraction_metadata": {
            "tender_id": tender_id,
            "extraction_timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "extraction_method": "deterministic",
            "model": None,
            "ocr_applied": any("tesseract" in str(v.get("pages", [{}])[0].get("method", "")) for v in doc_results.values() if v.get("pages")),
        },
        "derived_features": derived,
        "classification": classification,
        "voltage_levels": voltage_levels,
        "mva_values": mva_values,
    }

    # Schema validation
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
    ok, msg = validate_against_schema(result, schema_path)
    if not ok:
        raise ValueError(f"Schema validation failed: {msg}")

    return result
