"""
Deterministic Mock Matcher — TenderMind — TEST FIXTURE ONLY
- For offline unit tests ONLY — deterministic, no external API, no cost, no network
- Implements BaseMatcher with deterministic, explainable logic for test coverage
- NOT evidence that semantic matching acceptance criteria (Matching macro F1 >=0.93) are achieved
- Real semantic matching requires LLM provider (OpenAIMatcher) with valid API key and measured benchmark; MockMatcher is a heuristic stub for test isolation
- Respects all preserved semantics (MISSING != FAIL etc. via output, but final decision still via status.py)
- See docs/Matcher_Provider_Guide.md for provider abstraction and cost warning
"""
from typing import List
from datetime import datetime
import re

from .base import BaseMatcher, MatcherInput, MatcherOutput

class MockMatcher(BaseMatcher):
    name = "mock-deterministic"
    version = "1.0"

    def match(self, inp: MatcherInput) -> MatcherOutput:
        # --- Hard rule checks FIRST (must not be bypassed) ---
        # Wrong tender non-reusable -> MISSING
        if inp.evidence_tender_source and inp.evidence_tender_source != inp.current_tender_id and not inp.evidence_reusable:
            return MatcherOutput(
                support=False,
                contradiction=False,
                missing_facts=[f"No applicable evidence — evidence from wrong tender {inp.evidence_tender_source} is non-reusable for {inp.current_tender_id}"],
                supporting_facts=[],
                contradictory_facts=[],
                applicability="MISSING",
                confidence=0.0,
                reason=f"Wrong tender non-reusable evidence from {inp.evidence_tender_source} cannot satisfy {inp.requirement_id} for {inp.current_tender_id} — requires human review if reusable, else MISSING per hard rule"
            )

        # Expired evidence -> REVIEW (not PASS)
        if inp.evidence_valid_until:
            try:
                vu = datetime.fromisoformat(inp.evidence_valid_until.replace("Z", ""))
                if vu < datetime.utcnow():
                    return MatcherOutput(
                        support=None,
                        contradiction=False,
                        missing_facts=[],
                        supporting_facts=[],
                        contradictory_facts=[],
                        applicability="REVIEW",
                        confidence=0.0,
                        reason=f"Evidence {inp.evidence_id} expired on {inp.evidence_valid_until} — historical validity not current, requires human review"
                    )
            except Exception:
                pass  # If date parse fails, ignore and continue

        # Ambiguous applicability -> REVIEW
        if inp.applicable_entity == "AMBIGUOUS" or inp.requirement_id == "REQ-AMB":
            return MatcherOutput(
                support=None,
                contradiction=False,
                missing_facts=[],
                supporting_facts=[],
                contradictory_facts=[],
                applicability="REVIEW",
                confidence=0.0,
                reason=f"Requirement {inp.requirement_id} applicability is AMBIGUOUS (Consortium vs Lead vs OEM unclear per spec §19 #6) — requires human review"
            )

        # Wrong entity -> MISSING (strict)
        req_entity = (inp.applicable_entity or "CONSORTIUM").upper()
        ev_entity = (inp.evidence_applicable_entity or "CONSORTIUM").upper()
        if req_entity == "GIZA" and ev_entity == "HYOSUNG":
            return MatcherOutput(
                support=False,
                contradiction=False,
                missing_facts=[f"Evidence entity {ev_entity} cannot satisfy GIZA-specific requirement {inp.requirement_id}"],
                supporting_facts=[],
                contradictory_facts=[],
                applicability="MISSING",
                confidence=0.0,
                reason=f"Entity mismatch: requirement {inp.requirement_id} requires {req_entity}, but evidence {inp.evidence_id} is {ev_entity} — must be GIZA per hard rule"
            )
        if req_entity == "HYOSUNG" and ev_entity == "GIZA":
            return MatcherOutput(
                support=False,
                contradiction=False,
                missing_facts=[f"Evidence entity {ev_entity} cannot satisfy HYOSUNG-specific requirement"],
                supporting_facts=[],
                contradictory_facts=[],
                applicability="MISSING",
                confidence=0.0,
                reason=f"Entity mismatch: {inp.requirement_id} requires {req_entity}, evidence is {ev_entity}"
            )

        # --- OEM isolation: OEM evidence (J) must not satisfy K/L/D/I ---
        # If requirement is K/L/D/I and evidence is OEM (J), then missing
        if inp.requirement_id in ("REQ-K", "REQ-L", "REQ-D", "REQ-I", "REQ-H") and inp.evidence_id in ("AI-E-003", "E-003", "E-OEM") and "oem" in inp.evidence_fact.lower():
            # Check if requirement is type-test/operating reference vs OEM
            # OEM fact should not satisfy these
            if inp.requirement_id in ("REQ-K", "REQ-L"):
                return MatcherOutput(
                    support=False,
                    contradiction=False,
                    missing_facts=[f"OEM evidence does not satisfy {inp.requirement_id} ({inp.requirement_text[:60]}...) — requires type-test/operating reference, not OEM linkage"],
                    supporting_facts=[],
                    contradictory_facts=[],
                    applicability="MISSING",
                    confidence=0.0,
                    reason=f"OEM evidence {inp.evidence_id} cannot satisfy {inp.requirement_id} per spec §19 #3 — type-test/operating refs require separate certificates"
                )

        # --- Contradiction detection ---
        req_lower = (inp.requirement_text or "").lower()
        fact_lower = (inp.evidence_fact or "").lower()

        # Explicit contradiction for REQ-A: First Category required, but Second Category provided
        if inp.requirement_id == "REQ-A":
            has_first_req = "first category" in req_lower or "first-category" in req_lower
            has_second_fact = "second category" in fact_lower or "grade 2" in fact_lower
            has_first_fact = "first category" in fact_lower or "grade 1" in fact_lower
            if has_first_req and has_second_fact:
                return MatcherOutput(
                    support=False,
                    contradiction=True,
                    missing_facts=[],
                    supporting_facts=[],
                    contradictory_facts=[f"Requirement requires First Category, but evidence {inp.evidence_id} shows Second Category — explicit contradiction"],
                    applicability="FAIL",
                    confidence=0.92,
                    reason=f"Explicit contradiction: {inp.requirement_id} requires First Category, evidence {inp.evidence_id} shows Second Category — FAIL per hard rule"
                )
            if has_first_req and has_first_fact:
                return MatcherOutput(
                    support=True,
                    contradiction=False,
                    missing_facts=[],
                    supporting_facts=[f"Evidence {inp.evidence_id} shows First Category — matches requirement"],
                    contradictory_facts=[],
                    applicability="PASS",
                    confidence=0.95,
                    reason=f"Strong support: First Category evidence matches {inp.requirement_id} — PASS with provenance {inp.source_document} {inp.page_or_section}"
                )

        # Generic contradiction: if evidence says "Second Category" for any First Category requirement, or "Grade 2" vs "Grade 1"
        if "first category" in req_lower and "second category" in fact_lower:
            return MatcherOutput(
                support=False, contradiction=True,
                missing_facts=[], supporting_facts=[], contradictory_facts=[f"Contradictory: First vs Second Category"],
                applicability="FAIL", confidence=0.90,
                reason="Contradiction detected: requirement vs evidence First/Second mismatch"
            )

        # --- Strong support detection (keyword overlap) ---
        # For known passing cases: REQ-B (origin South Korea), REQ-J (OEM), REQ-R (consortium)
        if inp.requirement_id == "REQ-B" and "south korea" in fact_lower and "origin" in req_lower:
            return MatcherOutput(
                support=True, contradiction=False,
                missing_facts=[], supporting_facts=[f"Hyosung South Korea within approved origin list (Europe, South Korea, Japan, North America)"],
                contradictory_facts=[], applicability="PASS", confidence=0.92,
                reason="Strong support: South Korea origin satisfies approved list — PASS"
            )
        if inp.requirement_id == "REQ-J" and ("oem" in fact_lower or "manufacturer" in fact_lower):
            return MatcherOutput(
                support=True, contradiction=False,
                missing_facts=[], supporting_facts=[f"OEM linkage: Hyosung is manufacturer for GIS"],
                contradictory_facts=[], applicability="PASS", confidence=0.88,
                reason="Strong support: OEM relationship evidenced — PASS"
            )
        if inp.requirement_id == "REQ-R" and ("consortium" in fact_lower and "joint" in fact_lower):
            return MatcherOutput(
                support=True, contradiction=False,
                missing_facts=[], supporting_facts=[f"Consortium with joint and several liability"],
                contradictory_facts=[], applicability="PASS", confidence=0.95,
                reason="Strong support: Consortium agreement with joint liability — PASS"
            )
        if inp.requirement_id == "REQ-U" and "joint" in fact_lower and "liability" in fact_lower:
            # Joint liability is REVIEW not PASS per spec §19 #1 (structural, not bank capacity)
            return MatcherOutput(
                support=None, contradiction=False,
                missing_facts=[], supporting_facts=["Joint commitment indicates intent, not bank capacity"],
                contradictory_facts=[], applicability="REVIEW", confidence=0.60,
                reason="Ambiguous: joint liability shows intent, not proof of bank guarantee capacity — REVIEW per spec §19 #1"
            )
        if inp.requirement_id == "REQ-C" and ("5,700,000" in fact_lower or "5700000" in fact_lower or "egp 5,700" in fact_lower):
            return MatcherOutput(
                support=True, contradiction=False,
                missing_facts=[], supporting_facts=[f"Tender security EGP 5,700,000 found"],
                contradictory_facts=[], applicability="PASS", confidence=0.90,
                reason="Strong support: Tender security amount matches"
            )

        # Generic support: if requirement and fact share significant keywords
        # Simple token overlap for strong support
        req_tokens = set(re.findall(r"\w+", req_lower))
        fact_tokens = set(re.findall(r"\w+", fact_lower))
        overlap = len(req_tokens & fact_tokens)
        # If evidence fact is very short or generic, not strong
        if overlap >= 3 and len(fact_lower) > 20:
            # Check if fact is at least 30% overlap with requirement's key terms
            key_terms = [t for t in req_tokens if len(t) > 3]
            if key_terms and overlap / len(key_terms) > 0.3:
                return MatcherOutput(
                    support=True, contradiction=False,
                    missing_facts=[], supporting_facts=[f"Keyword overlap {overlap} terms: {', '.join(list(req_tokens & fact_tokens)[:3])}"],
                    contradictory_facts=[], applicability="PASS", confidence=0.75,
                    reason=f"Strong semantic support: {overlap} overlapping terms between requirement and evidence"
                )

        # --- Missing evidence (default) ---
        # If no strong support or contradiction, and no hard rule triggered, then missing
        return MatcherOutput(
            support=False,
            contradiction=False,
            missing_facts=[f"No supporting facts found for {inp.requirement_id} — evidence {inp.evidence_id} does not contain required terms"],
            supporting_facts=[],
            contradictory_facts=[],
            applicability="MISSING",
            confidence=0.0,
            reason=f"No support: evidence {inp.evidence_id} does not satisfy {inp.requirement_id} — MISSING per hard rule (no invented evidence)"
        )
