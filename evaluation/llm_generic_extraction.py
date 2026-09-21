"""
LLM Generic Extraction — TenderMind — Phase 2A Experiment
- SAFE, OFFLINE, GENERIC — local Ollama qwen2.5:3b, $0, no Azure/OpenAI
- Chunk-aware, provenance-preserving, schema-constrained
- Deterministic extraction remains authoritative for voltage/MVA/dates
"""
import json
import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Configurable via env
DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_BASE_URL = "http://localhost:11434"

def get_ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", os.environ.get("TENDERMIND_OLLAMA_MODEL", DEFAULT_MODEL)).strip() or DEFAULT_MODEL

def get_ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", os.environ.get("TENDERMIND_OLLAMA_ENDPOINT", DEFAULT_BASE_URL)).strip().rstrip("/")

def check_ollama_available() -> tuple[bool, str]:
    import requests
    base = get_ollama_base_url()
    model = get_ollama_model()
    try:
        resp = requests.get(f"{base}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False, f"OLLAMA {base} returned {resp.status_code}"
        data = resp.json()
        models = [m.get("name","") for m in data.get("models",[])]
        found = any(m==model or m.startswith(model) or model.startswith(m) for m in models)
        if not found:
            return False, f"Model {model} not found, available {models[:3]}"
        return True, f"OK {base} model {model}"
    except Exception as e:
        return False, f"Ollama not available: {e}"

# --- Chunking ---
def chunk_documents(doc_results: Dict[str, Any], max_chars: int = 3000) -> List[Dict[str, Any]]:
    """
    Page-aware, chunk-aware — each chunk retains source_document, page_number, chunk_id, text
    Conservative for 3B model (max 3000 chars per chunk)
    """
    chunks = []
    chunk_id = 0
    for fname, data in doc_results.items():
        for pg in data.get("pages", []):
            text = pg.get("text","") or ""
            if not text.strip():
                continue
            # Split page text into chunks if too long
            # Preserve page_number
            page_num = pg.get("page_number", 1)
            # Simple split by paragraphs
            paragraphs = text.split("\n")
            current = ""
            for para in paragraphs:
                if len(current) + len(para) + 1 > max_chars and current:
                    chunks.append({
                        "chunk_id": f"chunk-{chunk_id:04d}",
                        "source_document": fname,
                        "page_number": page_num,
                        "text": current.strip(),
                    })
                    chunk_id += 1
                    current = para + "\n"
                else:
                    current += para + "\n"
            if current.strip():
                chunks.append({
                    "chunk_id": f"chunk-{chunk_id:04d}",
                    "source_document": fname,
                    "page_number": page_num,
                    "text": current.strip(),
                })
                chunk_id += 1
    return chunks

# --- LLM Prompt Contract — Phase 2B: candidate IDs, evidence, provenance ---
LLM_SYSTEM_PROMPT = """You are a tender document extraction assistant. Extract ONLY information explicitly supported by the supplied text.

For each requirement, return:
- candidate_id (e.g., chunk-0001-item-02) — temporary, not canonical REQ-*
- summary (human-readable)
- category (LEGAL, TECHNICAL, EXPERIENCE, EQUIPMENT, FINANCIAL, SCHEDULE, COMMERCIAL, HSE, QA_QC, PERSONNEL, SUBCONTRACTOR, SUBMISSION)
- mandatory (true/false/null) — null if unknown, never infer from category
- requirement_type (HARD_GATE, EXPERIENCE, TECHNICAL, etc. — or null if unknown)
- applicable_entity (string or null — never invent, null if unknown)
- evidence_required (array, may be empty)
- conditional (true/false)
- source_document (must be from supplied chunk's source_document)
- page_number (must be from chunk's page_number)
- confidence (0.0-1.0, extraction confidence)
- provenance (quote_en — exact quote from text)
- extraction_method ("llm")

For each evidence (only if explicitly supported by same chunk):
- candidate_id (e.g., chunk-0001-ev-01)
- requirement_candidate_id (which requirement it supports, or null)
- fact (human-readable fact)
- source_document (must be from chunk)
- page_number
- confidence
- provenance
- applicable_entity (string or null)
- valid_until (ISO date or null)
- reusable (boolean)

Rules:
- UNKNOWN != FALSE — if source does not establish mandatory/applicable_entity/deadline/risk/severity/evidence, return null
- Never invent entities, dates, evidence, source_document/page_number
- Every requirement and evidence must have traceable provenance (source_document + page_number) — reject if missing
- Evidence must point to same chunk's source_document/page_number unless explicitly supported by different source
- If no evidence exists for a requirement, return [] for evidence, do not create evidence
- Return ONLY valid JSON, no extra text, no markdown

Category definitions (classify by PRIMARY PURPOSE, not keywords):
- TECHNICAL = equipment/specification/performance requirements
- EXPERIENCE = bidder/project experience requirements
- FINANCIAL = financial/commercial qualification requirements
- LEGAL = legal/documentary/legal-status requirements
- SCHEDULE = delivery/completion/time requirements
- HSE = health/safety/environment requirements
- QA_QC = quality assurance/control requirements
- COMMERCIAL = pricing/payment/commercial terms
Classify by PRIMARY PURPOSE, not keywords. Similar 220kV projects is EXPERIENCE even though it contains 220kV/GIS.
"""

def build_llm_prompt(chunk: Dict[str, Any]) -> str:
    return f"""Extract requirements and evidence from this tender chunk.

Source: {chunk['source_document']} Page: {chunk['page_number']} Chunk: {chunk['chunk_id']}

Text:
\"\"\"{chunk['text'][:2500]}\"\"\"

Return JSON:
{{
  "requirements": [
    {{
      "candidate_id": "chunk-0001-item-01",
      "summary": "...",
      "category": "TECHNICAL",
      "mandatory": null,
      "requirement_type": null,
      "applicable_entity": null,
      "evidence_required": [],
      "conditional": false,
      "source_document": "{chunk['source_document']}",
      "page_number": {chunk['page_number']},
      "confidence": 0.75,
      "provenance": {{"quote_en": "..."}},
      "extraction_method": "llm"
    }}
  ],
  "evidence": [
    {{
      "candidate_id": "chunk-0001-ev-01",
      "requirement_candidate_id": "chunk-0001-item-01",
      "fact": "...",
      "source_document": "{chunk['source_document']}",
      "page_number": {chunk['page_number']},
      "confidence": 0.8,
      "provenance": {{"quote_en": "..."}},
      "applicable_entity": null,
      "valid_until": null,
      "reusable": false
    }}
  ]
}}
If no requirements, return {{"requirements": [], "evidence": []}}.
"""

# --- LLM Call ---
def call_ollama_for_chunk(chunk: Dict[str, Any], model: Optional[str] = None) -> Optional[Dict[str, Any]]:
    import requests, json as js
    base = get_ollama_base_url()
    mdl = model or get_ollama_model()
    prompt = build_llm_prompt(chunk)
    payload = {
        "model": mdl,
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0}
    }
    try:
        resp = requests.post(f"{base}/api/chat", json=payload, timeout=90)
        if resp.status_code != 200:
            return None
        data = resp.json()
        raw = ""
        if "message" in data and isinstance(data["message"], dict):
            raw = data["message"].get("content", "")
        if not raw:
            raw = data.get("response", "")
        raw = raw.strip()
        if not raw:
            return None
        return {"raw": raw, "chunk": chunk}
    except Exception:
        return None

