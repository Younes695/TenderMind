"""
Optional Future OpenAI / Azure OpenAI Matcher — TenderMind
- Implements BaseMatcher interface for LLM-assisted structured comparison
- DO NOT call in offline tests — would incur API costs and network inference
- Strict JSON output contract, validated via MatcherOutput
- LLM NEVER decides BID/NO_BID — only requirement/evidence matching
- Requires valid API key (sk-proj-... or Azure OpenAI), never logs secret
- This file is a provider stub — ready for future paid inference, but offline tests use mock_matcher.py
"""
import os
from typing import Optional

from .base import BaseMatcher, MatcherInput, MatcherOutput

# Prompt version per AI Evaluation Contract v1
PROMPT_VERSION = "v4 Hybrid LLM v1.0"
MODEL_DEFAULT = "gpt-4o"
PROMPT_TEMPLATE = """You are Arabic tender requirement-evidence matcher.
Input ONLY: requirement text + candidate evidence fact + provenance/context.
Requirement: {requirement_text} (ID: {requirement_id}, Category: {requirement_category}, Type: {requirement_type}, Mandatory: {mandatory}, Applicable: {applicable_entity})
Evidence: {evidence_fact} (ID: {evidence_id}, Type: {evidence_type}, Applicable: {evidence_applicable_entity}, Valid until: {valid_until}, Source: {source_document} {page_or_section})

Task: Compare evidence fact to requirement. Output strict JSON:
{{"support": true/false/null, "contradiction": true/false, "missing_facts": [], "supporting_facts": [], "contradictory_facts": [], "applicability": "PASS|FAIL|REVIEW|MISSING", "confidence": 0.0, "reason": "..."}}
Hard rules remain authoritative: MISSING != FAIL, etc. LLM must NOT decide BID.
- support: true if evidence strongly supports requirement, false if not, null if ambiguous
- contradiction: true if evidence explicitly contradicts requirement (e.g., Second Category vs First)
- applicability: PASS if fully satisfies, FAIL if contradicts, MISSING if no support, REVIEW if ambiguous/expired/wrong entity
- confidence: 0.0-1.0
- reason: human-readable why
Do NOT invent evidence. Preserve provenance. Respond ONLY with JSON.
"""

class OpenAIMatcher(BaseMatcher):
    """
    Future paid provider — DO NOT instantiate in offline tests without valid key.
    Cost warning: Each match is one LLM call (21 req × 4 ev = 84 calls per tender, ~8k input + 2k output tokens ≈ $0.04/tender via GPT-4o).
    """
    name = "openai-gpt-4o"
    version = PROMPT_VERSION

    def __init__(self, api_key: Optional[str] = None, model: str = MODEL_DEFAULT, endpoint: Optional[str] = None, api_version: Optional[str] = None):
        # Read from env if not provided, but never log key
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
        self.model = model
        self.endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.api_version = api_version or os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self._client = None
        # Do NOT validate key here to avoid network; validation is lazy on first match()
        if self.api_key and self.api_key.startswith("sk-svcacct-"):
            raise ValueError("OPENAI_API_KEY starts with sk-svcacct-* which is invalid for OpenAI API (per v4, must be sk-proj-...). See docs/AI_Evaluation_Run_Sarai_Real_v4.md for correct key format. This matcher will not be called in offline tests.")

    def _get_client(self):
        if self._client:
            return self._client
        if not self.api_key:
            raise RuntimeError("OpenAI/Azure OpenAI API key not configured — set OPENAI_API_KEY=sk-proj-... or AZURE_OPENAI_* in env (see docs). This is expected in offline tests — use MockMatcher instead.")
        # Check for placeholder/demo keys
        if self.api_key.strip().startswith("sk-svcacct-"):
            raise RuntimeError("Invalid OPENAI_API_KEY sk-svcacct-* — must be sk-proj-... per v4 docs")
        try:
            if self.endpoint:
                # Azure OpenAI
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.api_key,
                    api_version=self.api_version
                )
            else:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            return self._client
        except Exception as e:
            raise RuntimeError(f"OpenAI client init failed: {type(e).__name__}: {e}") from e

    def match(self, inp: MatcherInput) -> MatcherOutput:
        """
        Would call LLM for structured comparison — DO NOT call in offline tests.
        This method is intentionally not executed in cost-guardrailed tasks.
        If called without valid credentials, it raises with safe message (no key logged).
        Requires BOTH TENDERMIND_MATCHER_PROVIDER=openai AND TENDERMIND_ENABLE_LLM=1 (strengthened opt-in).
        Default behavior remains offline/mock — having OPENAI_API_KEY alone NEVER triggers network.
        """
        # Safety: Require BOTH explicit opt-in flags before any paid inference
        provider = os.environ.get("TENDERMIND_MATCHER_PROVIDER", "").lower()
        enabled = os.environ.get("TENDERMIND_ENABLE_LLM", "").lower()
        if provider != "openai" or enabled not in ("1", "true", "yes"):
            raise RuntimeError(
                "OpenAIMatcher.match() is disabled — requires BOTH TENDERMIND_MATCHER_PROVIDER=openai AND TENDERMIND_ENABLE_LLM=1 to enable paid LLM inference. "
                "Default is offline/mock. Having OPENAI_API_KEY alone NEVER triggers network. "
                "Set both flags explicitly to opt-in. Use MockMatcher for offline tests."
            )
        client = self._get_client()
        # Build prompt
        prompt = PROMPT_TEMPLATE.format(
            requirement_text=inp.requirement_text,
            requirement_id=inp.requirement_id,
            requirement_category=inp.requirement_category,
            requirement_type=inp.requirement_type,
            mandatory=inp.mandatory,
            applicable_entity=inp.applicable_entity,
            evidence_fact=inp.evidence_fact,
            evidence_id=inp.evidence_id,
            evidence_type=inp.evidence_type,
            evidence_applicable_entity=inp.evidence_applicable_entity,
            valid_until=inp.evidence_valid_until or "N/A",
            source_document=inp.source_document,
            page_or_section=inp.page_or_section
        )
        try:
            # Real LLM call — would incur cost, strictly JSON mode
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict JSON matcher. Output ONLY valid JSON per the requested schema."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=500,
                response_format={"type": "json_object"} if "gpt-4" in self.model else None
            )
            content = resp.choices[0].message.content or "{}"
            import json
            data = json.loads(content)
            # Validate via MatcherOutput
            return MatcherOutput.model_validate(data)
        except Exception as e:
            # Safe fallback: return REVIEW with reason, never raise, never invent BID
            # Do not log key, only len
            key_len = len(self.api_key.strip()) if self.api_key else 0
            return MatcherOutput(
                support=None,
                contradiction=False,
                missing_facts=[f"LLM call failed: {type(e).__name__}: {str(e)[:200]}"],
                supporting_facts=[],
                contradictory_facts=[],
                applicability="REVIEW",
                confidence=0.0,
                reason=f"LLM matcher error (key len {key_len}, model {self.model}) — requires human review: {type(e).__name__}"
            )

# For backward compatibility, alias
AzureOpenAIMatcher = OpenAIMatcher
