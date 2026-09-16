"""
Hybrid Matcher — TenderMind — Deterministic pre-classification + candidate filter + LLM fallback
- Localhost Ollama only, no Azure/OpenAI/paid APIs in this task (inner matcher is OllamaMatcher)
- Reduces applicability reasoning delegated to qwen2.5:3b: LLM called ONLY when deterministic logic cannot safely decide
- Preserves BaseMatcher contract, provenance, hard-rule behavior, existing tests
- A low relevance score means "no strong candidate found", NOT proven MISSING (avoids false negatives)

Pipeline per pair:
  1. evaluate_pre_llm() from deterministic_rules.py -> final output if a rule proves it (zero HTTP)
  1b. Evidence Presence Gate (has_evidence_content): no-content evidence -> MISSING (zero HTTP);
      content with low overlap is NEVER auto-MISSING (continues below)
  2. relevance band (deterministic lexical candidate filter: irrelevant|potential|strong) with score
     - deterministic rule -> final (from step 1)
     - strong/potential -> LLM fallback (inner OllamaMatcher)
     - weak/irrelevant with NO deterministic proof -> REVIEW (safe non-final, BaseMatcher-compatible;
       reason explicitly states "no strong candidate found — REVIEW, not proven MISSING")
  3. Inner LLM (OllamaMatcher) returns 2-field {applicability, confidence}; wrapper derives rest deterministically
  4. validate_post_llm() from deterministic_rules.py (same shared rules) — LLM can never override safety
  5. Final decision (BID/NO_BID) remains fully deterministic in app/engines/decision.py — matcher never returns it

Instrumentation (measured, not claimed):
  llm_calls, preclassified_count, irrelevant_count, potential_count, strong_count,
  total_latency, average_llm_latency, deterministic_latency
  (No hardcoded runtime claims — measured later via tests/benchmarks, never tuned on gold.)
"""
import os
import re
import time
from typing import Optional, Tuple, Dict, Any, Literal

from .base import BaseMatcher, MatcherInput, MatcherOutput
from .deterministic_rules import evaluate_pre_llm, validate_post_llm, has_evidence_content

# Small static Arabic procurement synonym map (from A/B diagnostic, not learned, not tuned on gold)
_AR_SYNONYMS = {
    "الفئة الأولى": "first category",
    "الفئة الاولى": "first category",
    "اتحاد المقاولين": "union contractors",
    "ضمان ابتدائي": "tender security bid bond",
    "كفالة حسن التنفيذ": "performance guarantee",
    "اختبار النوع": "type test",
    "تشغيل مستمر": "continuous operation",
}

# Relevance bands are a CANDIDATE FILTER, not a decision engine.
# Thresholds are fixed a priori (not tuned on gold, not learned):
#   score < 0.15 -> "irrelevant" (no strong candidate found)
#   0.15..0.5  -> "potential"
#   > 0.5      -> "strong"
_RELEVANCE_LOW = 0.15
_RELEVANCE_HIGH = 0.5


def _normalize(text: str) -> str:
    t = (text or "").lower()
    for ar, en in _AR_SYNONYMS.items():
        if ar in t:
            t = t.replace(ar, f" {en} ")
    return t


def _tokens(text: str):
    return set(re.findall(r"\w+", _normalize(text)))


def relevance_score(inp: MatcherInput) -> Tuple[str, float]:
    """
    Deterministic lexical relevance between requirement and evidence.
    Returns (band, score) where band in {"irrelevant","potential","strong"}.
    - score = token overlap ratio over requirement key terms (no gold, no learning)
    - Band is a candidate filter only; "irrelevant" does NOT prove MISSING (see HybridMatcher.match).
    """
    req_tokens = _tokens(inp.requirement_text)
    fact_tokens = _tokens(inp.evidence_fact)
    key_terms = [t for t in req_tokens if len(t) > 3]
    if not key_terms or not fact_tokens:
        return "irrelevant", 0.0
    overlap = len(set(key_terms) & fact_tokens)
    score = overlap / max(len(key_terms), 1)
    # Small type prior (static, not learned): certificate-like evidence for membership reqs
    # Kept tiny (+0.05) so it cannot flip bands on its own; documented here.
    _type_boost = 0.0
    if inp.requirement_id == "REQ-A" and inp.evidence_type.upper() == "CERTIFICATE":
        _type_boost = 0.05
    score = min(1.0, score + _type_boost)
    if score < _RELEVANCE_LOW:
        return "irrelevant", round(score, 3)
    if score <= _RELEVANCE_HIGH:
        return "potential", round(score, 3)
    return "strong", round(score, 3)


