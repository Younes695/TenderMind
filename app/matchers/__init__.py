"""
Matcher package — TenderMind
- base: interface + output contract
- mock_matcher: deterministic offline provider for tests
- openai_matcher: future paid provider (not called in offline tests)
"""
from .base import BaseMatcher, MatcherInput, MatcherOutput
from .mock_matcher import MockMatcher
from .openai_matcher import OpenAIMatcher, AzureOpenAIMatcher
from .deterministic_rules import evaluate_pre_llm, validate_post_llm, has_evidence_content
from .hybrid_matcher import HybridMatcher, relevance_score

__all__ = ["BaseMatcher", "MatcherInput", "MatcherOutput", "MockMatcher", "OpenAIMatcher", "AzureOpenAIMatcher",
           "evaluate_pre_llm", "validate_post_llm", "has_evidence_content", "HybridMatcher", "relevance_score"]
