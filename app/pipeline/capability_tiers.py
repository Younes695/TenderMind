"""Stage 4E — capability tiers + lanes + bounded workers (additive).

Tiers are ABSTRACT (FAST_LOCAL / STRONG_LOCAL / API_FUTURE); concrete model
names come from env with safe defaults and are NEVER hardcoded per capability.
One model may serve many lanes; lanes are not models (§6).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CapabilityTier(str, Enum):
    FAST_LOCAL = "FAST_LOCAL"      # cheap local semantic work (production-default class)
    STRONG_LOCAL = "STRONG_LOCAL"  # heavy local reasoning (unassigned until 4F+ selection)
    API_FUTURE = "API_FUTURE"      # external API models (no credentials; never auto-used)


TIER_DEFAULTS = {"FAST_LOCAL": "qwen2.5:3b", "STRONG_LOCAL": "", "API_FUTURE": ""}
TIER_ENV = {"FAST_LOCAL": "TENDERMIND_TIER_FAST_MODEL",
            "STRONG_LOCAL": "TENDERMIND_TIER_STRONG_MODEL",
            "API_FUTURE": "TENDERMIND_TIER_API_MODEL"}


def tier_model(tier: CapabilityTier) -> str:
    """Configured concrete model for a tier ('' == unassigned)."""
    return os.environ.get(TIER_ENV[tier.value], TIER_DEFAULTS[tier.value])


# Capability -> (reasoning level, preferred tier, fallback tier, volume class).
# Reasoning levels: NONE (deterministic) | LIGHT (single-call normalization) |
# INTERPRET (clause semantics) | REASON (multi-step/conflict/synthesis).
CAPABILITY_TIERS: Dict[str, Dict[str, str]] = {
    "REQUIREMENT_NORMALIZATION": {"reasoning": "LIGHT", "tier": "FAST_LOCAL",
                                  "fallback": "STRONG_LOCAL", "volume": "per-candidate/high"},
    "CLAUSE_INTERPRETATION": {"reasoning": "INTERPRET", "tier": "FAST_LOCAL",
                              "fallback": "STRONG_LOCAL", "volume": "per-ambiguous/low"},
    "AMBIGUITY_ANALYSIS": {"reasoning": "INTERPRET", "tier": "FAST_LOCAL",
                           "fallback": "STRONG_LOCAL", "volume": "per-requirement/medium"},
    "RECONCILIATION": {"reasoning": "REASON", "tier": "STRONG_LOCAL",
                       "fallback": "API_FUTURE", "volume": "per-tender/low"},
    "SYNTHESIS": {"reasoning": "REASON", "tier": "STRONG_LOCAL",
                  "fallback": "API_FUTURE", "volume": "per-tender/low"},
}


def tier_assignment(capability: str) -> Dict[str, str]:
    entry = CAPABILITY_TIERS.get(capability)
    if entry is None:
        return {"capability": capability, "status": "NOT_CONFIGURED"}
    tier = CapabilityTier(entry["tier"])
    return {"capability": capability, "reasoning": entry["reasoning"],
            "tier": tier.value, "model": tier_model(tier) or "UNASSIGNED",
            "fallback_tier": entry["fallback"], "volume": entry["volume"]}


@dataclass
class LaneContract:
    """Stable contract for one capability lane (A-E). Backends plug in later."""

    name: str
    input_contract: str
    output_contract: str
    deterministic_preprocessing: str
    ai_step: str  # "none" or capability name; "NOT_CONFIGURED" when unwired
    provenance_requirement: str
    failure_semantics: str
    model_tier: str
    parallelizable: bool


LANES: Dict[str, LaneContract] = {
    "LANE_A_REQUIREMENT_INTELLIGENCE": LaneContract(
        "LANE_A_REQUIREMENT_INTELLIGENCE", "SourceText[]",
        "ValidatedRequirement[] + EvidenceLink[]",
        "discovery + compression (4A)", "REQUIREMENT_NORMALIZATION",
        "R1-R6 validator per job",
        "candidate-level statuses; PARTIAL; never fabricate",
        "FAST_LOCAL", True),
    "LANE_B_COMMERCIAL_SCHEDULE": LaneContract(
        "LANE_B_COMMERCIAL_SCHEDULE", "StructuredTable[] + SourceText[]",
        "CommercialLineItem[] + ScheduleRecord[] + commercial/deadline dicts",
        "BOQ normalizer + deadline/currency/payment patterns",
        "CLAUSE_INTERPRETATION (NOT_CONFIGURED)",
        "file+sheet+row or document+page+span",
        "unparseable listed, never guessed", "FAST_LOCAL", True),
    "LANE_C_COMPLIANCE_GAP_AMBIGUITY": LaneContract(
        "LANE_C_COMPLIANCE_GAP_AMBIGUITY", "ValidatedRequirement[] + inventory",
        "GapSummary + flags (4F)",
        "gap counts; UNKNOWN quarantine; failure lists",
        "AMBIGUITY_ANALYSIS (NOT_CONFIGURED)",
        "requirement/inventory IDs cited",
        "counts always; interpretive flags only from backends",
        "FAST_LOCAL", False),
    "LANE_D_CROSS_DOCUMENT_RECONCILIATION": LaneContract(
        "LANE_D_CROSS_DOCUMENT_RECONCILIATION", "ReconciliationInput",
        "ReconciliationResult",
        "textual dedup; addenda as ordinary sources",
        "RECONCILIATION (NOT_CONFIGURED)",
        "member requirement IDs per group",
        "no fake reconciliation; NOT_CONFIGURED surfaced",
        "STRONG_LOCAL", True),
    "LANE_E_SYNTHESIS_MANAGEMENT": LaneContract(
        "LANE_E_SYNTHESIS_MANAGEMENT", "TenderAnalysisResult",
        "cited summary pack (4F); NEVER auto BID/NO-BID",
        "mandatory lists, gaps, UNKNOWNs, counts",
        "SYNTHESIS (NOT_CONFIGURED)",
        "every claim cites artifact IDs",
        "truthful slots; prose only with citations",
        "STRONG_LOCAL", False),
}


@dataclass
class WorkerConfig:
    """Bounded concurrency: MAX_AI_WORKERS default 2 (4D evidence). OFF globally."""

    max_workers: int = 2
    max_pending: int = 8  # 4 x workers; overflow sheds explicitly
    enabled: bool = False  # production default OFF; batch tooling opts in

    def __post_init__(self):
        try:
            w = int(self.max_workers)
        except (TypeError, ValueError):
            w = 2
        self.max_workers = max(1, min(8, w))
        try:
            p = int(self.max_pending)
        except (TypeError, ValueError):
            p = 4 * self.max_workers
        self.max_pending = max(self.max_workers, p)


def load_worker_config(env: Optional[Dict[str, str]] = None) -> WorkerConfig:
    e = env if env is not None else os.environ
    try:
        w = int(e.get("TENDERMIND_MAX_AI_WORKERS", 2))
    except (TypeError, ValueError):
        w = 2
    return WorkerConfig(max_workers=w, enabled=e.get("TENDERMIND_WORKERS_ENABLED") == "1")


def lane_manifest() -> Dict[str, Dict[str, Any]]:
    return {name: {"input": l.input_contract, "output": l.output_contract,
                   "preprocessing": l.deterministic_preprocessing, "ai_step": l.ai_step,
                   "provenance": l.provenance_requirement, "failure": l.failure_semantics,
                   "tier": l.model_tier, "parallelizable": l.parallelizable}
            for name, l in LANES.items()}
