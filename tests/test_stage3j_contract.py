"""
Stage 3J — Minimal output-contract harness tests (no Ollama required).
Proves the 16-candidate fixture is reused exactly, the contract requests only
the minimal schema, provenance is deterministic, and production is untouched.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.stage3j.minimal_contract_prompt import (
    MINIMAL_CONTRACT_SYSTEM, PROMPT_VERSION_3J, prompt_hash_3j,
    attach_provenance, derive_evidence,
)


def _candidates_3i():
    import json
    return json.loads((Path(__file__).resolve().parents[1] / "evaluation" / "stage3i" / "generated_candidates.json").read_text(encoding="utf-8"))


def test_stage_3i_variant_b_unchanged():
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash, get_system_prompt
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
    assert get_system_prompt("B") == LLM_SYSTEM_PROMPT
    print("PASS Stage 3I Variant B unchanged")


def test_exact_16_candidate_fixture_reuse():
    cands = _candidates_3i()
    assert len(cands) == 16
    assert [c["candidate_id"] for c in cands] == [f"3i-{i:02d}" for i in range(1, 17)]
    for c in cands:
        for field in ("candidate_id", "parent_chunk_id", "source_document", "page", "source_text", "span", "deterministic_signal_categories", "category_gold"):
            assert field in c, f"Missing {field} in {c.get('candidate_id')}"
    print("PASS exact 16-candidate fixture reuse")


def test_minimal_contract_output_schema():
    assert '"summary"' in MINIMAL_CONTRACT_SYSTEM
    assert '"category"' in MINIMAL_CONTRACT_SYSTEM
    assert '"mandatory"' in MINIMAL_CONTRACT_SYSTEM
    assert '"applicable_entity"' in MINIMAL_CONTRACT_SYSTEM
    assert '"candidate_id"' not in MINIMAL_CONTRACT_SYSTEM
    assert '"evidence"' not in MINIMAL_CONTRACT_SYSTEM
    assert '"provenance"' not in MINIMAL_CONTRACT_SYSTEM
    assert '"source_document"' not in MINIMAL_CONTRACT_SYSTEM
    print("PASS minimal-contract output schema")


def test_no_evidence_ids_provenance_requested():
    low = MINIMAL_CONTRACT_SYSTEM.lower()
    assert "do not generate ids, evidence, source_document, page, provenance, or candidate linkage." in low
    print("PASS no evidence/IDs/provenance requested from LLM")


def test_deterministic_provenance_attachment():
    cands = _candidates_3i()
    c = cands[0]
    req = {"summary": "Test", "category": "TECHNICAL", "mandatory": None, "applicable_entity": None}
    full = attach_provenance({**req, "requirement_id": c["candidate_id"]}, c)
    assert full["source_document"] == c["source_document"]
    assert full["page_number"] == c["page"]
    assert full["source_text"] == c["source_text"]
    assert full["candidate_id"] == c["candidate_id"]
    assert full["parent_chunk_id"] == c["parent_chunk_id"]
    ev = derive_evidence(full)
    assert ev["source_document"] == c["source_document"]
    assert ev["requirement_id"] == c["candidate_id"]
    print("PASS deterministic provenance attachment")


def test_no_production_code_mutation():
    import inspect
    from evaluation import llm_generic_extraction as m
    assert m.get_ollama_model() == "qwen2.5:3b"
    assert inspect.signature(m.call_ollama_for_chunk).parameters["system_prompt"].default is None
    from evaluation.generic_extraction import GENERIC_PATTERNS
    assert any("tender security" in pat for pat, _, _ in GENERIC_PATTERNS)
    assert PROMPT_VERSION_3J == "Variant B-minimal-contract"
    assert len(prompt_hash_3j(MINIMAL_CONTRACT_SYSTEM)) == 16
    print("PASS no production code mutation")


def test_allowed_categories():
    from evaluation.stage3h.single_req_tasks import ALLOWED_CATEGORIES
    cands = _candidates_3i()
    for c in cands:
        assert c["category_gold"] in ALLOWED_CATEGORIES, c["candidate_id"]
    print("PASS allowed categories")


def test_exactly_one_requirement_expected():
    from evaluation.stage3h.single_req_tasks import parse_single_requirement
    req, status = parse_single_requirement('{"requirements": [{"summary": "T", "category": "TECHNICAL", "mandatory": null, "applicable_entity": null}]}')
    assert status == "ok"
    _, status = parse_single_requirement('{"requirements": [{}, {}]}')
    assert status == "multi"
    _, status = parse_single_requirement('{"requirements": []}')
    assert status == "wrong_shape"
    print("PASS exactly one requirement expected")


if __name__ == "__main__":
    test_stage_3i_variant_b_unchanged()
    test_exact_16_candidate_fixture_reuse()
    test_minimal_contract_output_schema()
    test_no_evidence_ids_provenance_requested()
    test_deterministic_provenance_attachment()
    test_no_production_code_mutation()
    test_allowed_categories()
    test_exactly_one_requirement_expected()
    print("\nAll 8 Stage 3J tests passed")