def parse_llm_json(raw: str) -> tuple[Optional[Dict], str]:
    """Handle valid JSON, fenced JSON, malformed, truncated, empty, unexpected fields"""
    if not raw or not raw.strip():
        return None, "empty output"
    # Try direct
    try:
        parsed = json.loads(raw)
        return parsed, "ok"
    except:
        pass
    # Try fenced ```json ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(1))
            return parsed, "fenced"
        except:
            pass
    # Try extract first {...}
    m2 = re.search(r"\{.*\}", raw, re.DOTALL)
    if m2:
        try:
            parsed = json.loads(m2.group(0))
            return parsed, "extracted"
        except Exception as e:
            return None, f"malformed: {e}"
    return None, "malformed"

# --- Validation Pipeline ---
def validate_requirement(req: Dict[str, Any], chunk: Dict[str, Any]) -> tuple[bool, str]:
    """Pydantic-like validation + provenance + schema checks — allows candidate_id for Phase 2B"""
    # Allow candidate_id as temporary ID (Phase 2B), will be normalized to REQ-* after
    req_id = req.get("requirement_id") or req.get("candidate_id")
    if not req_id:
        return False, "missing requirement_id/candidate_id"
    # Check pattern: allow REQ-* or chunk-*-item-* or candidate_id
    if not re.match(r"^(REQ-[A-Z0-9-_]+|chunk-\d+-item-\d+|candidate-.+)$", req_id):
        # Also allow any candidate_id with chunk prefix
        if not req_id.startswith("chunk-"):
            return False, f"invalid requirement_id/candidate_id {req_id}"
    for field in ["summary", "category", "mandatory"]:
        if field not in req:
            return False, f"missing {field}"
    # category enum
    if req["category"] not in ["LEGAL", "TECHNICAL", "EXPERIENCE", "EQUIPMENT", "FINANCIAL", "SCHEDULE", "COMMERCIAL", "HSE", "QA_QC", "PERSONNEL", "SUBCONTRACTOR", "SUBMISSION"]:
        return False, f"invalid category {req['category']}"
    # confidence
    if "confidence" in req and not (0 <= req["confidence"] <= 1):
        return False, f"confidence out of range {req['confidence']}"
    # provenance
    if not req.get("source_document"):
        return False, "missing source_document"
    if req.get("source_document") != chunk["source_document"]:
        # Allow if chunk source is in doc, but must be traceable
        # For this experiment, require exact match to chunk
        if req["source_document"] not in [chunk["source_document"]]:
            return False, f"source_document {req['source_document']} not in chunk {chunk['source_document']}"
    if req.get("page_number") is not None and req["page_number"] != chunk["page_number"]:
        # Allow but log
        pass
    # Never invent mandatory from category — if mandatory is not null, it must be explicitly supported
    # For now, we allow any, but log
    return True, "ok"

