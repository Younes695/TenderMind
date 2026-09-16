"""
Regression: deterministic hard-rule cases make ZERO Ollama HTTP calls.
Offline, no network, $0. Mocks requests.post and fails if called.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
from app.matchers.ollama_matcher import OllamaMatcher
from app.matchers.base import MatcherInput

def _inp(req_id, req_text, ev_id, ev_fact, req_ent="CONSORTIUM", ev_ent="CONSORTIUM"):
    return MatcherInput(
        requirement_id=req_id, requirement_text=req_text,
        requirement_category="TEST", requirement_type="TEST", mandatory=True,
        applicable_entity=req_ent,
        evidence_id=ev_id, evidence_fact=ev_fact,
        evidence_type="TEST", evidence_applicable_entity=ev_ent,
        source_document="Doc.pdf", page_or_section="Page 1",
        current_tender_id="SA-2018-HV2",
    )

def test_req_a_contradiction_zero_http():
    m = OllamaMatcher(model="qwen3:4b", timeout=90)
    inp = _inp("REQ-A", "First-category membership required", "E-FAIL-001",
               "Second Category membership certificate — Grade 2", "GIZA", "GIZA")
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        out = m.safe_match(inp)
        assert mock_post.call_count == 0, f"Case 2 must make ZERO Ollama POST calls, got {mock_post.call_count}"
        assert mock_get.call_count == 0, f"Case 2 must make ZERO Ollama GET calls (no availability check), got {mock_get.call_count}"
    assert out.applicability == "FAIL", f"expected FAIL got {out.applicability}"
    assert out.contradiction is True

def test_missing_no_evidence_zero_http():
    m = OllamaMatcher(model="qwen3:4b", timeout=90)
    inp = _inp("REQ-K", "Type-test certificates for major equipment", "E-NO-EV",
               "No evidence provided — empty fact")
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        out = m.safe_match(inp)
        assert mock_post.call_count == 0, f"Case 3 must make ZERO Ollama POST calls, got {mock_post.call_count}"
        assert mock_get.call_count == 0, f"Case 3 must make ZERO Ollama GET calls, got {mock_get.call_count}"
    assert out.applicability == "MISSING", f"expected MISSING got {out.applicability}"

def test_wrong_tender_zero_http():
    m = OllamaMatcher(model="qwen3:4b", timeout=90)
    from app.matchers.base import MatcherInput
    inp = MatcherInput(
        requirement_id="REQ-C", requirement_text="Tender security EGP 5,700,000",
        evidence_id="E-WRONG", evidence_fact="Tender security for OTHER/2020/XYZ",
        evidence_applicable_entity="CONSORTIUM",
        evidence_tender_source="OTHER-2020-XYZ", evidence_reusable=False,
        current_tender_id="SA-2018-HV2",
        source_document="Other.pdf", page_or_section="Page 1",
    )
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        out = m.safe_match(inp)
        assert mock_post.call_count == 0
        assert mock_get.call_count == 0
    assert out.applicability == "MISSING"

def test_ambiguous_zero_http():
    m = OllamaMatcher(model="qwen3:4b", timeout=90)
    inp = _inp("REQ-AMB", "Ambiguous applies to Consortium vs Lead vs OEM unclear", "E-001", "Some evidence")
    # set AMBIGUOUS entity
    inp.applicable_entity = "AMBIGUOUS"
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        out = m.safe_match(inp)
        assert mock_post.call_count == 0
        assert mock_get.call_count == 0
    assert out.applicability == "REVIEW"

if __name__ == "__main__":
    test_req_a_contradiction_zero_http()
    print("PASS test_req_a_contradiction_zero_http")
    test_missing_no_evidence_zero_http()
    print("PASS test_missing_no_evidence_zero_http")
    test_wrong_tender_zero_http()
    print("PASS test_wrong_tender_zero_http")
    test_ambiguous_zero_http()
    print("PASS test_ambiguous_zero_http")
    print("All hard-rule zero-HTTP tests passed")
