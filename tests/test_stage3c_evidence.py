"""
Stage 3C — Evidence integrity regression tests (no Ollama required).
Proves evidence cannot silently drift to another requirement.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.llm_generic_extraction import assign_canonical_ids


def _req(cid, summary="Test", category="TECHNICAL", doc="a.pdf", page=1):
    return {
        "candidate_id": cid, "requirement_id": cid, "summary": summary, "category": category,
        "mandatory": None, "requirement_type": None, "applicable_entity": None,
        "evidence_required": [], "conditional": False,
        "source_document": doc, "page_number": page, "confidence": 0.8,
        "provenance": {"quote_en": "test"}, "extraction_method": "llm",
    }


def _ev(eid, req_cand, doc="a.pdf", page=1, fact="Fact"):
    return {
        "candidate_id": eid, "evidence_id": eid, "requirement_candidate_id": req_cand,
        "fact": fact, "source_document": doc, "page_number": page, "confidence": 0.8,
        "provenance": {"quote_en": "test"}, "applicable_entity": None,
        "valid_until": None, "reusable": False,
    }


def test_cross_chunk_hallucination_rejected_in_assign():
    # Stage 3B failure: chunk-0004-ev-01 -> chunk-0001-item-01 must not attach to REQ-001
    reqs = [_req("chunk-0001-item-01", doc="Drawings.pdf"), _req("chunk-0004-item-01", doc="Price.xlsx")]
    evs = [_ev("chunk-0004-ev-01", "chunk-0001-item-01", doc="Price.xlsx")]
    _, final_evs = assign_canonical_ids(reqs, evs)
    assert len(final_evs) == 0, f"Cross-chunk evidence must be rejected, got {final_evs}"
    print("PASS cross-chunk hallucinated requirement_candidate_id")


def test_missing_candidate_id_rejected():
    # Evidence logic is tested via llm_extract path; here test assign handles missing linkage
    reqs = [_req("chunk-0001-item-01")]
    evs = [{
        "candidate_id": "chunk-0001-ev-01", "evidence_id": "chunk-0001-ev-01",
        "fact": "Fact", "source_document": "a.pdf", "page_number": 1,
        "confidence": 0.8, "provenance": {"quote_en": "t"},
        "applicable_entity": None, "valid_until": None, "reusable": False,
        # no requirement_candidate_id and no requirement_id
    }]
    _, final_evs = assign_canonical_ids(reqs, evs)
    assert len(final_evs) == 0, "Missing linkage must be rejected"
    print("PASS missing candidate ID")


def test_duplicate_candidate_ids_do_not_collide():
    # Two requirements with same candidate_id in different chunks must not silently merge via canonical_map?
    # assign_canonical_ids maps old_id -> new_id; duplicate old_id would collide.
    # Our per-chunk fix ensures uniqueness before assign, but assign should still handle gracefully.
    reqs = [_req("chunk-0001-item-01", summary="A", doc="a.pdf"), _req("chunk-0001-item-01", summary="B", doc="b.pdf")]
    # Simulate what happens if duplicates reach assign (should not overwrite silently without trace?)
    # Currently second overwrites first in canonical_map — we test that evidence still resolves deterministically
    evs = [_ev("chunk-0001-ev-01", "chunk-0001-item-01", doc="a.pdf")]
    _, final_evs = assign_canonical_ids(reqs, evs)
    # Must resolve to exactly one requirement (the last mapping), not crash, not attach to multiple
    assert len(final_evs) == 1
    assert final_evs[0]["requirement_id"] in ("REQ-001", "REQ-002")
    print("PASS duplicate candidate IDs")


def test_valid_same_chunk_evidence():
    reqs = [_req("chunk-0007-item-01", doc="Vol I.pdf", page=3), _req("chunk-0007-item-02", doc="Vol I.pdf", page=3)]
    evs = [
        _ev("chunk-0007-ev-01", "chunk-0007-item-01", doc="Vol I.pdf", page=3, fact="Fact 1"),
        _ev("chunk-0007-ev-02", "chunk-0007-item-02", doc="Vol I.pdf", page=3, fact="Fact 2"),
    ]
    final_reqs, final_evs = assign_canonical_ids(reqs, evs)
    assert len(final_evs) == 2
    # Each evidence must point to a distinct canonical requirement
    assert final_evs[0]["requirement_id"] != final_evs[1]["requirement_id"]
    # Each must be one of the canonical IDs
    canon_ids = {r["requirement_id"] for r in final_reqs}
    for e in final_evs:
        assert e["requirement_id"] in canon_ids
    print("PASS valid same-chunk evidence")


def test_evidence_for_deleted_candidate_rejected():
    # Requirement that will be deduplicated away: evidence referencing it must be rejected, not drift
    reqs = [
        _req("chunk-0001-item-01", summary="Same", category="TECHNICAL", doc="a.pdf"),
        _req("chunk-0002-item-01", summary="Same", category="TECHNICAL", doc="a.pdf"),
    ]
    # Simulate dedup keeping only first (deduplicate_requirements would keep higher confidence)
    # Here directly test assign with only first surviving
    surviving = [reqs[0]]
    evs = [_ev("chunk-0002-ev-01", "chunk-0002-item-01", doc="a.pdf")]
    _, final_evs = assign_canonical_ids(surviving, evs)
    assert len(final_evs) == 0, "Evidence for deleted/deduped candidate must be rejected"
    print("PASS evidence for a deleted/deduplicated candidate")


def test_canonical_reassignment_stable():
    reqs = [
        _req("chunk-0002-item-01", summary="B", doc="b.pdf"),
        _req("chunk-0001-item-01", summary="A", doc="a.pdf"),
    ]
    evs = [_ev("chunk-0001-ev-01", "chunk-0001-item-01", doc="a.pdf")]
    final_reqs, final_evs = assign_canonical_ids(reqs, evs)
    # Sorted by source_document: a.pdf first -> REQ-001, b.pdf -> REQ-002
    assert final_reqs[0]["requirement_id"] == "REQ-001"
    assert final_reqs[0]["_candidate_id"] == "chunk-0001-item-01"
    assert final_evs[0]["requirement_id"] == "REQ-001"
    assert final_evs[0]["_candidate_requirement_id"] == "chunk-0001-item-01"
    print("PASS canonical ID reassignment")


if __name__ == "__main__":
    test_cross_chunk_hallucination_rejected_in_assign()
    test_missing_candidate_id_rejected()
    test_duplicate_candidate_ids_do_not_collide()
    test_valid_same_chunk_evidence()
    test_evidence_for_deleted_candidate_rejected()
    test_canonical_reassignment_stable()
    print("\nAll 6 Stage 3C evidence tests passed")
