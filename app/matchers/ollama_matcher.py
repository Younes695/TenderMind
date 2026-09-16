"""
Ollama Matcher — TenderMind — Local LLM, OFFLINE, No Paid API
- Uses Ollama local HTTP API at localhost only (http://localhost:11434)
- Default model: qwen3:4b (override via TENDERMIND_OLLAMA_MODEL)
- Default provider remains offline/local — never produces BID/NO_BID
- Output MUST conform exactly to MatcherOutput (via strict JSON)
- Malformed/ambiguous model output => REVIEW, confidence 0.0
- Preserves tender_id, requirement_id, company_id, source evidence and provenance
- LLM may classify applicability/matching only; it must NOT make final tender decision
- Cost: $0, no network beyond localhost, no Azure/OpenAI
"""
import os
import json
import re
import time
from typing import Optional, List

from .base import BaseMatcher, MatcherInput, MatcherOutput

DEFAULT_MODEL = "qwen3:4b"
OLLAMA_ENDPOINT = "http://localhost:11434"
TIMEOUT_PER_REQUEST = 90  # seconds, increased from 30 for qwen3:4b per 2026-09-13 smoke (33s >30s timeout) — configurable via TENDERMIND_OLLAMA_TIMEOUT

# Minimal JSON-only prompt — model returns ONLY applicability + confidence (2 fields)
# All other fields (reason, evidence IDs, provenance, contradiction flags, facts) are derived
# deterministically in Python from MatcherInput — LLM never generates IDs, reasons, or provenance.
PROMPT_TEMPLATE = """Classify ONE requirement-evidence pair. Return ONLY JSON: {{"applicability": "PASS|FAIL|REVIEW|MISSING", "confidence": 0.0-1.0}}.

Requirement [{requirement_id}]:
\"\"\"{requirement_text}\"\"\"

Evidence [{evidence_id}]:
\"\"\"{evidence_fact}\"\"\"

Rules: PASS=satisfies, FAIL=explicitly contradicts, MISSING=no support, REVIEW=ambiguous.
Respond ONLY: {{"applicability": "...", "confidence": 0.0}}
"""

