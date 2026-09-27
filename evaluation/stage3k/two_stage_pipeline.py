"""
Stage 3K — Behind-flag two-stage pipeline (evaluation-only).

Architecture under test:
    deterministic candidate discovery / segmentation
        -> single-requirement candidate
        -> minimal-contract LLM normalization
        -> deterministic provenance / evidence / canonical IDs

Isolation rules:
- Production path is never touched. The flag TENDERMIND_TWO_STAGE_LLM only
  affects the evaluate-only dispatcher in this module ("1" = experimental,
  anything else = existing deterministic behavior).
- Reuses production helpers without modifying them: chunk_documents,
  GENERIC_PATTERNS, parse/validate/dedup/assign helpers, tiny-guard semantics.
- No prompt tuning, no new categories, no model change.
"""
import os
import re
import time
from typing import List, Dict, Any, Optional

TWO_STAGE_FLAG = "TENDERMIND_TWO_STAGE_LLM"

# Tiny-chunk guard threshold (same semantics as Stage 3D tiny_guard: chunks
# below this size stalled qwen2.5:3b past the 90s timeout). Applies at the
# chunk level only; candidate-level filtering uses the splitter gate.
TINY_CHUNK_THRESHOLD = 300
SKIPPED_TINY_INPUT = "SKIPPED_TINY_INPUT"


def flag_enabled() -> bool:
    """Evaluation-only flag. Default/off preserves existing behavior."""
    return os.environ.get(TWO_STAGE_FLAG) == "1"


def discover_candidates(doc_results=None, chunks=None, max_per_chunk: int = 20):
    """Stage A — deterministic candidate discovery / segmentation.

    Accepts either ingested doc_results (chunks them with the existing
    chunker) or an explicit chunk list (e.g., the exact Stage 3D 12 chunks).
    Returns (accepted, rejected, skipped_tiny).
    """
    from evaluation.llm_generic_extraction import chunk_documents
    from evaluation.stage3i.presegment import segment_parent_chunk

    if chunks is None:
        assert doc_results is not None, "need doc_results or chunks"
        chunks = chunk_documents(doc_results, max_chars=3000)
    accepted, rejected, skipped = [], [], []
    for ch in chunks:
        text = (ch.get("text") or "").strip()
        if len(text) < TINY_CHUNK_THRESHOLD:
            skipped.append({
                "chunk_id": ch.get("chunk_id"),
                "source_document": ch.get("source_document"),
                "page_number": ch.get("page_number"),
                "text_len": len(text),
                "status": SKIPPED_TINY_INPUT,
            })
            continue
        acc, rej = segment_parent_chunk({
            "chunk_id": ch.get("chunk_id"),
            "source_document": ch.get("source_document"),
            "page_number": ch.get("page_number", 1),
            "text": ch.get("text", ""),
        })
        accepted.extend(acc[:max_per_chunk])
        rejected.extend(rej)
    return accepted, rejected, skipped


def normalize_candidate(candidate, system_prompt=None, timeout: int = 90, model=None):
    """Stage B — minimal-contract LLM normalization for ONE candidate.

    Returns (requirement|None, status, latency, raw). Exactly one requirement
    is expected. Provenance/evidence are NOT requested from the model.
    """
    from evaluation.stage3j.minimal_contract_prompt import MINIMAL_CONTRACT_SYSTEM
    from evaluation.stage3h.single_req_tasks import parse_single_requirement
    from evaluation.llm_generic_extraction import get_ollama_model, get_ollama_base_url
    import requests
    sys_prompt = system_prompt or MINIMAL_CONTRACT_SYSTEM
    base = get_ollama_base_url()
    mdl = model or get_ollama_model()
    payload = {
        "model": mdl,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"Requirement text:\n\"\"\"{candidate['source_text']}\"\"\"\nReturn the normalized requirement."},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    if mdl.startswith("qwen3"):
        # qwen3 thinks by default, which breaks single-JSON output (Stage 4B).
        payload["think"] = False
    t0 = time.time()
    try:
        resp = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
        lat = time.time() - t0
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}", lat, None
        data = resp.json()
        raw = ""
        if isinstance(data.get("message"), dict):
            raw = data["message"].get("content", "") or ""
        if not raw:
            raw = data.get("response", "") or ""
        req, status = parse_single_requirement(raw)
        return req, status, lat, raw
    except Exception as e:
        lat = time.time() - t0
        is_timeout = "timeout" in type(e).__name__.lower() or "timeout" in str(e).lower() or "timed out" in str(e).lower()
        return None, ("timeout" if is_timeout else f"error_{type(e).__name__}"), lat, None


