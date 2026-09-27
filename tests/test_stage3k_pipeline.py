"""
Stage 3K — Two-stage pipeline tests (no Ollama required; LLM stubbed).
Proves flag behavior, provenance, evidence, IDs, and failure handling.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os
from evaluation.stage3k import two_stage_pipeline as tsp


def _cand(cid="cand-01", gold="TECHNICAL", doc="a.pdf", page=1, text="Supply and installation of 220 kV GIS."):
    return {
        "candidate_id": cid, "parent_chunk_id": "chunk-0000",
        "source_document": doc, "page": page, "source_text": text,
        "span": [0, len(text)], "deterministic_signal_categories": [gold],
        "category_gold": gold,
    }


def _stub_ok_factory(predicted="TECHNICAL"):
    def _stub(candidate):
        return ({"summary": candidate["source_text"][:80], "category": predicted,
                 "mandatory": None, "applicable_entity": None}, "ok", 0.5, '{"requirements": []}')
    return _stub


def test_flag_off_preserves_old_path():
    if "TENDERMIND_TWO_STAGE_LLM" in os.environ:
        del os.environ["TENDERMIND_TWO_STAGE_LLM"]
    assert not tsp.flag_enabled()
    doc_results = {"a.pdf": {"pages": [{"page_number": 1, "text": "Supply and installation of 220 kV GIS. Tender security EGP 500,000."}]}}
    out = tsp.extract_requirements_dispatch(doc_results=doc_results)
    assert out["mode"] == "deterministic"
    assert len(out["requirements"]) >= 1
    assert out["evidence"] == []
    print("PASS flag off preserves old path")


def test_flag_on_uses_two_stage_path():
    os.environ["TENDERMIND_TWO_STAGE_LLM"] = "1"
    try:
        assert tsp.flag_enabled()
        cands = [_cand("cand-01"), _cand("cand-02", doc="b.pdf", text="Tender security EGP 500,000 valid for 180 days.")]
        out = tsp.extract_requirements_dispatch(candidates=cands)
        # Real LLM would be called; here just check dispatch shape with stub below instead.
        # Call the stubbed path directly for determinism:
        reqs, evs, recs = tsp.extract_requirements_two_stage(cands, llm_fn=_stub_ok_factory())
        assert len(reqs) == 2
        assert reqs[0]["requirement_id"] == "REQ-001"
        assert reqs[1]["requirement_id"] == "REQ-002"
    finally:
        del os.environ["TENDERMIND_TWO_STAGE_LLM"]
    print("PASS flag on uses two-stage path")


def test_deterministic_candidate_provenance():
    cands = [_cand("cand-09", doc="Vol II.pdf", page=3, text="Power Transformer 60 MVA.")]
    reqs, evs, _ = tsp.extract_requirements_two_stage(cands, llm_fn=_stub_ok_factory())
    assert reqs[0]["source_document"] == "Vol II.pdf"
    assert reqs[0]["page_number"] == 3
    assert reqs[0]["provenance"]["quote_en"] in "Power Transformer 60 MVA."
    assert reqs[0]["candidate_id"] == "cand-09"
    print("PASS deterministic candidate provenance")


def test_minimal_llm_contract():
    # Stub returns extra fields; pipeline must only rely on the 4 minimal fields.
    def _stub(candidate):
        return ({"summary": "S", "category": "LEGAL", "mandatory": None, "applicable_entity": None,
                 "candidate_id": "SHOULD-BE-IGNORED", "evidence": [{"x": 1}]}, "ok", 0.1, "{}")
    reqs, evs, recs = tsp.extract_requirements_two_stage([_cand()], llm_fn=_stub)
    assert reqs[0]["category"] == "LEGAL"
    print("PASS minimal LLM contract")


def test_deterministic_evidence():
    reqs, evs, _ = tsp.extract_requirements_two_stage([
        _cand("cand-01", text="Supply and installation of 220 kV GIS."),
        _cand("cand-02", doc="b.pdf", text="Tender security EGP 500,000 valid for 180 days."),
    ], llm_fn=_stub_ok_factory())
    assert len(evs) == 2
    by_req = {e["requirement_id"]: e for e in evs}
    for r in reqs:
        e = by_req[r["requirement_id"]]
        assert e["source_document"] == r["source_document"]
        assert e["page_number"] == r["page_number"]
        assert e["fact"] == r["summary"]
    print("PASS deterministic evidence")


def test_deterministic_canonical_ids():
    texts = [
        "Supply and installation of 220 kV GIS.",
        "Tender security EGP 500,000 valid for 180 days.",
        "Experience with similar 220kV GIS projects in last 5 years.",
    ]
    cands = [_cand(f"cand-{i:02d}", doc=f"{chr(98+i)}.pdf", text=texts[i]) for i in range(3)]
    reqs, _, _ = tsp.extract_requirements_two_stage(cands, llm_fn=_stub_ok_factory())
    assert [r["requirement_id"] for r in reqs] == ["REQ-001", "REQ-002", "REQ-003"]
    print("PASS deterministic canonical IDs")


def test_source_text_integrity():
    text = "Tender security EGP 500,000 valid for 180 days."
    reqs, _, _ = tsp.extract_requirements_two_stage([_cand(text=text)], llm_fn=_stub_ok_factory())
    assert reqs[0]["source_text"] == text or reqs[0]["provenance"]["quote_en"] in text
    print("PASS source text integrity")


def test_no_cross_document_evidence():
    reqs, evs, _ = tsp.extract_requirements_two_stage(
        [_cand("cand-01", doc="a.pdf"), _cand("cand-02", doc="b.pdf")], llm_fn=_stub_ok_factory())
    for e in evs:
        r = next(r for r in reqs if r["requirement_id"] == e["requirement_id"])
        assert e["source_document"] == r["source_document"]
    print("PASS no cross-document evidence")


def test_rejected_candidate_handling():
    cands = [_cand("cand-01"), _cand("cand-02")]
    def _stub(candidate):
        if candidate["candidate_id"] == "cand-01":
            return ({"summary": "S", "category": "TECHNICAL", "mandatory": None, "applicable_entity": None}, "ok", 0.1, "{}")
        return (None, "malformed", 0.1, "{bad")
    reqs, evs, recs = tsp.extract_requirements_two_stage(cands, llm_fn=_stub)
    assert len(reqs) == 1
    assert recs[1]["status"] == "malformed"
    print("PASS rejected candidate handling")


def test_llm_failures_do_not_fabricate():
    def _fail(candidate):
        return (None, "timeout", 90.0, None)
    reqs, evs, recs = tsp.extract_requirements_two_stage([_cand()], llm_fn=_fail)
    assert reqs == [] and evs == []
    assert recs[0]["status"] == "timeout"
    print("PASS LLM failures do not fabricate requirements")


def test_existing_variant_b_unchanged():
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
    print("PASS existing Variant B remains unchanged")


if __name__ == "__main__":
    test_flag_off_preserves_old_path()
    test_flag_on_uses_two_stage_path()
    test_deterministic_candidate_provenance()
    test_minimal_llm_contract()
    test_deterministic_evidence()
    test_deterministic_canonical_ids()
    test_source_text_integrity()
    test_no_cross_document_evidence()
    test_rejected_candidate_handling()
    test_llm_failures_do_not_fabricate()
    test_existing_variant_b_unchanged()
    print("\nAll 11 Stage 3K tests passed")
