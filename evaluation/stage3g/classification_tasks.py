"""
Stage 3G — Controlled single-label classification tasks (evaluation-only).

No production Variant B/C/D mutation. No TenderMind behavior change.
Same model/endpoint/decoding as the existing LLM evaluator where applicable:
- model qwen2.5:3b, endpoint http://localhost:11434 (via existing helpers)
- temperature 0, stream False, timeout 90 (same as call_ollama_for_chunk)
- Task A/B differ ONLY in the system-prompt definition block.
"""
import re
import time
from typing import Optional

ALLOWED_LABELS = [
    "LEGAL", "EXPERIENCE", "FINANCIAL", "PERSONNEL", "COMMERCIAL", "SCHEDULE",
    "TECHNICAL", "HSE", "QA_QC", "EQUIPMENT", "SUBCONTRACTOR", "SUBMISSION",
    "UNKNOWN",
]

TASK_A_SYSTEM = """You are a tender requirement classifier. Choose the single best category for the given tender requirement text.
Allowed labels: LEGAL, EXPERIENCE, FINANCIAL, PERSONNEL, COMMERCIAL, SCHEDULE, TECHNICAL, HSE, QA_QC, EQUIPMENT, SUBCONTRACTOR, SUBMISSION, UNKNOWN.
Return ONLY the category label, no other text."""

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
    return f'Requirement text:\n"""{source_text}"""\nCategory:'


def normalize_output(raw: Optional[str]) -> tuple[Optional[str], str]:
    """Map raw model output to an allowed label or (None, reason). Never silently coerce."""
    if raw is None:
        return None, "empty"
    text = raw.strip()
    # Strip markdown fences / quotes that models sometimes add
    text = re.sub(r"^```(?:json|text)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip().strip("\"'").strip()
    # Take first token/line only (single-label task)
    first = re.split(r"[\s,.;:]+", text, maxsplit=1)[0] if text else ""
    up = first.upper()
    if up in ALLOWED_LABELS:
        return up, "ok"
    return None, f"invalid: {raw[:120]!r}"


def call_classifier(snippet_text: str, system_prompt: str, timeout: int = TIMEOUT_SECONDS) -> dict:
    """Single classification call. Returns dict with raw output, latency, timeout flag."""
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