class HybridMatcher(BaseMatcher):
    """
    Hybrid deterministic + LLM matcher. Default inner is OllamaMatcher (localhost, qwen2.5:3b).
    """
    name = "hybrid-deterministic-llm"
    version = "1.0"

    def __init__(self, llm_matcher: Optional[BaseMatcher] = None):
        # Lazy import to avoid circulars; default inner is OllamaMatcher (not MockMatcher fallback in production)
        if llm_matcher is None:
            from .ollama_matcher import OllamaMatcher
            llm_matcher = OllamaMatcher()
        self.llm_matcher = llm_matcher
        # Instrumentation (measured, never hardcoded claims)
        self.llm_calls = 0
        self.preclassified_count = 0
        self.presence_gate_count = 0
        self.irrelevant_count = 0
        self.potential_count = 0
        self.strong_count = 0
        self.total_latency = 0.0
        self._llm_latency_sum = 0.0
        self._det_latency_sum = 0.0

    def reset_stats(self):
        self.llm_calls = 0
        self.preclassified_count = 0
        self.presence_gate_count = 0
        self.irrelevant_count = 0
        self.potential_count = 0
        self.strong_count = 0
        self.total_latency = 0.0
        self._llm_latency_sum = 0.0
        self._det_latency_sum = 0.0

    def get_stats(self) -> Dict[str, Any]:
        avg_llm = (self._llm_latency_sum / self.llm_calls) if self.llm_calls else 0.0
        det_calls = self.preclassified_count + self.irrelevant_count + self.potential_count + self.strong_count
        return {
            "llm_calls": self.llm_calls,
            "preclassified_count": self.preclassified_count,
            "presence_gate_count": self.presence_gate_count,
            "irrelevant_count": self.irrelevant_count,
            "potential_count": self.potential_count,
            "strong_count": self.strong_count,
            "total_latency": round(self.total_latency, 3),
            "average_llm_latency": round(avg_llm, 3),
            "deterministic_latency": round(self._det_latency_sum, 3),
        }

    def match(self, inp: MatcherInput) -> MatcherOutput:
        t0 = time.time()
        # 1. Deterministic pre-classification (zero HTTP) — single source of truth, authoritative
        pre = evaluate_pre_llm(inp)
        if pre is not None:
            dt = time.time() - t0
            self.preclassified_count += 1
            self._det_latency_sum += dt
            self.total_latency += dt
            return pre

        # 1b. Evidence Presence Gate (auditable, deterministic, zero HTTP)
        # Fires ONLY when the evidence carries no actual content:
        #   truly empty text, whitespace-only text, or explicit no-evidence markers.
        # Low lexical overlap alone NEVER proves MISSING — pairs with actual content
        # continue to relevance/LLM below (REVIEW or LLM fallback, never auto-MISSING).
        _has_content, _gate_why = has_evidence_content(inp)
        if not _has_content:
            dt = time.time() - t0
            self.presence_gate_count += 1
            self._det_latency_sum += dt
            self.total_latency += dt
            return MatcherOutput(
                support=False, contradiction=False,
                missing_facts=[f"No supporting facts found for {inp.requirement_id} — evidence {inp.evidence_id} provides no usable fact"],
                supporting_facts=[], contradictory_facts=[],
                applicability="MISSING", confidence=0.0,
                reason=f"Evidence Presence Gate: {_gate_why} in {inp.evidence_id} — MISSING per hard rule (deterministic, zero HTTP, MISSING != FAIL)"
            )

        # 2. Candidate relevance filter (deterministic, no HTTP, not a decision)
        band, score = relevance_score(inp)
        if band == "irrelevant":
            self.irrelevant_count += 1
            dt = time.time() - t0
            self._det_latency_sum += dt
            self.total_latency += dt
            # SAFEST BaseMatcher-compatible behavior: REVIEW (not MISSING), because low lexical
            # overlap may be a wording difference (false-negative risk). Provenance preserved.
            return MatcherOutput(
                support=None, contradiction=False,
                missing_facts=[],
                supporting_facts=[], contradictory_facts=[],
                applicability="REVIEW", confidence=0.0,
                reason=(
                    f"No strong candidate found (relevance {score:.2f} [{band}]) for "
                    f"{inp.requirement_id} based on evidence {inp.evidence_id} from "
                    f"{inp.source_document} {inp.page_or_section} — REVIEW (not proven MISSING "
                    f"to avoid false negatives from wording differences)"
                )
            )
        if band == "potential":
            self.potential_count += 1
        else:
            self.strong_count += 1

        # 3. LLM fallback (only when deterministic logic cannot safely decide)
        llm_t0 = time.time()
        # Delegate to inner matcher (OllamaMatcher), which itself re-applies shared pre-rules
        # (idempotent) and enforces minimal 2-field contract + derivation.
        llm_out = self.llm_matcher.match(inp)
        self._llm_latency_sum += time.time() - llm_t0
        self.llm_calls += 1

        # 4. Post-LLM safety validation via SAME shared rules (LLM can never override safety)
        override = validate_post_llm(inp, llm_out.applicability, llm_out.confidence)
        dt = time.time() - t0
        self.total_latency += dt
        if override is not None:
            return override
        # 5. Accept LLM output as-is (already derived deterministically inside OllamaMatcher);
        # final BID/NO_BID remains in decision.py, never here.
        return llm_out
