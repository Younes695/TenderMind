"""Stage 4A — AI Router + ModelProvider abstraction.

    AITask -> Router -> ModelProvider -> Result

No business logic in the new pipeline path touches Ollama (or any model API)
directly; everything goes through a ModelProvider behind Router.route().
Only REQUIREMENT_NORMALIZATION is wired (validated qwen2.5:3b minimal
contract). Every other task returns NOT_CONFIGURED — support is never faked.

Timeout / failure policy (explicit, no silent recovery):
- transport timeout        -> status "timeout", NO requirement fabricated
- malformed / wrong shape  -> validation failure status, NO requirement
- contract violation       -> rejected status, NO requirement
A future fallback model plugs into Router.fallback_policy; nothing else changes.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple

from app.pipeline.contracts import (
    LLMNormalizationResult,
    NOT_CONFIGURED,
    RequirementCandidate,
)

NORMALIZER_CONTRACT_VERSION = "minimal-1"
QWEN_MODEL_NAME = "qwen2.5:3b"


class AITask(str, Enum):
    REQUIREMENT_NORMALIZATION = "REQUIREMENT_NORMALIZATION"
    CLAUSE_INTERPRETATION = "CLAUSE_INTERPRETATION"
    AMBIGUITY_ANALYSIS = "AMBIGUITY_ANALYSIS"
    RECONCILIATION = "RECONCILIATION"
    SYNTHESIS = "SYNTHESIS"


@dataclass
class ProviderCapability:
    task: str
    input_type: str
    output_type: str
    model_name: str
    enabled: bool
    timeout_s: int
    max_retries: int = 0
    # "none" unless the model actually returns calibrated confidence.
    confidence: str = "none"


class ModelProvider(ABC):
    """Interface every current and future model implements."""

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def capabilities(self) -> List[ProviderCapability]: ...

    @abstractmethod
    def normalize_requirement(
        self, candidate: RequirementCandidate
    ) -> Tuple[Optional[LLMNormalizationResult], str, float, Any]:
        """(result|None, status, latency_s, raw). Never raises on model failure."""

    @abstractmethod
    def health_check(self) -> Tuple[bool, str]: ...

    def metrics(self) -> Dict[str, Any]:
        return {"model": self.model_name, "calls": 0}


# Transport type: (candidate) -> (req_dict|None, status, latency, raw).
# Defaults to the validated Stage 3K minimal-contract caller; tests inject stubs.
TransportFn = Callable[[RequirementCandidate], Tuple[Optional[Dict[str, Any]], str, float, Any]]


def active_prompt_version() -> str:
    """minimal-2 (Stage 5A, default) or minimal-1 via TENDERMIND_PROMPT_VERSION."""
    import os
    v = os.environ.get("TENDERMIND_PROMPT_VERSION", "").strip()
    return "minimal-1" if v == "minimal-1" else "minimal-2"


def active_system_prompt() -> str:
    if active_prompt_version() == "minimal-1":
        from evaluation.stage3j.minimal_contract_prompt import MINIMAL_CONTRACT_SYSTEM
        return MINIMAL_CONTRACT_SYSTEM
    from app.pipeline.prompts import REQUIREMENT_NORMALIZATION_SYSTEM
    return REQUIREMENT_NORMALIZATION_SYSTEM


def active_model_name() -> str:
    """The model actually called (OLLAMA_MODEL), not a hardcoded label."""
    from app.pipeline.config import load_config
    return load_config().ollama_model


def _default_transport(candidate: RequirementCandidate):
    from evaluation.stage3k.two_stage_pipeline import normalize_candidate

    return normalize_candidate({
        "candidate_id": candidate.candidate_id,
        "source_text": candidate.source_text,
    }, system_prompt=active_system_prompt())


class QwenMinimalContractProvider(ModelProvider):
    """REQUIREMENT_NORMALIZATION via qwen2.5:3b + validated minimal contract.

    The model returns ONLY {summary, category, mandatory, applicable_entity}.
    IDs / evidence / provenance are never requested and never accepted from
    the model (post-processing overwrites/binds them deterministically).
    """

    def __init__(self, timeout_s: int = 90,
                 transport: Optional[TransportFn] = None) -> None:
        self._timeout_s = timeout_s
        self._transport = transport or _default_transport
        self._calls = 0
        self._failures = 0
        self._timeouts = 0
        self._latencies: list = []

    @property
    def model_name(self) -> str:
        return active_model_name()

    def capabilities(self) -> List[ProviderCapability]:
        return [ProviderCapability(
            task=AITask.REQUIREMENT_NORMALIZATION.value,
            input_type="RequirementCandidate",
            output_type="LLMNormalizationResult",
            model_name=self.model_name,
            enabled=True,
            timeout_s=self._timeout_s,
            max_retries=0,
            confidence="none",
        )]

    def normalize_requirement(self, candidate: RequirementCandidate):
        t0 = time.time()
        try:
            req, status, lat, raw = self._transport(candidate)
        except Exception as e:  # transport must not take down the pipeline
            lat = time.time() - t0
            self._calls += 1
            self._failures += 1
            name = type(e).__name__.lower()
            if "timeout" in name or "timeout" in str(e).lower() or "timed out" in str(e).lower():
                self._timeouts += 1
                return None, "timeout", lat, None
            return None, f"transport_error:{type(e).__name__}", lat, None
        self._calls += 1
        self._latencies.append(lat)
        if status == "timeout":
            self._timeouts += 1
            self._failures += 1
            return None, "timeout", lat, raw
        if status != "ok" or not req:
            self._failures += 1
            return None, status, lat, raw
        # Minimal-contract whitelist: ONLY these four keys cross the boundary.
        # Anything model-generated beyond them (IDs, provenance, source) is dropped.
        result = LLMNormalizationResult(
            summary=str(req.get("summary", "")),
            category=str(req.get("category", "")),
            mandatory=req.get("mandatory"),
            applicable_entity=req.get("applicable_entity"),
        )
        if not result.summary:
            self._failures += 1
            return None, "empty", lat, raw
        return result, "ok", lat, raw

    def health_check(self):
        try:
            from evaluation.llm_generic_extraction import check_ollama_available
            return check_ollama_available()
        except Exception as e:
            return False, f"health check failed: {e}"

    def metrics(self) -> Dict[str, Any]:
        lats = sorted(self._latencies)
        return {
            "model": self.model_name,
            "calls": self._calls,
            "failures": self._failures,
            "timeouts": self._timeouts,
            "avg_latency_s": round(sum(lats) / len(lats), 2) if lats else 0.0,
            "p95_latency_s": round(lats[int(len(lats) * 0.95)], 2) if lats else 0.0,
        }


class Router:
    """Routes AITasks to providers. Unknown/unwired tasks -> NOT_CONFIGURED."""

    def __init__(self, providers: Optional[Dict[str, ModelProvider]] = None,
                 fallback_policy: str = "none: explicit failure, no silent fallback") -> None:
        self._providers: Dict[str, ModelProvider] = dict(providers or {})
        self.fallback_policy = fallback_policy

    def register(self, task: AITask, provider: ModelProvider) -> None:
        self._providers[task.value] = provider

    def route(self, task: AITask):
        """Return the provider, or NOT_CONFIGURED (falsy) — never fake support."""
        return self._providers.get(task.value, NOT_CONFIGURED)

    def selection_metadata(self, task: AITask) -> Dict[str, Any]:
        provider = self.route(task)
        if provider is NOT_CONFIGURED:
            return {"task": task.value, "status": "NOT_CONFIGURED",
                    "fallback_policy": self.fallback_policy}
        return {"task": task.value, "status": "configured",
                "model": provider.model_name,
                "provider": type(provider).__name__,
                "contract_version": NORMALIZER_CONTRACT_VERSION,
                "fallback_policy": self.fallback_policy}

    def normalize(self, task: AITask, candidate: RequirementCandidate):
        """Convenience: route + normalize, or explicit not-configured failure."""
        provider = self.route(task)
        if provider is NOT_CONFIGURED:
            return None, "not_configured", 0.0, None
        return provider.normalize_requirement(candidate)


class EscalatingProvider(ModelProvider):
    """Per-task model routing: fast primary model for every candidate, a
    stronger model ONLY for candidates the primary could not settle
    (failure status or UNKNOWN category).

    The escalation result is used only when it is a valid, non-UNKNOWN answer;
    otherwise the primary outcome stands. Nothing is fabricated either way.
    Model: TENDERMIND_ESCALATION_MODEL (default qwen3:4b; "off" disables).
    """

    def __init__(self, primary: ModelProvider, escalation_model: str,
                 timeout_s: int = 240,
                 transport: Optional[TransportFn] = None) -> None:
        self._primary = primary
        self._escalation_model = escalation_model
        self._timeout_s = timeout_s
        self._transport = transport or self._default_escalation_transport
        self.escalations = 0
        self.escalation_wins = 0

    def _default_escalation_transport(self, candidate: RequirementCandidate):
        from evaluation.stage3k.two_stage_pipeline import normalize_candidate
        return normalize_candidate({
            "candidate_id": candidate.candidate_id,
            "source_text": candidate.source_text,
        }, system_prompt=active_system_prompt(), timeout=self._timeout_s,
            model=self._escalation_model)

    @property
    def model_name(self) -> str:
        return f"{self._primary.model_name}+{self._escalation_model}"

    def capabilities(self) -> List[ProviderCapability]:
        return self._primary.capabilities()

    def health_check(self):
        return self._primary.health_check()

    def normalize_requirement(self, candidate: RequirementCandidate):
        result, status, lat, raw = self._primary.normalize_requirement(candidate)
        needs = status != "ok" or result is None or result.category == "UNKNOWN"
        if not needs:
            return result, status, lat, raw
        self.escalations += 1
        t0 = time.time()
        try:
            req, st2, _lat2, raw2 = self._transport(candidate)
        except Exception:
            req, st2, raw2 = None, "escalation_error", None
        lat += time.time() - t0
        if st2 == "ok" and req and req.get("summary") and req.get("category") not in (None, "", "UNKNOWN"):
            self.escalation_wins += 1
            return LLMNormalizationResult(
                summary=str(req.get("summary", "")),
                category=str(req.get("category", "")),
                mandatory=req.get("mandatory"),
                applicable_entity=req.get("applicable_entity"),
            ), "ok", lat, raw2
        return result, status, lat, raw

    def metrics(self) -> Dict[str, Any]:
        m = dict(self._primary.metrics())
        m.update({"escalation_model": self._escalation_model,
                  "escalations": self.escalations,
                  "escalation_wins": self.escalation_wins})
        return m


DEFAULT_ESCALATION_MODEL = "qwen3:4b"


def default_router(timeout_s: int = 90) -> Router:
    """Production router: only REQUIREMENT_NORMALIZATION wired.

    Per-task escalation: only UNKNOWN/failed candidates are re-asked to
    TENDERMIND_ESCALATION_MODEL (default qwen3:4b, measured +2/70 with no
    change to rows the primary settled — docs/STAGE_5G_ESCALATION.md).
    Set it to "off" to disable. If the model is not installed the call fails
    fast and the primary outcome stands.
    """
    import os
    provider: ModelProvider = QwenMinimalContractProvider(timeout_s)
    esc = os.environ.get("TENDERMIND_ESCALATION_MODEL", DEFAULT_ESCALATION_MODEL).strip()
    if esc and esc.lower() not in ("off", "none", "0", "false"):
        try:
            esc_timeout = int(os.environ.get("TENDERMIND_ESCALATION_TIMEOUT", 150))
        except ValueError:
            esc_timeout = 150
        provider = EscalatingProvider(provider, esc, timeout_s=esc_timeout)
    return Router({AITask.REQUIREMENT_NORMALIZATION.value: provider})
