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

# Generic deterministic signals — shared by production extraction and evaluation selectors.
# Must remain generic procurement terminology, no tender-specific sentences.
GENERIC_PATTERNS = [
    (r"experience|reference.*project|past performance", "EXPERIENCE", "Experience/qualification"),
    (r"schedule|programme|delivery|completion.*date|duration", "SCHEDULE", "Schedule/delivery"),
    (r"220kV|GIS|transformer|MVA|22kV|11kV|66kV|voltage", "TECHNICAL", "Technical equipment"),
    (r"tender security|bid bond|EGP|price.*schedule|BOQ|bill of quantities", "COMMERCIAL", "Commercial/bid security"),
    (r"consortium|joint.*venture|joint.*liability", "LEGAL", "Consortium/JV"),
    (r"financial|turnover|working capital|audited", "FINANCIAL", "Financial capacity"),
    (r"HSE|health.*safety|environment", "HSE", "HSE"),
    (r"QA/QC|quality.*assurance", "QA_QC", "QA/QC"),
    (r"subcontractor", "SUBCONTRACTOR", "Subcontractor"),
    (r"penalty|liquidated damages|termination|delay", "COMMERCIAL", "Penalty/termination"),
    (r"personnel|key personnel|project manager|qualified staff|technical staff|experienced personnel", "PERSONNEL", "Personnel"),
]

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
    """Obvious dates when safely detected — deterministic, context-sensitive (Stage 3A hardening)"""
    dates = []
    # Require deadline context within 50 chars before/after the date token
    context_terms = r"deadline|submission|bid submission|tender submission|closing date|due date|delivery date|completion date|clarification deadline|tender opening|validity|opening date|bid validity|offer validity"
    # Use word boundaries to avoid matching voltage substrings like 20/22/22 inside 220/22/22
    for m in re.finditer(r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{1,2}\s+of\s+\w+,\s*\d{4})\b", text):
        raw = m.group(1)
        snippet = text[max(0, m.start()-50):m.end()+50]
        if not re.search(context_terms, snippet, re.IGNORECASE):
            continue
        # Validate month/day for slash/dash dates (avoid 20/22/22 where month=22)
        if "/" in raw or "-" in raw:
            # Normalize separators
            parts = re.split(r"[\/\-]", raw)
            if len(parts) >= 2:
                try:
                    day = int(parts[0])
                    month = int(parts[1])
                    if not (1 <= day <= 31 and 1 <= month <= 12):
                        continue
                except:
                    continue
        dates.append({"type": "unknown", "date": raw, "source_snippet": snippet.strip()[:120]})
        if len(dates) >= 3:
            break
    return dates

def extract_commercial_terms_deterministic(text: str) -> Optional[Dict[str, Any]]:
    """Minimal deterministic commercial extraction — only when explicitly present, no inference"""
    # Search for each field independently, return None if none found (per schema, commercial_terms can be null)
    found = {}
    # Currency: look for explicit currency codes near commercial terms
    # Use word boundaries, generic currencies
    curr_match = re.search(r"\b(EGP|USD|EUR|SAR|GBP|L\.E|LE)\b", text, re.IGNORECASE)
    if curr_match:
        # Verify currency is near commercial context (within 100 chars of tender security/price/payment or alone is okay for currency)
        # For minimal, accept any explicit currency code found (conservative: require commercial context for non-EGP?)
        # Keep simple: if currency found, populate
        found["currency"] = curr_match.group(1).upper().replace(".", "").strip()
        # Normalize L.E/LE to EGP
        if found["currency"] in ("L", "LE", "L.E"):
            found["currency"] = "EGP"
        if found["currency"] == "L E":
            found["currency"] = "EGP"
    # Payment terms: look for payment.*term|advance.*payment|payment.*schedule etc.
    pay_match = re.search(r"(payment[^.\n]{0,60}term|advance[^.\n]{0,40}payment|payment[^.\n]{0,40}schedule|\d+\s*%[^.\n]{0,30}advance|\d+\s*%[^.\n]{0,30}delivery|\d+\s*%[^.\n]{0,30}retention)", text, re.IGNORECASE)
    if pay_match:
        snippet = pay_match.group(0).strip()[:120].replace("\n", " ")
        found["payment"] = snippet
    # Tender security / bid bond: look for explicit phrase and nearby value
    sec_match = re.search(r"(tender security|bid bond|bid security)[^.\n]{0,80}(\d[\d,\.]*\s*(EGP|USD|EUR|SAR|L\.E)?)", text, re.IGNORECASE)
    if sec_match:
        snippet = sec_match.group(0).strip()[:150].replace("\n", " ")
        # Use price_schedules field for tender security per schema (best fit), keep payment for payment terms
        found["price_schedules"] = snippet
    # Validity period: look for validity.*\d+ days|valid for \d+ days
    valid_match = re.search(r"(validity[^.\n]{0,40}\d+\s*days|valid for \d+\s*days|bid validity[^.\n]{0,40}\d+\s*days|offer validity[^.\n]{0,40}\d+\s*days|tender validity[^.\n]{0,40}\d+\s*days)", text, re.IGNORECASE)
    if valid_match:
        snippet = valid_match.group(0).strip()[:120].replace("\n", " ")
        # If price_schedules already used for tender security, append validity there or use payment
        if "price_schedules" not in found:
            found["price_schedules"] = snippet
        elif "payment" not in found:
            found["payment"] = snippet
        else:
            # Both occupied, append to price_schedules
            found["price_schedules"] = (found["price_schedules"] + " | " + snippet)[:200]
    if not found:
        return None
    # Ensure at least one of the schema fields is populated; return with null for missing per schema
    return {
        "price_schedules": found.get("price_schedules"),
        "payment": found.get("payment"),
        "currency": found.get("currency"),
    }

