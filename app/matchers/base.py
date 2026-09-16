"""
Matcher Interface — TenderMind
- Clean provider abstraction for requirement-evidence matching
- Exact structured output contract per spec
- Strict validation, safe handling of malformed/null/ambiguous
- Matcher NEVER produces final BID/NO_BID — only requirement/evidence level
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ValidationError, field_validator
import re

# Exact output contract per task
class MatcherOutput(BaseModel):
    """
    {
      "support": true|false|null,
      "contradiction": true|false,
      "missing_facts": [],
      "supporting_facts": [],
      "contradictory_facts": [],
      "applicability": "PASS|FAIL|REVIEW|MISSING",
      "confidence": 0.0,
      "reason": "..."
    }
    """
    support: Optional[bool] = Field(None, description="Does evidence support requirement? true/false/null (null=ambiguous)")
    contradiction: bool = Field(..., description="Does evidence explicitly contradict requirement?")
    missing_facts: List[str] = Field(default_factory=list)
    supporting_facts: List[str] = Field(default_factory=list)
    contradictory_facts: List[str] = Field(default_factory=list)
    applicability: Literal["PASS", "FAIL", "REVIEW", "MISSING"] = Field(..., description="Evidence applicability to requirement")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence 0.0-1.0")
    reason: str = Field(..., min_length=1, description="Human-readable why")

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be 0.0-1.0")
        return v

    @field_validator("applicability")
    @classmethod
    def check_applicability(cls, v):
        if v not in ("PASS", "FAIL", "REVIEW", "MISSING"):
            raise ValueError("applicability must be PASS|FAIL|REVIEW|MISSING")
        return v

class MatcherInput(BaseModel):
    requirement_id: str
    requirement_text: str
    requirement_category: str = "UNKNOWN"
    requirement_type: str = "UNKNOWN"
    mandatory: bool = True
    applicable_entity: str = "CONSORTIUM"
    evidence_id: str
    evidence_fact: str
    evidence_type: str = "OTHER"
    evidence_applicable_entity: str = "CONSORTIUM"
    evidence_valid_until: Optional[str] = None  # ISO date or None
    evidence_reusable: bool = True
    evidence_tender_source: Optional[str] = None
    current_tender_id: str = "SA-2018-HV2"
    source_document: str = ""
    page_or_section: str = ""

class BaseMatcher(ABC):
    """
    Clean interface — any provider (mock, TF-IDF, OpenAI, Azure OpenAI) must implement match().
    - Takes MatcherInput (requirement + evidence + provenance)
    - Returns MatcherOutput (strict contract)
    - NEVER returns BID/NO_BID — only requirement/evidence level
    - Must preserve semantics: MISSING != FAIL, etc. — enforced by deterministic layer after matcher
    """
    name: str = "base"
    version: str = "1.0"

    @abstractmethod
    def match(self, inp: MatcherInput) -> MatcherOutput:
        pass

    def safe_match(self, inp: MatcherInput) -> MatcherOutput:
        """
        Safe wrapper: validates input, calls match(), validates output, handles malformed/null/ambiguous
        Returns REVIEW with low confidence on any failure, never raises, never invents BID
        """
        try:
            # Validate input (pydantic will raise if malformed)
            if not isinstance(inp, MatcherInput):
                inp = MatcherInput.model_validate(inp)
        except Exception as e:
            return MatcherOutput(
                support=None,
                contradiction=False,
                missing_facts=[f"Invalid input: {e}"],
                supporting_facts=[],
                contradictory_facts=[],
                applicability="REVIEW",
                confidence=0.0,
                reason=f"Input validation failed — ambiguous, requires human review: {e}"
            )
        try:
            out = self.match(inp)
            # Ensure output is MatcherOutput (validate)
            if not isinstance(out, MatcherOutput):
                # Try to parse dict
                if isinstance(out, dict):
                    out = MatcherOutput.model_validate(out)
                else:
                    raise ValueError(f"Matcher returned {type(out)}, not MatcherOutput")
            # Strict validation already done by pydantic, but double-check
            return out
        except ValidationError as e:
            # Safe fallback for malformed matcher output
            return MatcherOutput(
                support=None,
                contradiction=False,
                missing_facts=[f"Malformed matcher output: {e}"],
                supporting_facts=[],
                contradictory_facts=[],
                applicability="REVIEW",
                confidence=0.0,
                reason=f"Matcher output validation failed — ambiguous, requires human review: {e}"
            )
        except Exception as e:
            return MatcherOutput(
                support=None,
                contradiction=False,
                missing_facts=[f"Matcher error: {e}"],
                supporting_facts=[],
                contradictory_facts=[],
                applicability="REVIEW",
                confidence=0.0,
                reason=f"Matcher exception — requires human review: {type(e).__name__}: {e}"
            )

# Helper for deterministic hard rules (preserved semantics) — matcher should NOT bypass these
# These are enforced AFTER matcher, in status.py, but we document here for clarity
HARD_RULES = {
    "MISSING != FAIL": "If no applicable evidence, status must be MISSING_EVIDENCE, never FAIL",
    "RISK != NO_BID": "Risk always REVIEW, never NO_BID (enforced in decision.py)",
    "contradiction -> FAIL": "If matcher says contradiction=true and applicability=FAIL, status may be FAIL at requirement level, but final decision still via deterministic hierarchy",
    "ambiguity -> REVIEW": "If applicability=REVIEW or support=null, status must be REVIEW",
    "wrong_tender -> ignore": "If evidence_tender_source != current and reusable=False, evidence must be ignored (MISSING)",
    "expired -> REVIEW": "If valid_until < now, must be REVIEW not PASS",
    "wrong_entity -> MISSING": "If evidence_applicable_entity != requirement_applicable_entity (strict), must be MISSING",
}
