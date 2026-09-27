"""Stage 4B — ModelProvider adapters (evaluation-only benchmark).

One adapter per shootout model, all implementing app.pipeline.ai_router.ModelProvider
and returning the same LLMNormalizationResult. No model-specific business logic
in the Router; no prompt tuning per model; no production defaults touched.

Fairness controls (identical for every local model):
- same MINIMAL_CONTRACT_SYSTEM string (shared constant, hash in manifest)
- same user message builder (stage3h.build_user_message)
- same parser (stage3h.parse_single_requirement) -> identical status vocabulary
- temperature 0, format json, timeout 90s
- qwen3 note: its Ollama default enables thinking, which breaks single-JSON
  comparability; think:false is a documented comparability control, not tuning.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from app.pipeline.ai_router import AITask, ModelProvider, NORMALIZER_CONTRACT_VERSION, ProviderCapability
from app.pipeline.contracts import LLMNormalizationResult, RequirementCandidate

TIMEOUT_S = 90

QWEN25_MODEL = "qwen2.5:3b"
QWEN3_MODEL = "qwen3:4b"
GEMMA_MODEL = "gemma3:12b"
PHI_MODEL = "phi4-mini"
GEMINI_MODEL = "gemini-3.8-flash"


def _ollama_base() -> str:
    from evaluation.llm_generic_extraction import get_ollama_base_url
    return get_ollama_base_url()


def _ollama_model_present(model: str) -> bool:
    try:
        from evaluation.llm_generic_extraction import check_ollama_available
        ok, _ = check_ollama_available()
        if not ok:
            return False
        import requests
        resp = requests.get(f"{_ollama_base()}/api/tags", timeout=5)
        names = [m.get("name", "") for m in resp.json().get("models", [])]
        return any(n == model or n.startswith(model + ":") for n in names)
    except Exception:
        return False


def _chat(model: str, system: str, user: str, timeout: int = TIMEOUT_S,
          think: Optional[bool] = None) -> Tuple[str, float, Dict[str, Any], Optional[str]]:
    """POST /api/chat. Returns (raw_text, latency_s, usage, error).

    usage carries prompt_eval_count/eval_count when the backend reports them.
    """
    import requests
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    if think is not None:
        payload["think"] = think
    t0 = time.time()
    try:
        resp = requests.post(f"{_ollama_base()}/api/chat", json=payload, timeout=timeout)
        lat = time.time() - t0
        if resp.status_code != 200:
            return "", lat, {}, f"http_{resp.status_code}"
        data = resp.json()
        raw = ""
        if isinstance(data.get("message"), dict):
            raw = data["message"].get("content", "") or ""
        if not raw:
            raw = data.get("response", "") or ""
        usage = {k: data.get(k) for k in ("prompt_eval_count", "eval_count",
                                          "prompt_eval_duration", "eval_duration",
                                          "total_duration") if data.get(k) is not None}
        return raw, lat, usage, None
    except Exception as e:
        lat = time.time() - t0
        name = type(e).__name__.lower() + " " + str(e).lower()
        if "timeout" in name or "timed out" in name:
            return "", lat, {}, "timeout"
        return "", lat, {}, f"transport:{type(e).__name__}"


class _OllamaMinimalProvider(ModelProvider):
    """Shared minimal-contract Ollama transport. Subclasses fix model + controls."""

    provider_name = "ollama"
    ollama_model = ""
    think: Optional[bool] = None  # None = backend default; False = comparability control

    def __init__(self, timeout_s: int = TIMEOUT_S) -> None:
        self._timeout_s = timeout_s
        self._calls = 0
        self._failures = 0
        self._timeouts = 0
        self._latencies: List[float] = []
        self._prompt_tokens = 0
        self._output_tokens = 0

    @property
    def model_name(self) -> str:
        return self.ollama_model

    def capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability(
            task=AITask.REQUIREMENT_NORMALIZATION.value,
            input_type="RequirementCandidate", output_type="LLMNormalizationResult",
            model_name=self.model_name, enabled=True, timeout_s=self._timeout_s,
            max_retries=0, confidence="none")]

    def health_check(self):
        present = _ollama_model_present(self.ollama_model)
        return present, f"ollama model {self.ollama_model} {'present' if present else 'MISSING'}"

    def normalize_requirement(self, candidate: RequirementCandidate):
        from evaluation.stage3j.minimal_contract_prompt import MINIMAL_CONTRACT_SYSTEM
        from evaluation.stage3h.single_req_tasks import (
            build_user_message, parse_single_requirement)
        raw, lat, usage, err = _chat(
            self.ollama_model, MINIMAL_CONTRACT_SYSTEM,
            build_user_message(candidate.source_text),
            timeout=self._timeout_s, think=self.think)
        self._calls += 1
        self._latencies.append(lat)
        self._prompt_tokens += int(usage.get("prompt_eval_count") or 0)
        self._output_tokens += int(usage.get("eval_count") or 0)
        if err == "timeout":
            self._failures += 1
            self._timeouts += 1
            return None, "timeout", lat, ""
        if err is not None:
            self._failures += 1
            return None, f"provider_error:{err}", lat, raw
        req, status = parse_single_requirement(raw)
        if status != "ok" or not req:
            self._failures += 1
            return None, status, lat, raw
        result = LLMNormalizationResult(
            summary=str(req.get("summary", "")), category=str(req.get("category", "")),
            mandatory=req.get("mandatory"), applicable_entity=req.get("applicable_entity"))
        if not result.summary:
            self._failures += 1
            return None, "empty", lat, raw
        return result, "ok", lat, raw

    def metrics(self) -> Dict[str, Any]:
        lats = sorted(self._latencies)
        return {"provider": self.provider_name, "model": self.model_name,
                "calls": self._calls, "failures": self._failures, "timeouts": self._timeouts,
                "avg_latency_s": round(sum(lats) / len(lats), 2) if lats else 0.0,
                "p50_latency_s": round(lats[len(lats) // 2], 2) if lats else 0.0,
                "p95_latency_s": round(lats[int(len(lats) * 0.95)], 2) if lats else 0.0,
                "min_latency_s": round(lats[0], 2) if lats else 0.0,
                "max_latency_s": round(lats[-1], 2) if lats else 0.0,
                "prompt_tokens_total": self._prompt_tokens,
                "output_tokens_total": self._output_tokens}


class Qwen25Provider(_OllamaMinimalProvider):
    """Baseline: qwen2.5:3b (production model, minimal-1 contract)."""

    provider_name = "ollama"
    ollama_model = QWEN25_MODEL


class Qwen3Provider(_OllamaMinimalProvider):
    """Local challenger: qwen3:4b with thinking disabled (comparability control)."""

    provider_name = "ollama"
    ollama_model = QWEN3_MODEL
    think = False


class GemmaProvider(_OllamaMinimalProvider):
    """Local challenger: gemma3:12b (no thinking mode on this family)."""

    provider_name = "ollama"
    ollama_model = GEMMA_MODEL


class PhiProvider(_OllamaMinimalProvider):
    """Optional local challenger: phi4-mini."""

    provider_name = "ollama"
    ollama_model = PHI_MODEL


class GeminiProvider(ModelProvider):
    """External API challenger (gemini-3.8-flash). Runs ONLY with pre-existing
    credentials; never asks for secrets, never hardcodes keys, never persists
    them. Without credentials every call reports provider_not_configured."""

    provider_name = "gemini-api"
    ollama_model = GEMINI_MODEL

    def __init__(self, timeout_s: int = TIMEOUT_S) -> None:
        self._timeout_s = timeout_s
        self._calls = 0

    @property
    def model_name(self) -> str:
        return GEMINI_MODEL

    def capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability(
            task=AITask.REQUIREMENT_NORMALIZATION.value,
            input_type="RequirementCandidate", output_type="LLMNormalizationResult",
            model_name=self.model_name, enabled=self._creds_present(),
            timeout_s=self._timeout_s, max_retries=0, confidence="none")]

    @staticmethod
    def _creds_present() -> bool:
        return any(os.environ.get(k) for k in
                   ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_API_KEY"))

    def health_check(self):
        ok = self._creds_present()
        return ok, ("gemini credentials present" if ok else "gemini NOT_CONFIGURED: no credentials")

    def normalize_requirement(self, candidate: RequirementCandidate):
        self._calls += 1
        return None, "provider_not_configured", 0.0, ""

    def metrics(self) -> Dict[str, Any]:
        return {"provider": self.provider_name, "model": self.model_name,
                "calls": self._calls, "status": "NOT_RUN"}


PROVIDER_CLASSES = {
    "qwen25": Qwen25Provider,
    "qwen3": Qwen3Provider,
    "gemma": GemmaProvider,
    "phi": PhiProvider,
    "gemini": GeminiProvider,
}
