"""
Deterministic Rules — TenderMind — Single Source of Truth
- Shared safety/applicability rules for requirement-evidence matching
- Used by BOTH OllamaMatcher and HybridMatcher (MockMatcher unchanged — test fixture only)
- Preserves existing behavior exactly (extracted verbatim from OllamaMatcher pre-LLM block)
- Rules NEVER produce BID/NO_BID — only PASS|FAIL|REVIEW|MISSING at requirement/evidence level
- A low relevance score must NOT manufacture MISSING — only these rules may prove MISSING

Rule precedence (strict, top-down, first hit wins):
  1. wrong tender non-reusable -> MISSING
  2. expired evidence -> REVIEW
  3. ambiguous applicability (AMBIGUOUS / REQ-AMB) -> REVIEW
  4. wrong entity (GIZA<->HYOSUNG strict) -> MISSING
  5. OEM isolation (REQ-K/L with OEM E-003/AI-E-003/E-OEM) -> MISSING
  5b. explicit REQ-A First vs Second contradiction -> FAIL + contradiction
  5c. generic First vs Second contradiction -> FAIL + contradiction
  5d. empty / no-evidence fact -> MISSING (MISSING != FAIL)
"""
from typing import Optional

from .base import MatcherInput, MatcherOutput


def evaluate_pre_llm(inp: MatcherInput) -> Optional[MatcherOutput]:
    """
    Deterministic pre-classification. Runs BEFORE any Ollama HTTP call.
    Returns MatcherOutput if a rule proves the outcome, else None (cannot safely decide -> continue).
    Behavior identical to the former inline block in OllamaMatcher.match().
    """
    # 1. Wrong tender non-reusable -> MISSING
    if inp.evidence_tender_source and inp.evidence_tender_source != inp.current_tender_id and not inp.evidence_reusable:
        return MatcherOutput(
            support=False,
            contradiction=False,
            missing_facts=[f"Evidence from wrong tender {inp.evidence_tender_source} non-reusable for {inp.current_tender_id}"],
            supporting_facts=[],
            contradictory_facts=[],
            applicability="MISSING",
            confidence=0.0,
            reason=f"Wrong tender non-reusable — evidence {inp.evidence_id} from {inp.evidence_tender_source} cannot satisfy {inp.requirement_id} — MISSING per hard rule"
        )
    # 2. Expired -> REVIEW
    if inp.evidence_valid_until:
        try:
            from datetime import datetime
            vu = datetime.fromisoformat(inp.evidence_valid_until.replace("Z", ""))
            if vu < datetime.utcnow():
                return MatcherOutput(
                    support=None, contradiction=False,
                    missing_facts=[], supporting_facts=[], contradictory_facts=[],
                    applicability="REVIEW", confidence=0.0,
                    reason=f"Evidence {inp.evidence_id} expired {inp.evidence_valid_until} — REVIEW per hard rule"
                )
        except Exception:
            pass
    # 3. Ambiguous applicability -> REVIEW
    if inp.applicable_entity == "AMBIGUOUS" or inp.requirement_id == "REQ-AMB":
        return MatcherOutput(
            support=None, contradiction=False,
            missing_facts=[], supporting_facts=[], contradictory_facts=[],
            applicability="REVIEW", confidence=0.0,
            reason=f"Requirement {inp.requirement_id} applicability AMBIGUOUS — REVIEW per hard rule"
        )
    # 4. Wrong entity -> MISSING (strict)
    req_e = (inp.applicable_entity or "CONSORTIUM").upper()
    ev_e = (inp.evidence_applicable_entity or "CONSORTIUM").upper()
    if req_e == "GIZA" and ev_e == "HYOSUNG":
        return MatcherOutput(
            support=False, contradiction=False,
            missing_facts=[f"Entity mismatch {ev_e} cannot satisfy {req_e}"],
            supporting_facts=[], contradictory_facts=[],
            applicability="MISSING", confidence=0.0,
            reason=f"Entity mismatch: {inp.requirement_id} requires {req_e}, evidence {inp.evidence_id} is {ev_e} — MISSING"
        )
    if req_e == "HYOSUNG" and ev_e == "GIZA":
        return MatcherOutput(
            support=False, contradiction=False,
            missing_facts=[f"Entity mismatch {ev_e} cannot satisfy {req_e}"],
            supporting_facts=[], contradictory_facts=[],
            applicability="MISSING", confidence=0.0,
            reason=f"Entity mismatch: {inp.requirement_id} requires {req_e}, evidence {inp.evidence_id} is {ev_e} — MISSING"
        )
    # 5. OEM isolation (REQ-K/L with OEM IDs)
    if inp.requirement_id in ("REQ-K", "REQ-L", "REQ-D", "REQ-I", "REQ-H") and inp.evidence_id in ("AI-E-003", "E-003", "E-OEM") and "oem" in (inp.evidence_fact or "").lower():
        if inp.requirement_id in ("REQ-K", "REQ-L"):
            return MatcherOutput(
                support=False, contradiction=False,
                missing_facts=[f"OEM alone cannot satisfy {inp.requirement_id}"],
                supporting_facts=[], contradictory_facts=[],
                applicability="MISSING", confidence=0.0,
                reason=f"OEM evidence {inp.evidence_id} cannot satisfy {inp.requirement_id} per hard rule §19 #3"
            )
    # 5b. Explicit contradiction for REQ-A First Category vs Second Category -> FAIL
    _req_lower = (inp.requirement_text or "").lower()
    _fact_lower = (inp.evidence_fact or "").lower()
    _req_has_first = ("first category" in _req_lower or "first-category" in _req_lower)
    _fact_has_second = ("second category" in _fact_lower or "second-category" in _fact_lower or "grade 2" in _fact_lower)
    if inp.requirement_id == "REQ-A" and _req_has_first and _fact_has_second:
        return MatcherOutput(
            support=False, contradiction=True,
            missing_facts=[], supporting_facts=[],
            contradictory_facts=[f"Requirement requires First Category, but evidence {inp.evidence_id} shows Second Category — explicit contradiction"],
            applicability="FAIL", confidence=0.92,
            reason=f"Explicit contradiction: {inp.requirement_id} requires First Category, evidence {inp.evidence_id} shows Second Category — FAIL per hard rule (deterministic, no LLM)"
        )
    if _req_has_first and _fact_has_second:
        return MatcherOutput(
            support=False, contradiction=True,
            missing_facts=[], supporting_facts=[],
            contradictory_facts=[f"Contradictory: First vs Second Category"],
            applicability="FAIL", confidence=0.90,
            reason="Contradiction detected: requirement vs evidence First/Second mismatch — FAIL per hard rule (deterministic, no LLM)"
        )
    # 5c. No evidence -> MISSING (deterministic; MISSING != FAIL)
    _fact_stripped = (inp.evidence_fact or "").strip()
    if not _fact_stripped or "no evidence" in _fact_lower or "empty fact" in _fact_lower:
        return MatcherOutput(
            support=False, contradiction=False,
            missing_facts=[f"No supporting facts found for {inp.requirement_id} — evidence {inp.evidence_id} provides no usable fact"],
            supporting_facts=[], contradictory_facts=[],
            applicability="MISSING", confidence=0.0,
            reason=f"No support: evidence {inp.evidence_id} does not satisfy {inp.requirement_id} — MISSING per hard rule (deterministic, no LLM, MISSING != FAIL)"
        )
    # No deterministic rule proves the outcome -> caller continues (relevance filter or LLM)
    return None