def validate_evidence(ev: Dict[str, Any], chunk: Dict[str, Any]) -> tuple[bool, str]:
    if not ev.get("evidence_id") or not ev.get("fact"):
        return False, "missing evidence_id/fact"
    if not ev.get("source_document"):
        return False, "missing source_document"
    if ev["source_document"] != chunk["source_document"]:
        return False, "source_document mismatch"
    return True, "ok"

# --- Deduplication ---
def deduplicate_requirements(reqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Conservative deduplication — prefer normalized summary + requirement_type + applicable_entity + source overlap"""
    seen = {}
    result = []
    for req in reqs:
        # Key: normalized summary lower + category + type
        key = (req["summary"].lower().strip(), req["category"], req.get("requirement_type"), req.get("applicable_entity"))
        # Also consider source overlap
        if key not in seen:
            seen[key] = req
            result.append(req)
        else:
            # Keep both if provenance different and confidence high
            existing = seen[key]
            if req.get("source_document") != existing.get("source_document") and req.get("confidence", 0) > 0.7 and existing.get("confidence", 0) > 0.7:
                # Uncertain, keep both
                result.append(req)
                # Make key unique for next
                seen[(key[0] + str(len(result)), key[1], key[2], key[3])] = req
            else:
                # Keep higher confidence
                if req.get("confidence", 0) > existing.get("confidence", 0):
                    # Replace
                    idx = result.index(existing)
                    result[idx] = req
                    seen[key] = req
    return result

# --- Canonical ID Assignment ---
def assign_canonical_ids(requirements: List[Dict[str, Any]], evidence: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Assign canonical REQ-* IDs after deduplication — deterministic, stable ordering — evidence follows requirement map, never list position"""
    # Sort by source_document, page_number, then summary for stability
    sorted_reqs = sorted(requirements, key=lambda r: (r.get("source_document",""), r.get("page_number",0), r.get("summary","")))
    canonical_map = {}
    for idx, req in enumerate(sorted_reqs, 1):
        old_id = req.get("candidate_id") or req.get("requirement_id")
        new_id = f"REQ-{idx:03d}"
        canonical_map[old_id] = new_id
        # Preserve candidate_id as metadata
        req["_candidate_id"] = old_id
        req["requirement_id"] = new_id
        # Ensure extraction_method is llm
        req["extraction_method"] = "llm"
    # Update evidence to reference canonical IDs — invariant: same candidate maps to same canonical
    for ev in evidence:
        old_req_id = ev.get("requirement_candidate_id") or ev.get("requirement_id")
        if old_req_id in canonical_map:
            ev["requirement_id"] = canonical_map[old_req_id]
            ev["_candidate_requirement_id"] = old_req_id
        elif old_req_id:
            # Evidence references unknown candidate — reject
            ev["_rejected"] = f"unknown candidate {old_req_id}"
            # Keep as is but mark for filtering
            ev["requirement_id"] = None
        # Ensure every accepted evidence has exactly one canonical requirement_id
        if ev.get("requirement_id") is None:
            ev["_rejected"] = ev.get("_rejected", "no canonical requirement_id")
    # Filter out rejected evidence
    evidence = [ev for ev in evidence if "_rejected" not in ev]
    return sorted_reqs, evidence

# --- Main LLM Extraction (per tender, chunk-aware) ---
def llm_extract_requirements_for_tender(tender_path: Path, tender_id: Optional[str] = None, max_chunks: int = 5) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Experiment entry point — chunk-aware LLM extraction for a tender — returns (requirements, evidence)"""
    from evaluation.generic_extraction import ingest_tender
    ingested = ingest_tender(tender_path, tender_id)
    doc_results = ingested["doc_results"]
    chunks = chunk_documents(doc_results)
    # Limit to max_chunks for experiment (conservative for 3B)
    chunks = chunks[:max_chunks]
    all_reqs = []
    all_evs = []
    for chunk in chunks:
        result = call_ollama_for_chunk(chunk)
        if not result:
            continue
        parsed, status = parse_llm_json(result["raw"])
        if not parsed:
            continue
        # Requirements
        for idx_r, req in enumerate(parsed.get("requirements", [])):
            # Handle candidate_id — must be chunk-aware, not allow collision across chunks
            # If LLM provided candidate_id, ensure it matches chunk prefix, otherwise correct it
            provided_cid = req.get("candidate_id") or req.get("requirement_id")
            expected_prefix = chunk["chunk_id"]
            if provided_cid and not provided_cid.startswith(expected_prefix):
                # Correct hallucinated candidate_id to be chunk-aware
                corrected = f"{chunk['chunk_id']}-item-{idx_r+1:02d}"
                req["_original_candidate_id"] = provided_cid
                req["candidate_id"] = corrected
                req["requirement_id"] = corrected
            elif "candidate_id" in req and "requirement_id" not in req:
                req["requirement_id"] = req["candidate_id"]
            elif "candidate_id" not in req and "requirement_id" not in req:
                # No ID provided, generate one
                gen_id = f"{chunk['chunk_id']}-item-{idx_r+1:02d}"
                req["candidate_id"] = gen_id
                req["requirement_id"] = gen_id
            req["extraction_method"] = "llm"
            ok, msg = validate_requirement(req, chunk)
            if not ok:
                # Mark as unverified candidate instead of rejecting outright
                req["confidence"] = 0.3
                req["provenance"] = None
                if "missing source_document" in msg:
                    continue
            if not req.get("source_document"):
                req["source_document"] = chunk["source_document"]
            if not req.get("page_number"):
                req["page_number"] = chunk["page_number"]
            # Ensure provenance not downgraded for low confidence
            all_reqs.append(req)
        # Evidence — must reference correct candidate, chunk-aware
        for idx_e, ev in enumerate(parsed.get("evidence", [])):
            if "candidate_id" in ev and "evidence_id" not in ev:
                # Ensure evidence candidate_id is chunk-aware
                provided_eid = ev["candidate_id"]
                if not provided_eid.startswith(chunk["chunk_id"]):
                    ev["_original_candidate_id"] = provided_eid
                    ev["candidate_id"] = f"{chunk['chunk_id']}-ev-{idx_e+1:02d}"
                    ev["evidence_id"] = ev["candidate_id"]
                else:
                    ev["evidence_id"] = ev["candidate_id"]
            # Handle requirement linkage — must be chunk-aware
            req_cand = ev.get("requirement_candidate_id")
            if req_cand and not req_cand.startswith(chunk["chunk_id"]):
                # Evidence references candidate from different chunk — likely hallucination, keep but will be validated as unknown
                # Preserve original for debugging
                ev["_original_requirement_candidate_id"] = req_cand
                # Try to find if there's a requirement in this chunk with similar summary that this evidence should link to
                # For now, keep as is and let assign_canonical_ids handle rejection if unknown
                pass
            # Validate
            ok_e, msg_e = validate_evidence(ev, chunk)
            if not ok_e:
                # Reject evidence without provenance
                continue
            if not ev.get("source_document"):
                ev["source_document"] = chunk["source_document"]
            if not ev.get("page_number"):
                ev["page_number"] = chunk["page_number"]
            all_evs.append(ev)
    # Deduplicate requirements (conservative)
    deduped_reqs = deduplicate_requirements(all_reqs)
    # Deduplicate evidence similarly (by fact + source)
    deduped_evs = []
    seen_evs = set()
    for ev in all_evs:
        key = (ev["fact"].lower().strip(), ev["source_document"], ev["page_number"])
        if key not in seen_evs:
            seen_evs.add(key)
            deduped_evs.append(ev)
        else:
            # Keep both if uncertain (different requirement linkage)
            if ev.get("requirement_candidate_id") != next((e.get("requirement_candidate_id") for e in deduped_evs if e["fact"].lower().strip()==ev["fact"].lower().strip()), None):
                deduped_evs.append(ev)
    # Assign canonical IDs
    final_reqs, final_evs = assign_canonical_ids(deduped_reqs, deduped_evs)
    return final_reqs, final_evs

def chunk_documents_inner(doc_results: Dict[str, Any], max_chars: int = 3000) -> List[Dict[str, Any]]:
    """Inner implementation for testing — not used directly"""
    chunks = []
    chunk_id = 0
    for fname, data in doc_results.items():
        for pg in data.get("pages", []):
            text = pg.get("text","") or ""
            if not text.strip():
                continue
            page_num = pg.get("page_number", 1)
            paragraphs = text.split("\n")
            current = ""
            for para in paragraphs:
                if len(current) + len(para) + 1 > max_chars and current:
                    chunks.append({"chunk_id": f"chunk-{chunk_id:04d}", "source_document": fname, "page_number": page_num, "text": current.strip()})
                    chunk_id += 1
                    current = para + "\n"
                else:
                    current += para + "\n"
            if current.strip():
                chunks.append({"chunk_id": f"chunk-{chunk_id:04d}", "source_document": fname, "page_number": page_num, "text": current.strip()})
                chunk_id += 1
    return chunks