def get_ollama_model() -> str:
    return os.environ.get("TENDERMIND_OLLAMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL

def get_ollama_endpoint() -> str:
    return os.environ.get("TENDERMIND_OLLAMA_ENDPOINT", OLLAMA_ENDPOINT).strip().rstrip("/")

def get_ollama_timeout() -> int:
    # Configurable via TENDERMIND_OLLAMA_TIMEOUT, default 90 for qwen3:4b
    val = os.environ.get("TENDERMIND_OLLAMA_TIMEOUT", str(TIMEOUT_PER_REQUEST)).strip()
    try:
        t = int(val)
        if 10 <= t <= 300:
            return t
    except:
        pass
    return TIMEOUT_PER_REQUEST

def check_ollama_available(model: Optional[str] = None) -> tuple[bool, str]:
    """
    Verify localhost Ollama endpoint and that requested model exists.
    Returns (ok, message). Never makes paid network calls.
    """
    import requests
    endpoint = get_ollama_endpoint()
    model = model or get_ollama_model()
    # Check endpoint reachable
    try:
        resp = requests.get(f"{endpoint}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False, f"Ollama endpoint {endpoint} returned {resp.status_code} — is Ollama running? Start with: ollama serve"
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        # Check if requested model exists (allow partial match, e.g., qwen3:4b vs qwen3:4b-... )
        if not models:
            return False, f"Ollama endpoint {endpoint} reachable but no models found — pull model with: ollama pull {model}"
        # Normalize: check if any model name starts with requested model
        found = any(m == model or m.startswith(model) or model.startswith(m) for m in models)
        if not found:
            return False, f"Ollama model '{model}' not found on {endpoint}. Available: {', '.join(models[:5])} — pull with: ollama pull {model}  (then verify with: ollama list)"
        return True, f"Ollama OK — endpoint {endpoint} reachable, model '{model}' available ({len(models)} models)"
    except Exception as e:
        # Distinguish not running vs other
        msg = str(e)
        if "Connection refused" in msg or "Failed to establish" in msg or "Max retries" in msg:
            return False, f"Ollama not running on {endpoint} — start with: ollama serve  (error: {type(e).__name__}: {msg[:200]})"
        return False, f"Ollama check failed: {type(e).__name__}: {msg[:300]}"

class OllamaMatcher(BaseMatcher):
    """
    Local Ollama matcher — OFFLINE, no paid API, localhost only.
    Default model qwen3:4b, override via TENDERMIND_OLLAMA_MODEL.
    Never produces BID/NO_BID — only PASS|FAIL|REVIEW|MISSING per pair.
    Malformed/ambiguous output => REVIEW, confidence 0.0.
    """
    name = "ollama-local"
    version = "1.0"

    def __init__(self, model: Optional[str] = None, endpoint: Optional[str] = None, timeout: Optional[int] = None):
        self.model = model or get_ollama_model()
        self.endpoint = endpoint or get_ollama_endpoint()
        # Configurable via TENDERMIND_OLLAMA_TIMEOUT (default 90 for qwen3:4b) — localhost only, no paid provider
        if timeout is None:
            try:
                self.timeout = get_ollama_timeout()
            except Exception:
                self.timeout = TIMEOUT_PER_REQUEST
        else:
            self.timeout = timeout
        # Do not check availability here — lazy on first match() or via check_ollama_available()
        # Keep offline/local default — no network until match() is called
        self._availability_checked = False

    def _ensure_available(self):
        ok, msg = check_ollama_available(self.model)
        if not ok:
            # Provide exact installation/pull command per task
            raise RuntimeError(
                f"Ollama unavailable: {msg}\n"
                f"To fix:\n"
                f"  1. Install Ollama: https://ollama.com/download  (Windows: OllamaSetup.exe)\n"
                f"  2. Pull model: ollama pull {self.model}\n"
                f"  3. Verify: ollama list  (should show {self.model})\n"
                f"  4. Ensure Ollama is running: ollama serve (or it auto-starts)\n"
                f"  5. Test endpoint: curl {self.endpoint}/api/tags\n"
                f"Do not install automatically unless already available — STOP and report BLOCKED."
            )

    def match(self, inp: MatcherInput) -> MatcherOutput:
        # Deterministic hard rules BEFORE LLM (single source of truth — no behavior change).
        # These ensure MISSING != FAIL etc., even if LLM is wrong. Zero HTTP here.
        from .deterministic_rules import evaluate_pre_llm
        _pre = evaluate_pre_llm(inp)
        if _pre is not None:
            return _pre

        # Now check Ollama availability (local, no paid API)
        try:
            self._ensure_available()
        except RuntimeError as e:
            # Graceful: return REVIEW with reason, do not hang, do not call network
            return MatcherOutput(
                support=None, contradiction=False,
                missing_facts=[str(e)[:200]],
                supporting_facts=[], contradictory_facts=[],
                applicability="REVIEW", confidence=0.0,
                reason=f"Ollama unavailable — {str(e)[:200]}"
            )

        # Build minimal JSON-only prompt (2 fields) — IDs/reasons/provenance derived deterministically below
        prompt = PROMPT_TEMPLATE.format(
            requirement_id=inp.requirement_id,
            requirement_text=inp.requirement_text,
            evidence_id=inp.evidence_id,
            evidence_fact=inp.evidence_fact
        )

        # Call Ollama local HTTP API with timeout — use /api/chat for strict JSON
        import requests
        import json as js
        # Minimal system prompt — short to minimize generation time on qwen3:4b CPU
        system_instructions = """Return ONLY valid JSON: {"applicability": "PASS|FAIL|REVIEW|MISSING", "confidence": 0.0-1.0}. No other text."""
        user_content = prompt  # PROMPT_TEMPLATE already contains requirement + evidence with provenance
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instructions},
                {"role": "user", "content": user_content}
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0}
        }
        try:
            resp = requests.post(
                f"{self.endpoint}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama HTTP {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            # /api/chat returns {"message": {"role": "assistant", "content": "JSON string"}, ...}
            # Fallback to "response" for /api/generate compatibility
            raw = ""
            if "message" in data and isinstance(data["message"], dict):
                raw = data["message"].get("content", "") or ""
            if not raw:
                raw = data.get("response", "") or ""
            # Ollama with format=json should return JSON string
            raw = raw.strip()
            if not raw:
                raise ValueError("Empty response from Ollama")
            # Parse minimal 2-field JSON: {applicability, confidence} — all else derived deterministically
            parsed = js.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("LLM output must be a JSON object")
            applicability = parsed.get("applicability")
            confidence = parsed.get("confidence", 0.0)
            # Strict enum: only these 4; BID/NO_BID or anything else => malformed -> REVIEW
            if applicability not in ("PASS", "FAIL", "REVIEW", "MISSING"):
                raise ValueError(f"Invalid applicability: {applicability!r} (must be PASS|FAIL|REVIEW|MISSING, never BID/NO_BID)")
            try:
                confidence = float(confidence)
                if not 0.0 <= confidence <= 1.0:
                    raise ValueError(f"confidence {confidence} out of range")
            except Exception:
                raise ValueError(f"Invalid confidence: {confidence!r}")

            # Defense in depth: LLM must never invent evidence IDs (we derive them deterministically,
            # so any invented IDs in model output indicate hallucination => REVIEW)
            _raw_ids = parsed.get("matched_evidence_ids", None)
            if _raw_ids:
                _allowed = {inp.evidence_id}
                for _mid in _raw_ids:
                    if _mid not in _allowed:
                        raise ValueError(f"Invented evidence ID: {_mid} not in allowed {_allowed}")

            # Deterministic post-LLM safety validation via SAME shared rules (LLM cannot bypass).
            from .deterministic_rules import validate_post_llm as _validate_post
            _override = _validate_post(inp, applicability, float(confidence))
            if _override is not None:
                return _override
            req_lower = (inp.requirement_text or "").lower()
            fact_lower = (inp.evidence_fact or "").lower()
            _has_first = ("first category" in req_lower or "first-category" in req_lower)
            _has_second = ("second category" in fact_lower or "second-category" in fact_lower or "grade 2" in fact_lower)

            # Derive all remaining fields deterministically from MatcherInput (LLM never generates them):
            # - contradiction: True iff final applicability is FAIL with explicit First/Second evidence
            # - matched evidence IDs: only input evidence_id when PASS, else [] (never invented)
            # - reason/provenance: built from original input provenance, not LLM text
            if applicability == "FAIL" and _has_first and _has_second:
                _contradiction = True
            elif applicability == "FAIL":
                _contradiction = True
            else:
                _contradiction = False
            support_map = {"PASS": True, "FAIL": False, "MISSING": False, "REVIEW": None}
            support = support_map.get(applicability, None)
            _reason = (
                f"{applicability} for {inp.requirement_id} based on evidence {inp.evidence_id} "
                f"from {inp.source_document} {inp.page_or_section} "
                f"(LLM {self.model}, confidence {float(confidence):.2f})"
            )[:500]
            _matched_ids = [inp.evidence_id] if applicability == "PASS" else []

            return MatcherOutput(
                support=support,
                contradiction=bool(_contradiction),
                missing_facts=[] if applicability in ("PASS", "FAIL") else [f"No supporting facts for {inp.requirement_id}"] if applicability == "MISSING" else [],
                supporting_facts=[f"Evidence {inp.evidence_id} supports {inp.requirement_id}"] if applicability == "PASS" else [],
                contradictory_facts=[f"Contradiction for {inp.requirement_id}: First vs Second Category"] if _contradiction else [],
                applicability=applicability,
                confidence=float(confidence),
                reason=_reason
            )

        except Exception as e:
            # Graceful failure: malformed/ambiguous/timeout => REVIEW, confidence 0.0
            # Never log key, never invent BID
            err = str(e)
            if "timeout" in err.lower() or "timed out" in err.lower():
                return MatcherOutput(
                    support=None, contradiction=False,
                    missing_facts=[f"Timeout after {self.timeout}s"],
                    supporting_facts=[], contradictory_facts=[],
                    applicability="REVIEW", confidence=0.0,
                    reason=f"Ollama timeout after {self.timeout}s — REVIEW per graceful failure"
                )
            # Check for malformed JSON
            if "JSON" in err or "json" in err.lower() or "Expecting" in err:
                return MatcherOutput(
                    support=None, contradiction=False,
                    missing_facts=[f"Malformed JSON: {err[:200]}"],
                    supporting_facts=[], contradictory_facts=[],
                    applicability="REVIEW", confidence=0.0,
                    reason=f"Malformed model output — REVIEW: {err[:200]}"
                )
            # Check for invented BID/NO_BID
            if "BID" in err:
                return MatcherOutput(
                    support=None, contradiction=False,
                    missing_facts=[f"Forbidden BID/NO_BID output: {err[:200]}"],
                    supporting_facts=[], contradictory_facts=[],
                    applicability="REVIEW", confidence=0.0,
                    reason=f"LLM returned forbidden BID/NO_BID — rejected, REVIEW"
                )
            # Generic malformed
            return MatcherOutput(
                support=None, contradiction=False,
                missing_facts=[f"Model error: {type(e).__name__}: {err[:200]}"],
                supporting_facts=[], contradictory_facts=[],
                applicability="REVIEW", confidence=0.0,
                reason=f"Malformed/ambiguous model output — REVIEW: {type(e).__name__}: {err[:200]}"
            )
