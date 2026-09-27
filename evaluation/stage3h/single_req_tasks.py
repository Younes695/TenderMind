"""
Stage 3H — Single-requirement normalization tasks (evaluation-only).

Test A: minimal single-requirement normalization (no definitions).
Test B: same + the concise category definitions from Stage 3G Task B.
Test C: existing Variant B extraction prompt/interface (unchanged production code).

No production Variant B/C/D mutation. No TenderMind behavior change.
Same model/endpoint/decoding as the existing LLM evaluator:
- model qwen2.5:3b, endpoint http://localhost:11434 (via existing helpers)
- temperature 0, stream False, JSON mode, timeout 90.
"""
import json
import re
import time
from typing import Optional

ALLOWED_CATEGORIES = [
    "LEGAL", "EXPERIENCE", "FINANCIAL", "PERSONNEL", "COMMERCIAL", "SCHEDULE",
    "TECHNICAL", "HSE", "QA_QC", "EQUIPMENT", "SUBCONTRACTOR", "SUBMISSION",
    "UNKNOWN",
]

TASK_A_SYSTEM = """You are a tender requirement normalizer. The supplied text contains exactly ONE requirement.
Extract that single requirement and normalize it.
Return ONLY valid JSON in exactly this shape:
{"requirements": [{"summary": "...", "category": "...", "mandatory": null, "applicable_entity": null}]}
Rules:
- "requirements" must contain exactly one object.
- "category" must be one of: LEGAL, EXPERIENCE, FINANCIAL, PERSONNEL, COMMERCIAL, SCHEDULE, TECHNICAL, HSE, QA_QC, EQUIPMENT, SUBCONTRACTOR, SUBMISSION, UNKNOWN.
- "summary" must be a human-readable paraphrase grounded in the supplied text.
- Do not invent mandatory or applicable_entity values; use null unless the text explicitly states them.
- Do not discover additional requirements.
- Return ONLY the JSON object, no other text."""

TASK_B_DEFINITIONS = """Category definitions:
LEGAL = legal authorization, registration, power of attorney, consortium/legal agreements.
EXPERIENCE = bidder history, previous/reference projects.
FINANCIAL = financial capacity, turnover, audited statements, working capital.
PERSONNEL = staff qualifications, CVs, key personnel, project manager.
COMMERCIAL = price, payment, bid security, commercial terms.
SCHEDULE = submission, delivery, completion, validity dates.
TECHNICAL = technical specifications, performance, testing, design requirements.
HSE = health, safety, environmental requirements.
QA_QC = quality assurance, quality control, inspection/testing quality requirements.
EQUIPMENT = required equipment/material/equipment characteristics.
SUBCONTRACTOR = subcontracting requirements.
SUBMISSION = tender submission/package/document-format requirements.
UNKNOWN = genuinely unclear."""

TASK_B_SYSTEM = TASK_A_SYSTEM + "\n\n" + TASK_B_DEFINITIONS

TIMEOUT_SECONDS = 90


def build_user_message(source_text: str) -> str:
    return f'Requirement text:\n"""{source_text}"""\nReturn the normalized requirement.'


def call_normalizer(snippet_text: str, system_prompt: str, timeout: int = TIMEOUT_SECONDS) -> dict:
    """Single normalization call. Returns dict with raw output, latency, timeout flag."""
    from evaluation.llm_generic_extraction import get_ollama_model, get_ollama_base_url
    import requests
    base = get_ollama_base_url()
    mdl = get_ollama_model()
    payload = {
        "model": mdl,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_user_message(snippet_text)},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    t0 = time.time()
    try:
        resp = requests.post(f"{base}/api/chat", json=payload, timeout=timeout)
        lat = time.time() - t0
        if resp.status_code != 200:
            return {"raw": None, "latency": lat, "timeout": False, "http_error": resp.status_code}
        data = resp.json()
        raw = ""
        if isinstance(data.get("message"), dict):
            raw = data["message"].get("content", "") or ""
        if not raw:
            raw = data.get("response", "") or ""
        return {"raw": raw, "latency": lat, "timeout": False}
    except Exception as e:
        lat = time.time() - t0
        is_timeout = "timeout" in type(e).__name__.lower() or "timeout" in str(e).lower() or "timed out" in str(e).lower()
        return {"raw": None, "latency": lat, "timeout": is_timeout, "error": f"{type(e).__name__}: {str(e)[:200]}"}


def parse_single_requirement(raw: Optional[str]) -> tuple[Optional[dict], str]:
    """Parse Test A/B output. Returns (requirement_dict_or_None, status).

    Statuses: ok / empty / malformed / wrong_shape / bad_category / multi.
    Never coerces an incorrect category into gold.
    """
    if raw is None or not raw.strip():
        return None, "empty"
    try:
        parsed = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None, "malformed"
        try:
            parsed = json.loads(m.group(0))
        except Exception as e:
            return None, f"malformed: {e}"
    reqs = parsed.get("requirements") if isinstance(parsed, dict) else None
    if not isinstance(reqs, list) or len(reqs) == 0:
        return None, "wrong_shape"
    if len(reqs) != 1:
        return None, "multi"
    req = reqs[0]
    if not isinstance(req, dict):
        return None, "wrong_shape"
    if req.get("category") not in ALLOWED_CATEGORIES:
        return None, "bad_category"
    return req, "ok"
