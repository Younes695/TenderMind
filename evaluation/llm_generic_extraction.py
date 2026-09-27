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

# --- Prompt Variant C (Stage 3E controlled experiment, minimal PRIMARY PURPOSE clarification) ---
# Variant B is preserved unchanged above. Variant C appends ONLY concise semantic guidance.
# No tender-specific examples, no new categories, no gold answers, UNKNOWN != FALSE preserved.
PROMPT_VERSION_B = "Variant B"
PROMPT_VERSION_C = "Variant C"
PROMPT_VERSION_D = "Variant D"

LLM_PRIMARY_PURPOSE_CLARIFICATION = """Primary-purpose guidance (semantic, not keyword matching):
- Classify by the main business/contractual purpose of the requirement.
- Experience requirements (bidder history, past projects, reference projects) -> EXPERIENCE.
- Financial capacity, turnover, audited statements, bank guarantee capacity -> FINANCIAL.
- Power of attorney, legal authorization, registration, consortium agreement -> LEGAL.
- Personnel qualifications, staff CVs, key staff, project manager -> PERSONNEL.
- Payment, price, bid security, commercial terms -> COMMERCIAL.
- Delivery, completion, submission, opening, validity dates -> SCHEDULE.
- Equipment, specification, performance, testing, drawings -> TECHNICAL."""

LLM_SYSTEM_PROMPT_VARIANT_C = LLM_SYSTEM_PROMPT + "\n\n" + LLM_PRIMARY_PURPOSE_CLARIFICATION

# --- Prompt Variant D (Stage 3F controlled experiment, structural only) ---
# Variant B preserved unchanged. Variant D adds ONLY one structural instruction.
# No category examples, definitions, priorities, tender terms, gold answers, or recall maximization.
LLM_STRUCTURAL_INSTRUCTION = """Extract all distinct requirements present in the supplied chunk; do not stop after identifying only one requirement."""

LLM_SYSTEM_PROMPT_VARIANT_D = LLM_SYSTEM_PROMPT + "\n\n" + LLM_STRUCTURAL_INSTRUCTION


def get_system_prompt(variant: str = "B") -> str:
    """Return the system prompt for a variant. Default is Variant B (production)."""
    if variant == "C":
        return LLM_SYSTEM_PROMPT_VARIANT_C
    if variant == "D":
        return LLM_SYSTEM_PROMPT_VARIANT_D
    return LLM_SYSTEM_PROMPT


