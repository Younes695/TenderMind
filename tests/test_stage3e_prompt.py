"""
Stage 3E — Prompt Variant B/C integrity tests (no Ollama required).
Proves Variant B preserved, Variant C minimal, no new categories/tender rules.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.llm_generic_extraction import (
    LLM_SYSTEM_PROMPT, LLM_SYSTEM_PROMPT_VARIANT_C, LLM_PRIMARY_PURPOSE_CLARIFICATION,
    PROMPT_VERSION_B, PROMPT_VERSION_C, get_system_prompt, prompt_hash,
)


def test_variant_b_preserved():
    assert PROMPT_VERSION_B == "Variant B"
    assert "UNKNOWN != FALSE" in LLM_SYSTEM_PROMPT
    assert "Variant C" not in LLM_SYSTEM_PROMPT
    assert "Primary-purpose guidance" not in LLM_SYSTEM_PROMPT
    print("PASS variant B preserved")


def test_variant_c_minimal_addition():
    assert PROMPT_VERSION_C == "Variant C"
    assert LLM_SYSTEM_PROMPT_VARIANT_C.startswith(LLM_SYSTEM_PROMPT)
    added = LLM_SYSTEM_PROMPT_VARIANT_C[len(LLM_SYSTEM_PROMPT):]
    assert len(added) < 1500, f"Variant C addition must stay minimal, got {len(added)}"
    assert len(added) > 100
    print("PASS variant C minimal addition")


def test_variant_c_no_new_categories():
    for cat in ["LEGAL", "TECHNICAL", "EXPERIENCE", "EQUIPMENT", "FINANCIAL", "SCHEDULE", "COMMERCIAL", "HSE", "QA_QC", "PERSONNEL", "SUBCONTRACTOR", "SUBMISSION"]:
        assert cat in LLM_SYSTEM_PROMPT  # B already has all 12
    # C must not introduce a 13th category token like BID/NO-BID/SCORE
    added = LLM_SYSTEM_PROMPT_VARIANT_C[len(LLM_SYSTEM_PROMPT):]
    assert "BID" not in added
    assert "NO-BID" not in added
    assert "score" not in added.lower() or "scoring" not in added.lower()
    print("PASS variant C no new categories")


def test_variant_c_no_tender_specific():
    added = LLM_SYSTEM_PROMPT_VARIANT_C[len(LLM_SYSTEM_PROMPT):]
    low = added.lower()
    for term in ["mobile", "sarai", "6th october", "motawreen", "nuca", "sa-2018", "giza", "hyosung", "220kv gis switchgear", "gold-"]:
        assert term not in low, f"Tender-specific term leaked: {term}"
    print("PASS variant C no tender-specific")


def test_variant_c_preserves_unknown():
    assert "UNKNOWN != FALSE" in LLM_SYSTEM_PROMPT_VARIANT_C
    assert "never invent" in LLM_SYSTEM_PROMPT_VARIANT_C.lower()
    print("PASS variant C preserves UNKNOWN")


def test_prompt_hashes_distinct_and_stable():
    hb = prompt_hash(LLM_SYSTEM_PROMPT)
    hc = prompt_hash(LLM_SYSTEM_PROMPT_VARIANT_C)
    assert hb != hc
    assert len(hb) == 16 and len(hc) == 16
    assert prompt_hash(LLM_SYSTEM_PROMPT) == hb  # stable
    assert get_system_prompt("B") == LLM_SYSTEM_PROMPT
    assert get_system_prompt("C") == LLM_SYSTEM_PROMPT_VARIANT_C
    assert get_system_prompt("UNKNOWN_VARIANT_FALLBACK") == LLM_SYSTEM_PROMPT
    print("PASS prompt hashes distinct and stable")


def test_call_ollama_defaults_to_variant_b():
    import inspect
    from evaluation import llm_generic_extraction as m
    sig = inspect.signature(m.call_ollama_for_chunk)
    assert "system_prompt" in sig.parameters
    # Default must be None -> Variant B inside function
    assert sig.parameters["system_prompt"].default is None
    print("PASS call_ollama defaults to Variant B")


if __name__ == "__main__":
    test_variant_b_preserved()
    test_variant_c_minimal_addition()
    test_variant_c_no_new_categories()
    test_variant_c_no_tender_specific()
    test_variant_c_preserves_unknown()
    test_prompt_hashes_distinct_and_stable()
    test_call_ollama_defaults_to_variant_b()
    print("\nAll 7 Stage 3E prompt tests passed")
