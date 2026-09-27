"""Stage 4A — machine-readable AI capability registry.

Each entry documents task / input / output / model / fallback / enabled /
timeout / retry / confidence. Only REQUIREMENT_NORMALIZATION is configured
(qwen2.5:3b, validated minimal contract). Confidence is "none": the model
does not return calibrated confidence and none is invented.
"""
from __future__ import annotations

from typing import Any, Dict

from app.pipeline.ai_router import AITask, NORMALIZER_CONTRACT_VERSION, QWEN_MODEL_NAME


def _entry(task: AITask, input_type: str, output_type: str, model: str,
           fallback: str, enabled: bool, timeout_s: int, retries: int,
           confidence: str, notes: str = "") -> Dict[str, Any]:
    return {
        "task": task.value,
        "input_type": input_type,
        "output_type": output_type,
        "preferred_model": model,
        "fallback_model": fallback,
        "enabled": enabled,
        "timeout_s": timeout_s,
        "max_retries": retries,
        "confidence": confidence,
        "notes": notes,
    }


AI_CAPABILITY_REGISTRY: Dict[str, Dict[str, Any]] = {
    AITask.REQUIREMENT_NORMALIZATION.value: _entry(
        AITask.REQUIREMENT_NORMALIZATION,
        "RequirementCandidate", "LLMNormalizationResult",
        QWEN_MODEL_NAME, "none-configured", True, 90, 0, "none",
        f"validated minimal contract {NORMALIZER_CONTRACT_VERSION}; "
        "UNKNOWN preserved, never coerced"),
    AITask.CLAUSE_INTERPRETATION.value: _entry(
        AITask.CLAUSE_INTERPRETATION,
        "RequirementCandidate", "TBD", "unassigned", "none-configured",
        False, 90, 0, "none", "Stage 4B+; Router returns NOT_CONFIGURED"),
    AITask.AMBIGUITY_ANALYSIS.value: _entry(
        AITask.AMBIGUITY_ANALYSIS,
        "ValidatedRequirement[]", "TBD", "unassigned", "none-configured",
        False, 90, 0, "none", "Stage 4B+; Router returns NOT_CONFIGURED"),
    AITask.RECONCILIATION.value: _entry(
        AITask.RECONCILIATION,
        "ReconciliationInput", "ReconciliationResult", "unassigned",
        "none-configured", False, 120, 0, "none",
        "contract defined in reconciliation.py; no backend"),
    AITask.SYNTHESIS.value: _entry(
        AITask.SYNTHESIS,
        "ValidatedRequirement[]", "TBD", "unassigned", "none-configured",
        False, 120, 0, "none", "Stage 4B+; Router returns NOT_CONFIGURED"),
}


def get_capability(task_name: str) -> Dict[str, Any]:
    return AI_CAPABILITY_REGISTRY.get(task_name, {"task": task_name, "enabled": False,
                                                  "status": "NOT_CONFIGURED"})


def enabled_tasks() -> list:
    return [name for name, e in AI_CAPABILITY_REGISTRY.items() if e.get("enabled")]
