"""
Stage 3F — Variant D prompt integrity tests (no Ollama required).
Proves Variant D is B + exactly one structural line, no category guidance drift.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.llm_generic_extraction import (
    LLM_SYSTEM_PROMPT, LLM_SYSTEM_PROMPT_VARIANT_D, LLM_STRUCTURAL_INSTRUCTION,
    PROMPT_VERSION_B, PROMPT_VERSION_D, get_system_prompt, prompt_hash,
)

EXPECTED_LINE = "Extract all distinct requirements present in the supplied chunk; do not stop after identifying only one requirement."


def test_variant_b_unchanged():
    assert PROMPT_VERSION_B == "Variant B"
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
    assert "UNKNOWN != FALSE" in LLM_SYSTEM_PROMPT
    print("PASS variant B unchanged")


def test_variant_d_single_structural_line():
    assert PROMPT_VERSION_D == "Variant D"
    assert LLM_SYSTEM_PROMPT_VARIANT_D.startswith(LLM_SYSTEM_PROMPT)
    added = LLM_SYSTEM_PROMPT_VARIANT_D[len(LLM_SYSTEM_PROMPT):]
    assert EXPECTED_LINE in added
    # Only one instruction: no category examples, definitions, or priorities
    assert "-> EXPERIENCE" not in added
    assert "-> FINANCIAL" not in added
    assert "-> LEGAL" not in added
    assert "-> PERSONNEL" not in added
    assert "-> COMMERCIAL" not in added
    assert "-> SCHEDULE" not in added
    assert "-> TECHNICAL" not in added
    print("PASS variant D single structural line")


def test_variant_d_no_category_guidance():
    added = LLM_SYSTEM_PROMPT_VARIANT_D[len(LLM_SYSTEM_PROMPT):]
    low = added.lower()
    # No category definitions or examples smuggled in
    assert "primary purpose" not in low or "business/contractual" not in low
    assert "few-shot" not in low
    assert "example" not in low
    print("PASS variant D no category guidance")


def test_variant_d_no_tender_terms():
    added = LLM_SYSTEM_PROMPT_VARIANT_D[len(LLM_SYSTEM_PROMPT):]
    low = added.lower()
    for term in ["mobile", "sarai", "6th october", "motawreen", "nuca", "gold-", "bid", "no-bid", "score"]:
        assert term not in low, f"Tender/scoring term leaked: {term}"
    print("PASS variant D no tender terms")


def test_variant_d_preserves_unknown():
    assert "UNKNOWN != FALSE" in LLM_SYSTEM_PROMPT_VARIANT_D
    print("PASS variant D preserves UNKNOWN")


def test_prompt_hashes():
    hb = prompt_hash(LLM_SYSTEM_PROMPT)
    hd = prompt_hash(LLM_SYSTEM_PROMPT_VARIANT_D)
    assert hb == "9aa3e11254f672cd"
    assert hd != hb
    assert len(hd) == 16
    assert get_system_prompt("B") == LLM_SYSTEM_PROMPT
    assert get_system_prompt("D") == LLM_SYSTEM_PROMPT_VARIANT_D
    assert get_system_prompt("NOPE") == LLM_SYSTEM_PROMPT
    print(f"PASS prompt hashes B={hb} D={hd}")


def test_call_defaults_to_b():
    import inspect
    from evaluation import llm_generic_extraction as m
    sig = inspect.signature(m.call_ollama_for_chunk)
    assert sig.parameters["system_prompt"].default is None
    print("PASS call defaults to B")


if __name__ == "__main__":
    test_variant_b_unchanged()
    test_variant_d_single_structural_line()
    test_variant_d_no_category_guidance()
    test_variant_d_no_tender_terms()
    test_variant_d_preserves_unknown()
    test_prompt_hashes()
    test_call_defaults_to_b()
    print("\nAll 7 Stage 3F prompt tests passed")