# --- Module 4: Generic Requirement Extraction (dynamic IDs) ---
def extract_requirements_generic(doc_results: Dict[str, Any], tender_id: str) -> List[Dict[str, Any]]:
    """Dynamic REQ-*, not REQ-A..U fixed, no FORM D/G assumptions — conservative, candidates only"""
    combined = ""
    for fname, data in doc_results.items():
        for pg in data.get("pages", []):
            combined += "\n" + (pg.get("text","") or "")
    low = combined.lower()
    # Generic patterns — common across tenders, not Sarai-specific — candidates, not authoritative
    # Stage 3A: FINANCIAL broadened to "financial" (was "financial capacity" too narrow), PERSONNEL added
    # GENERIC_PATTERNS is module-level for reuse by evaluation selectors (Stage 3C) — same list, no behavior change.
    generic_patterns = GENERIC_PATTERNS
    candidates = []
    req_counter = 1
    for pattern, category, summary in generic_patterns:
        if re.search(pattern.lower(), low):
            # Find provenance — never fabricate
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
            # Do NOT guess mandatory/applicable — leave null/unknown if not safely determinable
            # For Phase 1, mark all as not mandatory (conservative) and applicable_entity as null
            candidates.append({
                "requirement_id": f"REQ-{req_counter:03d}",
                "summary": summary + " (candidate — deterministic, not semantic)",
                "category": category,
                "mandatory": None,  # Unknown — do not guess based on category
                "requirement_type": "TECHNICAL",  # Generic, not HARD_GATE
                "applicable_entity": None,  # Unknown — do not hardcode CONSORTIUM
                "source_document": prov_file,  # None if not found — never fabricate
                "page_number": prov_page,
                "confidence": 0.55,  # Lower for candidates
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
def _doc_status(v: Dict[str, Any]) -> str:
    """Keep UNSUPPORTED distinct from FAILED (a .dwg is not an extraction error)."""
    if str(v.get("status", "")).upper() == "UNSUPPORTED":
        return "UNSUPPORTED"
    chars = v.get("total_text_chars", 0)
    return "COMPLETE" if chars > 100 else "PARTIAL" if chars > 0 else "FAILED"


def validate_against_schema(data: Dict[str, Any], schema_path: Path) -> tuple[bool, str]:
    """Real JSON Schema validation — uses jsonschema if available, otherwise robust fallback"""
    try:
        import json
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        # Try real jsonschema validation
        try:
            import jsonschema
            jsonschema.validate(instance=data, schema=schema)
            return True, "OK (jsonschema)"
        except ImportError:
            # Fallback: robust manual validation (not just top-level)
            # Check required fields
            for field in schema.get("required", []):
                if field not in data:
                    return False, f"Missing required field: {field}"
            # Check documents
            if not isinstance(data.get("documents"), list):
                return False, "documents must be array"
            for doc in data.get("documents", []):
                if "filename" not in doc or "page_count" not in doc:
                    return False, f"Document missing required fields: {doc}"
                if not isinstance(doc["page_count"], int):
                    return False, f"page_count must be integer: {doc}"
                if doc.get("extraction_method") not in ["tesseract", "libreoffice", "fitz", "xlrd", "openpyxl", "docx", "unknown", None]:
                    # Allow any string, but check if present
                    pass
            # Check requirements
            if not isinstance(data.get("requirements"), list):
                return False, "requirements must be array"
            for req in data.get("requirements", []):
                for rf in ["requirement_id", "summary", "category", "mandatory"]:
                    if rf not in req:
                        return False, f"Requirement missing {rf}: {req}"
                # Check types
                if not isinstance(req["requirement_id"], str) or not re.match(r"^REQ-[A-Z0-9-_]+$", req["requirement_id"]):
                    return False, f"Invalid requirement_id pattern: {req['requirement_id']}"
                if req["category"] not in ["LEGAL", "TECHNICAL", "EXPERIENCE", "EQUIPMENT", "FINANCIAL", "SCHEDULE", "COMMERCIAL", "HSE", "QA_QC", "PERSONNEL", "SUBCONTRACTOR", "SUBMISSION"]:
                    return False, f"Invalid category: {req['category']}"
                if req["mandatory"] is not None and not isinstance(req["mandatory"], bool):
                    return False, f"mandatory must be boolean or null: {req['mandatory']}"
                if not isinstance(req["confidence"], (int, float)) or not 0 <= req["confidence"] <= 1:
                    return False, f"confidence must be 0-1: {req['confidence']}"
                if req.get("extraction_method") not in ["deterministic", "llm", "hybrid", None]:
                    return False, f"Invalid extraction_method: {req.get('extraction_method')}"
            # Check deadlines
            for dl in data.get("deadlines", []):
                if dl.get("type") not in ["submission", "opening", "validity", "completion", "unknown", "unclassified", None]:
                    return False, f"Invalid deadline type: {dl.get('type')}"
                if dl.get("date") is not None and not isinstance(dl["date"], str):
                    return False, f"deadline date must be string or null: {dl}"
            # Check risks
            for risk in data.get("risks", []):
                if risk.get("severity") not in ["HIGH", "MEDIUM", "LOW", None]:
                    return False, f"Invalid risk severity: {risk.get('severity')}"
            # Check provenance
            for req in data.get("requirements", []):
                if req.get("source_document") is None and req.get("confidence", 0) > 0.8:
                    return False, f"High confidence requirement without source: {req['requirement_id']}"
            return True, "OK (fallback)"
        except Exception as e:
            # jsonschema validation error
            return False, f"Schema validation failed: {e}"
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
    # A. Ingestion — reuse canonical ingest_tender (no duplication, no self-import)
    ingested = ingest_tender(tender_path, tender_id)
    tender_id = ingested["tender_id"]
    doc_results = ingested["doc_results"]
    doc_stats = ingested["doc_stats"]
    inventory = ingested["inventory"]

    # C. Classification — reuse canonical function (no duplication)
    classification = classify_documents(doc_results)

    # D. Deterministic extraction — only reliable facts
    combined_text = "\n".join((pg.get("text","") or "") for d in doc_results.values() for pg in d.get("pages", []))
    voltage_levels = extract_voltage_levels(combined_text)
    mva_values = extract_mva_values(combined_text)
    deadlines = extract_deadlines_deterministic(combined_text)
    # Languages — detect, not hardcoded
    has_ar = any('\u0600' <= c <= '\u06FF' for c in combined_text)
    has_en = any(c.isalpha() and ord(c) < 128 for c in combined_text)
    languages = []
    if has_ar:
        languages.append("AR")
    if has_en:
        languages.append("EN")
    if not languages:
        languages = []

    # E. Generic requirement extraction — candidates only
    requirements = extract_requirements_generic(doc_results, tender_id)

    # F. Evidence/provenance — never without source (already ensured in extract_requirements_generic)
    evidence = extract_evidence_generic(doc_results)

    # G. Missing/unknown handling — already via None/empty arrays

    # Derived features — generic, no BID decision
    derived = compute_derived_features(doc_results, requirements, evidence)

    # Build final object — with proper handling for unknown
    result = {
        "tender_id": tender_id,
        "title": ingested["title"],
        "client": None,  # Unknown in Phase 1 — not guessed
        "location": None,  # Unknown
        "languages": languages,
        "documents": [
            {
                "filename": k,
                "page_count": v.get("page_count", 0),
                "text_length": v.get("total_text_chars", 0),
                "extraction_method": v["pages"][0].get("method", "unknown") if v.get("pages") else "unknown",
                "extraction_status": _doc_status(v),
                "document_type": classification.get(k),
                "document_status": _doc_status(v),
                "ocr_applied": any(p.get("ocr_applied") for p in v.get("pages", [])),
                "provenance_status": "COMPLETE" if any(p.get("page_number") for p in v.get("pages", [])) else "MISSING",
            } for k, v in doc_results.items()
        ],
        "requirements": requirements,
        "evidence": evidence,
        "risks": [],  # Not analyzed in Phase 1 — empty, not 0 as if analyzed
        "deadlines": deadlines,
        "commercial_terms": extract_commercial_terms_deterministic(combined_text),
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

    # Schema validation — real
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
    ok, msg = validate_against_schema(result, schema_path)
    if not ok:
        raise ValueError(f"Schema validation failed: {msg}")

    return result
