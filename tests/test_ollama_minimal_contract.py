"""
Focused tests for minimal Ollama inference contract (2 fields only).
Offline, mocked HTTP, $0. No real Ollama, no paid API.
- LLM returns ONLY {applicability, confidence}; all else derived deterministically in Python.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch, MagicMock
from app.matchers import MatcherInput
from app.matchers.ollama_matcher import OllamaMatcher


def _inp(req_id="REQ-A", req_text="First-category membership required", ev_id="E-GIZA-001",
         ev_fact="Giza Systems First Category certificate valid", req_ent="GIZA", ev_ent="GIZA"):
    return MatcherInput(
        requirement_id=req_id, requirement_text=req_text,
        requirement_category="LEGAL", requirement_type="HARD_GATE", mandatory=True,
        applicable_entity=req_ent,
        evidence_id=ev_id, evidence_fact=ev_fact,
        evidence_type="CERTIFICATE", evidence_applicable_entity=ev_ent,
        source_document="Cert.pdf", page_or_section="Page 1",
        current_tender_id="SA-2018-HV2",
    )


def _mock_chat(json_str):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"message": {"role": "assistant", "content": json_str}}
    return m


def test_minimal_json_parsing():
    m = OllamaMatcher(model="qwen3:4b")
    inp = _inp()
    with patch("requests.post", return_value=_mock_chat('{"applicability": "PASS", "confidence": 0.95}')):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = m.match(inp)
            assert out.applicability == "PASS", f"got {out.applicability}"
            assert out.confidence == 0.95
            assert out.contradiction is False
    print("PASS test_minimal_json_parsing")


def test_malformed_output_review():
    m = OllamaMatcher(model="qwen3:4b")
    inp = _inp()
    bad_cases = [
        "not a json { invalid",
        '{"applicability": "MAYBE", "confidence": 0.5}',
        '{"confidence": 0.9}',
        '{"applicability": null, "confidence": 0.5}',
        "",
        '{"applicability": "PASS", "confidence": 2.5}',
    ]
    for bad in bad_cases:
        with patch("requests.post", return_value=_mock_chat(bad)):
            with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
                out = m.match(inp)
                assert out.applicability == "REVIEW", f"malformed {bad!r} must be REVIEW, got {out.applicability}"
                assert out.confidence == 0.0
    print("PASS test_malformed_output_review")


def test_deterministic_evidence_id_derivation():
    m = OllamaMatcher(model="qwen3:4b")
    inp = _inp(req_id="REQ-A", ev_id="E-GIZA-001")
    # Even though minimal contract has no matched_evidence_ids, derived output must reference input ID
    with patch("requests.post", return_value=_mock_chat('{"applicability": "PASS", "confidence": 0.9}')):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = m.match(inp)
            assert out.applicability == "PASS"
            # Derived supporting facts must reference the input evidence ID (not invented)
            assert any("E-GIZA-001" in s for s in out.supporting_facts), f"derived facts must reference input ID, got {out.supporting_facts}"
            assert "E-GIZA-001" in out.reason, f"reason must reference provenance ID, got {out.reason}"
    print("PASS test_deterministic_evidence_id_derivation")


def test_hard_rules_zero_http():
    m = OllamaMatcher(model="qwen3:4b", timeout=90)
    # Contradiction case must not call HTTP
    inp_fail = MatcherInput(
        requirement_id="REQ-A", requirement_text="First-category membership required",
        applicable_entity="GIZA", evidence_id="E-FAIL-001",
        evidence_fact="Second Category membership — Grade 2", evidence_applicable_entity="GIZA",
        source_document="C.pdf", page_or_section="Page 1", current_tender_id="SA-2018-HV2")
    with patch("requests.post") as mp, patch("requests.get") as mg:
        out = m.safe_match(inp_fail)
        assert mp.call_count == 0 and mg.call_count == 0
    assert out.applicability == "FAIL" and out.contradiction is True
    # Missing case
    inp_miss = MatcherInput(
        requirement_id="REQ-K", requirement_text="Type-test certificates",
        evidence_id="E-NO-EV", evidence_fact="No evidence provided — empty fact",
        source_document="None", page_or_section="N/A", current_tender_id="SA-2018-HV2")
    with patch("requests.post") as mp, patch("requests.get") as mg:
        out2 = m.safe_match(inp_miss)
        assert mp.call_count == 0 and mg.call_count == 0
    assert out2.applicability == "MISSING"
    print("PASS test_hard_rules_zero_http")


def test_forbidden_bid_impossible():
    m = OllamaMatcher(model="qwen3:4b")
    inp = _inp()
    for bad_app in ["BID", "NO_BID"]:
        with patch("requests.post", return_value=_mock_chat(f'{{"applicability": "{bad_app}", "confidence": 0.9}}')):
            with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
                out = m.match(inp)
                assert out.applicability == "REVIEW", f"{bad_app} must become REVIEW, got {out.applicability}"
                assert out.applicability not in ("BID", "NO_BID")
    print("PASS test_forbidden_bid_impossible")


def test_provenance_preserved():
    m = OllamaMatcher(model="qwen3:4b")
    inp = _inp()
    with patch("requests.post", return_value=_mock_chat('{"applicability": "PASS", "confidence": 0.9}')):
        with patch("app.matchers.ollama_matcher.check_ollama_available", return_value=(True, "OK")):
            out = m.match(inp)
            assert "E-GIZA-001" in out.reason
            assert "Cert.pdf" in out.reason
            assert "Page 1" in out.reason
    print("PASS test_provenance_preserved")


if __name__ == "__main__":
    test_minimal_json_parsing()
    test_malformed_output_review()
    test_deterministic_evidence_id_derivation()
    test_hard_rules_zero_http()
    test_forbidden_bid_impossible()
    test_provenance_preserved()
    print("All 6 minimal-contract tests passed — offline, mocked, $0")