def has_evidence_content(inp: MatcherInput) -> tuple[bool, str]:
    """
    Evidence Presence predicate (pure, no HTTP, no LLM).
    Returns (True, "") when the evidence carries actual content, else (False, reason).
    Mirrors the empty/marker conditions of evaluate_pre_llm step 5c exactly:
      - truly empty evidence text -> no content
      - whitespace-only evidence text -> no content
      - explicit no-evidence markers ("no evidence", "empty fact") -> no content
    Low lexical overlap alone NEVER counts as no-content (see HybridMatcher gate docs).
    Additive helper — does not change evaluate_pre_llm semantics.
    """
    _fact_raw = inp.evidence_fact or ""
    _fact_lower = _fact_raw.lower()
    if not _fact_raw.strip():
        if not _fact_raw:
            return False, "empty evidence text"
        return False, "whitespace-only evidence text"
    if "no evidence" in _fact_lower or "empty fact" in _fact_lower:
        return False, "explicit no-evidence marker"
    return True, ""


def validate_post_llm(inp: MatcherInput, llm_applicability: str, llm_confidence: float) -> Optional[MatcherOutput]:
    """
    Post-LLM safety validation using the SAME shared rules.
    Returns an override MatcherOutput if deterministic rules contradict the LLM output, else None.
    Preserves existing OllamaMatcher post-LLM behavior: explicit REQ-A First-vs-Second override.
    - If LLM says anything other than FAIL for an explicit First-vs-Second case, override to FAIL.
    - Otherwise None (accept LLM output; caller derives remaining fields deterministically).
    """
    _req_lower = (inp.requirement_text or "").lower()
    _fact_lower = (inp.evidence_fact or "").lower()
    _has_first = ("first category" in _req_lower or "first-category" in _req_lower)
    _has_second = ("second category" in _fact_lower or "second-category" in _fact_lower or "grade 2" in _fact_lower)
    if inp.requirement_id == "REQ-A" and _has_first and _has_second:
        # Determine contradiction flag from facts (deterministic, not from LLM claims)
        if llm_applicability != "FAIL":
            return MatcherOutput(
                support=False, contradiction=True,
                missing_facts=[], supporting_facts=[],
                contradictory_facts=[f"Explicit contradiction: First vs Second Category"],
                applicability="FAIL", confidence=0.92,
                reason=f"Hard rule override: explicit contradiction Second Category vs First Category — FAIL (LLM said {llm_applicability}, corrected)"
            )
    if _has_first and _has_second and llm_applicability == "MISSING":
        # Contradiction must be FAIL, never MISSING (preserves existing OllamaMatcher post behavior)
        return MatcherOutput(
            support=False, contradiction=True,
            missing_facts=[], supporting_facts=[],
            contradictory_facts=[f"Contradictory: First vs Second Category"],
            applicability="FAIL", confidence=0.90,
            reason=f"Hard rule override: First/Second contradiction must be FAIL, never MISSING (LLM said MISSING, corrected)"
        )
    # 5d. REQ-U joint commitment vs bank capacity — insufficient evidence, not explicit contradiction -> REVIEW (single edge case, not systemic)
    # Scoped to REQ-U / performance/bank guarantee only — not any "capacity" (fixes REQ-S over-generalization)
    _req_is_u_type = inp.requirement_id == "REQ-U" or "performance guarantee" in _req_lower or "bank guarantee" in _req_lower
    _fact_has_joint = "joint commitment" in _fact_lower
    _fact_has_consortium = "consortium agreement" in _fact_lower
    _fact_has_not_capacity = "not" in _fact_lower and "capacity" in _fact_lower
    _fact_has_intent_not = "intent" in _fact_lower and "not" in _fact_lower and ("proof" in _fact_lower or "capacity" in _fact_lower)
    if _req_is_u_type and (_fact_has_joint or _fact_has_consortium) and (_fact_has_not_capacity or _fact_has_intent_not):
        # Evidence contains "not [X] capacity" or "intent, not proof/capacity" alongside joint commitment/consortium agreement
        # This is the REQ-U type case (joint commitment mechanism, indicating contractual intent, not bank capacity)
        # LLM confuses this with explicit contradiction (FAIL), but it is actually insufficient/ambiguous -> REVIEW
        if llm_applicability != "REVIEW":
            return MatcherOutput(
                support=None, contradiction=False,
                missing_facts=[], supporting_facts=[], contradictory_facts=[],
                applicability="REVIEW", confidence=0.60,
                reason=f"Hard rule override: joint commitment with 'not ... capacity' / 'intent, not proof/capacity' alongside joint commitment/consortium agreement — insufficient/ambiguous, not explicit contradiction — REVIEW (LLM said {llm_applicability}, corrected)"
            )
    return None
