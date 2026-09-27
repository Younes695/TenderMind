"""
Stage 3H — Single-requirement fixture/harness integrity tests (no Ollama required).
Proves A/B/C share one fixture, one requirement per snippet, allowed categories,
and no production Variant/mutation.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.stage3h.single_req_tasks import (
    ALLOWED_CATEGORIES, TASK_A_SYSTEM, TASK_B_SYSTEM,
    TIMEOUT_SECONDS, parse_single_requirement,
)


def _fixture():
    import json
    return json.loads((Path(__file__).resolve().parents[1] / "evaluation" / "stage3h" / "snippets_3h.json").read_text(encoding="utf-8"))


def test_fixture_consistency_across_abc():
    snippets = _fixture()
    assert 12 <= len(snippets) <= 20, f"Expected 12-20 snippets, got {len(snippets)}"
    ids = [s["test_id"] for s in snippets]
    assert len(set(ids)) == len(ids), "test_ids must be unique (fixed order A/B/C)"
    for s in snippets:
        for field in ("test_id", "category_gold", "source_document", "page", "source_text", "selection_reason"):
            assert field in s and s[field], f"Missing {field} in {s.get('test_id')}"
    print("PASS fixture consistency across A/B/C")


def test_exactly_one_requirement_per_snippet():
    snippets = _fixture()
    for s in snippets:
        # Single short requirement: no embedded second requirement sentence with a different signal.
        # Heuristic: snippet must be short (<300 chars) and contain at most 2 sentence terminators.
        assert len(s["source_text"]) < 300, f"Too long for single requirement: {s['test_id']}"
        assert s["source_text"].count(".") <= 2, f"Multiple sentences in {s['test_id']}"
    print("PASS exactly one requirement per snippet")


def test_allowed_categories():
    snippets = _fixture()
    for s in snippets:
        assert s["category_gold"] in ALLOWED_CATEGORIES, f"Bad gold category {s['test_id']}"
    for label in ("LEGAL", "TECHNICAL", "UNKNOWN"):
        assert label in ALLOWED_CATEGORIES
    print("PASS allowed categories")


def test_snippets_verbatim_in_fixture():
    import json as _json
    snippets = _fixture()
    rep = (Path(__file__).resolve().parents[1] / "evaluation" / "fixtures" / "mobile_llm_representative.json").read_text(encoding="utf-8")
    for s in snippets:
        assert s["source_text"] in rep, f"Snippet not verbatim in fixture: {s['test_id']}"
    print("PASS snippets verbatim in fixture")


def test_no_mutation_of_variant_b():
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash, get_system_prompt
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
    assert get_system_prompt("B") == LLM_SYSTEM_PROMPT
    print("PASS no mutation of Variant B")


def test_no_production_behavior_changes():
    import inspect
    from evaluation import llm_generic_extraction as m
    assert m.get_ollama_model() == "qwen2.5:3b"
    assert inspect.signature(m.call_ollama_for_chunk).parameters["system_prompt"].default is None
    print("PASS no production behavior changes")


def test_task_prompts_generic():
    for name, prompt in (("A", TASK_A_SYSTEM), ("B", TASK_B_SYSTEM)):
        low = prompt.lower()
        for term in ["mobile", "sarai", "6th october", "motawreen", "nuca", "gold-", "220kv gis switchgear"]:
            assert term not in low, f"Tender-specific leak in Task {name}: {term}"
    assert "UNKNOWN" in TASK_A_SYSTEM
    print("PASS task prompts generic")


def test_parse_single_requirement_never_coerces():
    req, status = parse_single_requirement('{"requirements": [{"summary": "Test", "category": "TECHNICAL", "mandatory": null, "applicable_entity": null}]}')
    assert status == "ok" and req["category"] == "TECHNICAL"
    _, status = parse_single_requirement('{"requirements": [{"summary": "Test", "category": "BID"}]}')
    assert status == "bad_category"
    _, status = parse_single_requirement('{"requirements": []}')
    assert status == "wrong_shape"
    _, status = parse_single_requirement('{"requirements": [{}, {}]}')
    assert status == "multi"
    _, status = parse_single_requirement("not json at all {{{")
    assert status == "malformed"
    _, status = parse_single_requirement("")
    assert status == "empty"
    print("PASS parse never coerces")


if __name__ == "__main__":
    test_fixture_consistency_across_abc()
    test_exactly_one_requirement_per_snippet()
    test_allowed_categories()
    test_snippets_verbatim_in_fixture()
    test_no_mutation_of_variant_b()
    test_no_production_behavior_changes()
    test_task_prompts_generic()
    test_parse_single_requirement_never_coerces()
    print("\nAll 8 Stage 3H tests passed")
