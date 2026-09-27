"""
Stage 3G — Capability harness integrity tests (no Ollama required).
Proves Task A/B share fixtures/controls and production is untouched.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.stage3g.classification_tasks import (
    ALLOWED_LABELS, TASK_A_SYSTEM, TASK_B_SYSTEM, TASK_B_DEFINITIONS,
    TIMEOUT_SECONDS, build_user_message, normalize_output,
)


def test_exact_allowed_labels():
    assert ALLOWED_LABELS == [
        "LEGAL", "EXPERIENCE", "FINANCIAL", "PERSONNEL", "COMMERCIAL", "SCHEDULE",
        "TECHNICAL", "HSE", "QA_QC", "EQUIPMENT", "SUBCONTRACTOR", "SUBMISSION",
        "UNKNOWN",
    ]
    print("PASS exact allowed labels")


def test_task_a_has_no_definitions():
    low = TASK_A_SYSTEM.lower()
    for phrase in ["power of attorney", "turnover", "past projects", "reference projects",
                   "payment, price", "bid security", "delivery, completion",
                   "technical specifications", "quality assurance"]:
        assert phrase not in low, f"Task A leaked definition: {phrase}"
    print("PASS Task A has no category-specific definitions")


def test_task_b_only_intended_definitions():
    assert TASK_B_SYSTEM.startswith(TASK_A_SYSTEM)
    added = TASK_B_SYSTEM[len(TASK_A_SYSTEM):]
    assert len(added) < 1500, f"Task B definitions must stay concise, got {len(added)}"
    for token in ["LEGAL =", "EXPERIENCE =", "FINANCIAL =", "PERSONNEL =", "COMMERCIAL =",
                  "SCHEDULE =", "TECHNICAL =", "HSE =", "QA_QC =", "EQUIPMENT =",
                  "SUBCONTRACTOR =", "SUBMISSION =", "UNKNOWN ="]:
        assert token in added, f"Missing definition: {token}"
    low = added.lower()
    for term in ["mobile", "sarai", "6th october", "motawreen", "nuca", "gold-", "220kv gis switchgear"]:
        assert term not in low, f"Tender-specific leak in Task B: {term}"
    print("PASS Task B contains only intended concise definitions")


def test_same_fixture_both_tasks():
    import json
    snippets = json.loads((Path(__file__).resolve().parents[1] / "evaluation" / "stage3g" / "snippets_3g.json").read_text(encoding="utf-8"))
    assert len(snippets) == 12
    for s in snippets:
        assert s["category_gold"] in ALLOWED_LABELS
        assert s["source_text"] and s["source_document"]
    # Every snippet text must occur verbatim in the representative fixture file
    rep = (Path(__file__).resolve().parents[1] / "evaluation" / "fixtures" / "mobile_llm_representative.json").read_text(encoding="utf-8")
    for s in snippets:
        assert s["source_text"] in rep, f"Snippet not verbatim in fixture: {s['test_id']}"
    print("PASS same fixture set used by A and B (verbatim)")


def test_no_production_variant_mutation():
    from evaluation.llm_generic_extraction import (
        LLM_SYSTEM_PROMPT, prompt_hash, get_system_prompt,
    )
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
    assert get_system_prompt("B") == LLM_SYSTEM_PROMPT
    print("PASS no production Variant B/C/D mutation")


def test_no_production_behavior_change():
    import inspect
    from evaluation import llm_generic_extraction as m
    assert m.get_ollama_model() == "qwen2.5:3b"
    assert inspect.signature(m.call_ollama_for_chunk).parameters["system_prompt"].default is None
    print("PASS no TenderMind production behavior change")


def test_normalize_never_coerces():
    assert normalize_output("TECHNICAL")[0] == "TECHNICAL"
    assert normalize_output("  commercial  ")[0] == "COMMERCIAL"
    assert normalize_output("```\nFINANCIAL\n```")[0] == "FINANCIAL"
    assert normalize_output("BID")[0] is None
    assert normalize_output("")[0] is None
    assert normalize_output(None)[0] is None
    print("PASS normalize never coerces")


if __name__ == "__main__":
    test_exact_allowed_labels()
    test_task_a_has_no_definitions()
    test_task_b_only_intended_definitions()
    test_same_fixture_both_tasks()
    test_no_production_variant_mutation()
    test_no_production_behavior_change()
    test_normalize_never_coerces()
    print("\nAll 7 Stage 3G tests passed")