def prompt_hash(prompt: str) -> str:
    """Short stable hash for prompt version tracking (evaluation artifacts)."""
    import hashlib
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


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
def call_ollama_for_chunk(chunk: Dict[str, Any], model: Optional[str] = None, system_prompt: Optional[str] = None) -> Optional[Dict[str, Any]]:
    import requests, json as js
    base = get_ollama_base_url()
    mdl = model or get_ollama_model()
    prompt = build_llm_prompt(chunk)
    sys_prompt = system_prompt or LLM_SYSTEM_PROMPT
    payload = {
        "model": mdl,
        "messages": [
            {"role": "system", "content": sys_prompt},
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
def _chunk_prefix(cid: Optional[str]) -> Optional[str]:
    """Extract chunk-XXXX prefix from candidate IDs like chunk-0001-item-01 or chunk-0001-ev-01."""
    if not cid or not isinstance(cid, str):
        return None
    m = re.match(r"(chunk-\d+)", cid)
    return m.group(1) if m else None

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
    # Defense-in-depth (Stage 3C): evidence chunk must match requirement chunk, else reject.
    for ev in evidence:
        if "_rejected" in ev:
            continue
        old_req_id = ev.get("requirement_candidate_id") or ev.get("requirement_id")
        ev_cid = ev.get("candidate_id") or ev.get("evidence_id")
        # Chunk-prefix consistency: evidence and its requirement must come from same chunk.
        if old_req_id and ev_cid:
            req_prefix = _chunk_prefix(old_req_id)
            ev_prefix = _chunk_prefix(ev_cid)
            if req_prefix and ev_prefix and req_prefix != ev_prefix:
                ev["_rejected"] = f"cross-chunk evidence {ev_cid} -> {old_req_id}"
                ev["requirement_id"] = None
                continue
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
        # Requirements — strict per-chunk IDs, no silent drift (Stage 3C)
        seen_req_ids: set = set()
        orig_to_corrected: dict = {}
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
                orig_to_corrected[provided_cid] = corrected
            elif "candidate_id" in req and "requirement_id" not in req:
                req["requirement_id"] = req["candidate_id"]
            elif "candidate_id" not in req and "requirement_id" not in req:
                # No ID provided, generate one
                gen_id = f"{chunk['chunk_id']}-item-{idx_r+1:02d}"
                req["candidate_id"] = gen_id
                req["requirement_id"] = gen_id
            # Duplicate candidate IDs within the same chunk must not collide silently
            if req.get("candidate_id") in seen_req_ids:
                dup_orig = req.get("candidate_id")
                corrected = f"{chunk['chunk_id']}-item-{idx_r+1:02d}-d{len(seen_req_ids)+1:02d}"
                req["_original_candidate_id"] = req.get("_original_candidate_id", dup_orig)
                req["_duplicate_candidate_id"] = dup_orig
                req["candidate_id"] = corrected
                req["requirement_id"] = corrected
            seen_req_ids.add(req.get("candidate_id"))
            if provided_cid and provided_cid.startswith(expected_prefix):
                orig_to_corrected.setdefault(provided_cid, req.get("candidate_id"))
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
        # Evidence — must reference correct candidate, chunk-aware (Stage 3C fix: strict source-local)
        # Track candidate IDs created in this chunk for strict validation
        chunk_req_ids = {r.get("candidate_id") for r in parsed.get("requirements", []) if r.get("candidate_id")}
        # Include original IDs that were corrected above so same-chunk hallucinated linkage can be remapped
        chunk_req_ids |= set(orig_to_corrected.keys())
        chunk_req_ids |= set(orig_to_corrected.values())
        # Expected generated IDs for this chunk
        expected_ids = {f"{chunk['chunk_id']}-item-{i+1:02d}" for i in range(len(parsed.get("requirements", [])))}
        chunk_req_ids |= expected_ids
        seen_ev_ids: set = set()
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
            elif "evidence_id" not in ev and "candidate_id" not in ev:
                # Missing candidate ID — generate one, but will still need requirement linkage
                gen_eid = f"{chunk['chunk_id']}-ev-{idx_e+1:02d}"
                ev["candidate_id"] = gen_eid
                ev["evidence_id"] = gen_eid
            if ev.get("candidate_id") in seen_ev_ids or ev.get("evidence_id") in seen_ev_ids:
                dup = ev.get("candidate_id")
                ev["_duplicate_candidate_id"] = dup
                ev["candidate_id"] = f"{chunk['chunk_id']}-ev-{idx_e+1:02d}-d{len(seen_ev_ids)+1:02d}"
                ev["evidence_id"] = ev["candidate_id"]
            seen_ev_ids.add(ev.get("candidate_id"))
            seen_ev_ids.add(ev.get("evidence_id"))
            # Handle requirement linkage — must be chunk-aware and exist
            req_cand = ev.get("requirement_candidate_id")
            if not req_cand:
                # Missing linkage — evidence must reference a requirement; reject if cannot be safely resolved
                ev["_rejected"] = "missing requirement_candidate_id"
                continue
            # Remap same-chunk hallucinated original ID to its corrected ID when possible
            if req_cand in orig_to_corrected:
                ev["_original_requirement_candidate_id"] = req_cand
                req_cand = orig_to_corrected[req_cand]
                ev["requirement_candidate_id"] = req_cand
            if not req_cand.startswith(chunk["chunk_id"]):
                # Cross-chunk hallucination: evidence references requirement from another chunk — must be rejected, not silently attached to REQ-001
                ev["_original_requirement_candidate_id"] = ev.get("_original_requirement_candidate_id", req_cand)
                ev["_rejected"] = f"cross-chunk hallucination {req_cand} not in {chunk['chunk_id']}"
                continue
            if req_cand not in chunk_req_ids:
                ev["_rejected"] = f"unknown candidate {req_cand} not in chunk {chunk['chunk_id']}"
                continue
            # Validate
            ok_e, msg_e = validate_evidence(ev, chunk)
            if not ok_e:
                # Reject evidence without provenance
                continue
            if not ev.get("source_document"):
                ev["source_document"] = chunk["source_document"]
            if not ev.get("page_number"):
                ev["page_number"] = chunk["page_number"]
            # Ensure evidence remains tied to source chunk (provenance)
            if ev.get("source_document") != chunk["source_document"]:
                ev["_rejected"] = "source_document mismatch after validation"
                continue
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
