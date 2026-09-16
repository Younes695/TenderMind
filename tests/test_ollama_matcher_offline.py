"""
Offline tests for OllamaMatcher — TenderMind
- No network, no Ollama required (mocked HTTP)
- Tests all 10 required cases per task
- If Ollama/model unavailable, tests still pass via mocks
- Never calls real Ollama, never uses paid API
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unittest.mock import patch, MagicMock
import os

from app.matchers import MatcherInput
from app.matchers.ollama_matcher import OllamaMatcher, get_ollama_model, check_ollama_available

# Helper to create mock Ollama response
def mock_ollama_response(json_str):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": json_str}
    return mock_resp

def test_normal_pass():
    # Normal PASS: First Category with correct evidence
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="First-category membership required for GIZA",
        requirement_category="LEGAL", requirement_type="HARD_GATE", mandatory=True,
        applicable_entity="GIZA",
        evidence_id="E-GIZA-001",
        evidence_fact="Giza Systems First Category certificate valid 2024-2025 — Grade 1",
        evidence_type="CERTIFICATE", evidence_applicable_entity="GIZA",
        source_document="Cert.pdf", page_or_section="Page 1"
    )
    # Mock successful Ollama JSON
    mock_json = '{"applicability": "PASS", "confidence": 0.95, "reason": "Strong support: First Category matches", "matched_evidence_ids": ["E-GIZA-001"], "contradiction": false}'
    with patch("app.matchers.ollama_matcher.requests.post", return_value=mock_ollama_response(mock_json)):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = matcher.match(inp)
            assert out.applicability == "PASS", f"Expected PASS, got {out.applicability}"
            assert out.confidence == 0.95
            assert out.contradiction is False
            print("PASS test_normal_pass")

def test_explicit_contradiction_fail():
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="First-category membership required",
        applicable_entity="GIZA",
        evidence_id="E-FAIL-001",
        evidence_fact="Second Category membership — Grade 2",
        evidence_applicable_entity="GIZA",
        source_document="Cert Grade 2.pdf", page_or_section="Page 1"
    )
    # Even if Ollama says PASS, hard rule should override to FAIL
    # Mock Ollama to incorrectly say PASS (to test hard rule override)
    mock_json = '{"applicability": "PASS", "confidence": 0.9, "reason": "wrong", "matched_evidence_ids": ["E-FAIL-001"], "contradiction": false}'
    with patch("app.matchers.ollama_matcher.requests.post", return_value=mock_ollama_response(mock_json)):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = matcher.match(inp)
            # Hard rule: Second Category vs First Category => FAIL, even if LLM says PASS
            assert out.applicability == "FAIL", f"Explicit contradiction should be FAIL, got {out.applicability}"
            assert out.contradiction is True
            print("PASS test_explicit_contradiction_fail")

def test_no_evidence_missing():
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-K",
        requirement_text="Type-test certificates for major equipment",
        evidence_id="E-NO-EV",
        evidence_fact="No evidence provided — empty fact",
        evidence_applicable_entity="CONSORTIUM",
        source_document="None", page_or_section="N/A"
    )
    mock_json = '{"applicability": "MISSING", "confidence": 0.0, "reason": "No supporting facts", "matched_evidence_ids": [], "contradiction": false}'
    with patch("app.matchers.ollama_matcher.requests.post", return_value=mock_ollama_response(mock_json)):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = matcher.match(inp)
            assert out.applicability == "MISSING"
            print("PASS test_no_evidence_missing")

def test_ambiguous_review():
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-AMB",
        requirement_text="Ambiguous: qualification applies to Consortium vs Lead partner vs OEM unclear",
        applicable_entity="AMBIGUOUS",
        evidence_id="E-001",
        evidence_fact="Some evidence",
        evidence_applicable_entity="CONSORTIUM",
        source_document="Doc.pdf", page_or_section="Page 1"
    )
    # Even if Ollama says PASS, hard rule for AMBIGUOUS should be REVIEW (handled before LLM)
    # So we don't even need to mock LLM — the matcher returns REVIEW before calling LLM
    out = matcher.match(inp)
    assert out.applicability == "REVIEW", f"Expected REVIEW for ambiguous, got {out.applicability}"
    assert out.support is None
    print("PASS test_ambiguous_review")

def test_wrong_tender_missing():
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-C",
        requirement_text="Tender security EGP 5,700,000",
        evidence_id="E-WRONG",
        evidence_fact="Tender security for OTHER/2020/XYZ — 3M",
        evidence_applicable_entity="CONSORTIUM",
        evidence_tender_source="OTHER-2020-XYZ",
        evidence_reusable=False,
        current_tender_id="SA-2018-HV2",
        source_document="Other.pdf", page_or_section="Page 1"
    )
    out = matcher.match(inp)
    assert out.applicability == "MISSING", f"Expected MISSING for wrong tender, got {out.applicability}"
    print("PASS test_wrong_tender_missing")

def test_expired_review():
    import datetime
    past = (datetime.datetime.utcnow() - datetime.timedelta(days=365*2)).isoformat()
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="First-category membership required",
        applicable_entity="GIZA",
        evidence_id="E-EXPIRED",
        evidence_fact="First Category certificate valid 2019-2020",
        evidence_applicable_entity="GIZA",
        evidence_valid_until=past,
        source_document="Expired.pdf", page_or_section="Page 1"
    )
    out = matcher.match(inp)
    assert out.applicability == "REVIEW", f"Expected REVIEW for expired, got {out.applicability}"
    print("PASS test_expired_review")

def test_oem_only_non_applicability():
    matcher = OllamaMatcher(model="qwen3:4b")
    # REQ-K type-test with OEM evidence should be MISSING (OEM alone not enough)
    inp = MatcherInput(
        requirement_id="REQ-K",
        requirement_text="Type-test certificates for major equipment",
        evidence_id="E-003",
        evidence_fact="Hyosung as consortium member IS the OEM/manufacturer for core GIS equipment",
        evidence_applicable_entity="HYOSUNG",
        applicable_entity="CONSORTIUM",
        source_document="Agreement rev1.doc", page_or_section="Page 1"
    )
    # Mock LLM to incorrectly say PASS — hard rule should override to MISSING
    mock_json = '{"applicability": "PASS", "confidence": 0.9, "reason": "OEM supports", "matched_evidence_ids": ["E-003"], "contradiction": false}'
    with patch("app.matchers.ollama_matcher.requests.post", return_value=mock_ollama_response(mock_json)):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = matcher.match(inp)
            assert out.applicability == "MISSING", f"OEM for REQ-K should be MISSING, got {out.applicability}"
            print("PASS test_oem_only_non_applicability")

def test_malformed_json_review():
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="test",
        evidence_id="E-001",
        evidence_fact="test fact",
        source_document="Doc.pdf", page_or_section="Page 1"
    )
    # Mock malformed JSON
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "not a json { invalid"}
    with patch("app.matchers.ollama_matcher.requests.post", return_value=mock_resp):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = matcher.match(inp)
            assert out.applicability == "REVIEW", f"Malformed JSON should be REVIEW, got {out.applicability}"
            assert out.confidence == 0.0
            print("PASS test_malformed_json_review")

def test_invented_evidence_id_reject():
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="First-category membership required",
        applicable_entity="GIZA",
        evidence_id="E-001",
        evidence_fact="First Category cert valid",
        evidence_applicable_entity="GIZA",
        source_document="Cert.pdf", page_or_section="Page 1"
    )
    # Mock invented ID
    mock_json = '{"applicability": "PASS", "confidence": 0.9, "reason": "test", "matched_evidence_ids": ["INVENTED-E-999"], "contradiction": false}'
    with patch("app.matchers.ollama_matcher.requests.post", return_value=mock_ollama_response(mock_json)):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = matcher.match(inp)
            # Should be REVIEW because invented ID is rejected
            assert out.applicability == "REVIEW", f"Invented ID should be REVIEW, got {out.applicability}"
            assert "Invented evidence ID" in out.reason or "Invented" in out.reason
            print("PASS test_invented_evidence_id_reject")

def test_bid_no_bid_reject():
    matcher = OllamaMatcher(model="qwen3:4b")
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="test",
        evidence_id="E-001",
        evidence_fact="test fact",
        source_document="Doc.pdf", page_or_section="Page 1"
    )
    # Mock BID
    mock_json = '{"applicability": "BID", "confidence": 0.9, "reason": "should be BID", "matched_evidence_ids": ["E-001"], "contradiction": false}'
    with patch("app.matchers.ollama_matcher.requests.post", return_value=mock_ollama_response(mock_json)):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = matcher.match(inp)
            assert out.applicability == "REVIEW", f"BID/NO_BID must be rejected to REVIEW, got {out.applicability}"
            assert "BID" in out.reason or "forbidden" in out.reason.lower()
            print("PASS test_bid_no_bid_reject")

def test_ollama_availability_detection():
    # Test availability detection without needing real Ollama
    # If Ollama not running, check_ollama_available should return False with install command
    # We mock requests.get to simulate not running
    with patch("app.matchers.ollama_matcher.requests.get", side_effect=Exception("Connection refused")):
        from app.matchers.ollama_matcher import check_ollama_available
        ok, msg = check_ollama_available("qwen3:4b")
        assert not ok, "Should be not ok when connection refused"
        assert "ollama serve" in msg or "Connection refused" in msg
        print("PASS test_ollama_availability_detection")

if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass
    test_normal_pass()
    test_explicit_contradiction_fail()
    test_no_evidence_missing()
    test_ambiguous_review()
    test_wrong_tender_missing()
    test_expired_review()
    test_oem_only_non_applicability()
    test_malformed_json_review()
    test_invented_evidence_id_reject()
    test_bid_no_bid_reject()
    test_ollama_availability_detection()
    print("\nAll 10 Ollama offline tests passed — no network to paid API, mocked localhost only")