def post_process(requirements_with_candidates):
    """Stage C — deterministic provenance / evidence / canonical IDs.

    Input: list of (requirement_dict, candidate_dict). Attaches provenance
    from the candidate fixture, derives 1-to-1 evidence deterministically,
    assigns canonical REQ-XXX IDs deterministically. No LLM involved.
    """
    from evaluation.llm_generic_extraction import deduplicate_requirements, assign_canonical_ids

    reqs = []
    for req, cand in requirements_with_candidates:
        r = dict(req)
        r["candidate_id"] = cand["candidate_id"]
        r["requirement_id"] = cand["candidate_id"]
        r["source_document"] = cand["source_document"]
        r["page_number"] = cand["page"]
        r["source_text"] = cand["source_text"]
        r["parent_chunk_id"] = cand.get("parent_chunk_id")
        r["provenance"] = {"quote_en": cand["source_text"][:200]}
        r["extraction_method"] = "two-stage"
        r.setdefault("confidence", 0.7)
        reqs.append(r)
    deduped = deduplicate_requirements(reqs)
    # Deterministic 1-to-1 evidence from the candidate association
    evs = []
    for r in deduped:
        # Recover the candidate via candidate_id
        cand = next((c for _, c in requirements_with_candidates if c["candidate_id"] == r["candidate_id"]), None)
        if cand is None:
            continue
        evs.append({
            "candidate_id": f"{r['candidate_id']}-ev-01",
            "evidence_id": f"{r['candidate_id']}-ev-01",
            "requirement_candidate_id": r["candidate_id"],
            "fact": r.get("summary", ""),
            "source_document": cand["source_document"],
            "page_number": cand["page"],
            "confidence": 0.7,
            "provenance": {"quote_en": cand["source_text"][:200]},
            "applicable_entity": None,
            "valid_until": None,
            "reusable": False,
        })
    final_reqs, final_evs = assign_canonical_ids(deduped, evs)
    return final_reqs, final_evs


def extract_requirements_two_stage(candidates, llm_fn=None):
    """Full experimental path over pre-discovered candidates.

    llm_fn(candidate) -> (requirement|None, status, latency, raw); defaults to
    the real minimal-contract caller. Tests inject a stub. Returns
    (final_requirements, final_evidence, per_candidate_records).
    """
    if llm_fn is None:
        def llm_fn(candidate):
            return normalize_candidate(candidate)
    pairs = []
    records = []
    for cand in candidates:
        req, status, lat, raw = llm_fn(cand)
        rec = {
            "candidate_id": cand["candidate_id"],
            "category_gold": cand.get("category_gold"),
            "source_document": cand["source_document"],
            "page": cand["page"],
            "status": status if status != "ok" else "ok",
            "predicted": (req or {}).get("category"),
            "latency": lat,
            "timeout": status == "timeout",
            "raw_output": raw,
        }
        records.append(rec)
        if req is not None and status == "ok":
            pairs.append((req, cand))
    final_reqs, final_evs = post_process(pairs) if pairs else ([], [])
    return final_reqs, final_evs, records


def extract_requirements_dispatch(doc_results=None, chunks=None, candidates=None):
    """Flag-gated dispatcher (evaluation-only).

    Flag off/unset -> existing deterministic behavior (same candidates as the
    deterministic baseline path, no LLM). Flag "1" -> two-stage experimental path.
    """
    if not flag_enabled():
        from evaluation.generic_extraction import extract_requirements_generic
        if doc_results is None:
            raise ValueError("deterministic path needs doc_results")
        return {
            "mode": "deterministic",
            "requirements": extract_requirements_generic(doc_results, "flag-check"),
            "evidence": [],
        }
    if candidates is None:
        candidates, _, _ = discover_candidates(doc_results=doc_results, chunks=chunks)
    final_reqs, final_evs, records = extract_requirements_two_stage(candidates)
    return {
        "mode": "two-stage",
        "requirements": final_reqs,
        "evidence": final_evs,
        "records": records,
    }
