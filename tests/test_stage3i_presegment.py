"""
Stage 3I — Pre-segmentation + Variant B interface tests (no Ollama required,
except none — all offline using stored artifacts and pure functions).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.stage3i.presegment import (
    segment_parent_chunk, pattern_hits, split_sentences,
    MIN_CANDIDATE_CHARS, MAX_MIXED_CATEGORIES, MIN_PRINTABLE_RATIO,
)


def _art(name):
    import json
    return json.loads((Path(__file__).resolve().parents[1] / "evaluation" / "stage3i" / name).read_text(encoding="utf-8"))


def test_variant_b_unchanged():
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash, get_system_prompt
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
    assert get_system_prompt("B") == LLM_SYSTEM_PROMPT
    print("PASS Variant B unchanged")


def test_splitter_uses_existing_signals():
    src = Path(__file__).resolve().parents[1] / "evaluation" / "stage3i" / "presegment.py"
    text = src.read_text(encoding="utf-8")
    assert "GENERIC_PATTERNS" in text
    # No private regex inventory: the only pattern literals allowed are structural (sentence splitting)
    assert "financial capacity" not in text.lower()
    assert "project manager" not in text.lower()
    print("PASS splitter uses existing signals")


def test_source_text_verbatim():
    candidates = _art("generated_candidates.json")
    assert 12 <= len(candidates) <= 20
    parents = {p["chunk_id"]: p for p in _art("parent_chunks_3i.json")}
    for c in candidates:
        parent_text = parents[c["parent_chunk_id"]]["text"]
        assert c["source_text"] in parent_text, f"Not verbatim: {c['candidate_id']}"
    print("PASS source text remains verbatim")


def test_page_document_provenance_preserved():
    candidates = _art("generated_candidates.json")
    parents = {p["chunk_id"]: p for p in _art("parent_chunks_3i.json")}
    for c in candidates:
        p = parents[c["parent_chunk_id"]]
        assert c["source_document"] == p["source_document"], c["candidate_id"]
        assert c["page"] == p["page_number"], c["candidate_id"]
    print("PASS page/document provenance preserved")


def test_candidates_deterministic():
    parents = _art("parent_chunks_3i.json")[:3]
    first = [segment_parent_chunk(p) for p in parents]
    second = [segment_parent_chunk(p) for p in parents]
    assert first == second
    print("PASS candidates are deterministic")


def test_rejected_candidate_rules():
    parent = {"chunk_id": "chunk-9999", "source_document": "t.pdf", "page_number": 1,
              "text": "x\nShip the goods to the warehouse on time.\nDeadline: submission 15 of March, 2024 and schedule and technical GIS and commercial EGP terms."}
    acc, rej = segment_parent_chunk(parent)
    reasons = {r["rejection_reason"] for r in rej}
    assert "tiny" in reasons, reasons  # "x"
    assert "no_signal" in reasons, reasons  # "Ship the goods."
    assert "mixed_multi_category" in reasons, reasons  # 3+ hits sentence
    # Accepted ones are small and single/dual-purpose
    for a in acc:
        assert len(a["deterministic_signal_categories"]) <= MAX_MIXED_CATEGORIES
        assert len(a["source_text"]) >= MIN_CANDIDATE_CHARS
    print("PASS rejected candidate rules")


def test_no_production_behavior_mutation():
    import inspect
    from evaluation import llm_generic_extraction as m
    assert m.get_ollama_model() == "qwen2.5:3b"
    assert inspect.signature(m.call_ollama_for_chunk).parameters["system_prompt"].default is None
    assert m.TIMEOUT_SECONDS if hasattr(m, "TIMEOUT_SECONDS") else True
    print("PASS no production behavior mutation")


def test_exact_same_variant_b_interface():
    # Every C output requirement must carry its candidate's document/page (source-local interface)
    cands = {c["candidate_id"]: c for c in _art("generated_candidates.json")}
    outputs = _art("variant_b_outputs_3i.json")
    assert len(outputs) == len(cands)
    for o in outputs:
        c = cands[o["candidate_id"]]
        for r in o["requirements"]:
            assert r["source_document"] == c["source_document"], o["candidate_id"]
            assert r["page_number"] == c["page"], o["candidate_id"]
        assert len(o["requirements"]) >= 1, o["candidate_id"]
    print("PASS exact same Variant B interface")


if __name__ == "__main__":
    test_variant_b_unchanged()
    test_splitter_uses_existing_signals()
    test_source_text_verbatim()
    test_page_document_provenance_preserved()
    test_candidates_deterministic()
    test_rejected_candidate_rules()
    test_no_production_behavior_mutation()
    test_exact_same_variant_b_interface()
    print("\nAll 8 Stage 3I tests passed")
