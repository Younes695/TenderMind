"""Stage 4A — cross-document reconciliation BOUNDARY (interface only).

Do NOT implement an AI reconciliation system in 4A. This module defines the
future contract so Stage 4B+ can plug a backend in without pipeline rewrites.

Future input: validated requirements across documents.
Future output: duplicate/related groups, conflicts, superseded requirements,
clarifications/addenda effects.

Until a backend exists every entry point returns NOT_CONFIGURED explicitly.
Reconciliation is never faked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from app.pipeline.contracts import NOT_CONFIGURED, ValidatedRequirement


@dataclass
class ReconciliationInput:
    requirements: List[ValidatedRequirement] = field(default_factory=list)


@dataclass
class RequirementGroup:
    group_id: str
    requirement_ids: List[str] = field(default_factory=list)
    relation: str = ""  # duplicate | related | conflict | supersedes
    rationale: str = ""


@dataclass
class ReconciliationResult:
    status: str = "NOT_CONFIGURED"  # or COMPLETED when a backend exists
    groups: List[RequirementGroup] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    superseded: List[Dict[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def reconcile(_input: ReconciliationInput):
    """No backend in 4A. Returns NOT_CONFIGURED — never an empty fake success."""
    return NOT_CONFIGURED
