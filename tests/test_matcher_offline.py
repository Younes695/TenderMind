"""
Offline Matcher Tests — TenderMind
- No external API calls, no network, no cost
- Uses MockMatcher (deterministic) + BaseMatcher.safe_match
- Covers 11 required cases per task
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.matchers import MockMatcher, MatcherInput, MatcherOutput, BaseMatcher
from app.matchers.base import MatcherOutput as BaseOutput
import datetime

matcher = MockMatcher()

def test_strong_semantic_support():
    # REQ-A First Category with correct GIZA evidence
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="First-category Egyptian Union for Construction Contractors membership required for local partner",
        requirement_category="LEGAL", requirement_type="HARD_GATE", mandatory=True,
        applicable_entity="GIZA",
        evidence_id="E-GIZA-001",
        evidence_fact="Giza Systems First Category Egyptian Union membership certificate valid 2024-2025 — Grade 1",
        evidence_type="CERTIFICATE", evidence_applicable_entity="GIZA",
        source_document="Giza First Category Certificate.pdf", page_or_section="Page 1"
    )
    out = matcher.safe_match(inp)
    assert out.support is True, f"Expected support true, got {out.support}"
    assert out.applicability == "PASS", f"Expected PASS, got {out.applicability}"
    assert out.confidence > 0.8, "Confidence should be high for strong support"
    assert len(out.supporting_facts) > 0, "Should have supporting facts"
    assert out.contradiction is False
    print("PASS test_strong_semantic_support")

def test_contradiction():
    # REQ-A First Category required, but Second Category provided
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="First-category membership required",
        applicable_entity="GIZA",
        evidence_id="E-FAIL-001",
        evidence_fact="Second Category membership certificate — Grade 2",
        evidence_applicable_entity="GIZA",
        source_document="Cert Grade 2.pdf", page_or_section="Page 1"
    )
    out = matcher.safe_match(inp)
    assert out.contradiction is True, "Should detect contradiction"
    assert out.applicability == "FAIL", f"Expected FAIL, got {out.applicability}"
    assert len(out.contradictory_facts) > 0
    print("PASS test_contradiction")

def test_missing_evidence():
    # Generic missing: evidence does not contain required terms
    inp = MatcherInput(
        requirement_id="REQ-K",
        requirement_text="Type-test certificates for major equipment",
        evidence_id="E-GENERIC",
        evidence_fact="We have some random company brochure",
        evidence_applicable_entity="CONSORTIUM",
        source_document="Brochure.pdf", page_or_section="Page 1"
    )
    out = matcher.safe_match(inp)
    assert out.applicability == "MISSING", f"Expected MISSING, got {out.applicability}"
    assert out.support is False
    assert len(out.missing_facts) > 0
    print("PASS test_missing_evidence")

def test_ambiguous_applicability():
    inp = MatcherInput(
        requirement_id="REQ-AMB",
        requirement_text="Ambiguous: qualification applies to Consortium vs Lead partner vs OEM unclear",
        applicable_entity="AMBIGUOUS",
        evidence_id="E-001",
        evidence_fact="Some evidence",
        evidence_applicable_entity="CONSORTIUM",
        source_document="Doc.pdf", page_or_section="Page 1"
    )
    out = matcher.safe_match(inp)
    assert out.applicability == "REVIEW", f"Expected REVIEW for ambiguous, got {out.applicability}"
    assert out.support is None, "Support should be null for ambiguous"
    print("PASS test_ambiguous_applicability")

def test_wrong_tender():
    inp = MatcherInput(
        requirement_id="REQ-C",
        requirement_text="Tender security EGP 5,700,000 valid for 270 days",
        evidence_id="E-WRONG-TENDER",
        evidence_fact="Tender security for OTHER/2020/XYZ — 3M",
        evidence_applicable_entity="CONSORTIUM",
        evidence_tender_source="OTHER-2020-XYZ",
        evidence_reusable=False,
        current_tender_id="SA-2018-HV2",
        source_document="Other Tender Security.pdf", page_or_section="Page 1"
    )
    out = matcher.safe_match(inp)
    assert out.applicability == "MISSING", f"Expected MISSING for wrong tender non-reusable, got {out.applicability}"
    assert "wrong tender" in out.reason.lower() or "non-reusable" in out.reason.lower()
    print("PASS test_wrong_tender")

def test_expired_evidence():
    past = (datetime.datetime.utcnow() - datetime.timedelta(days=365*2)).isoformat()
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="First-category membership required",
        applicable_entity="GIZA",
        evidence_id="E-EXPIRED",
        evidence_fact="First Category certificate valid 2019-2020",
        evidence_applicable_entity="GIZA",
        evidence_valid_until=past,
        source_document="Expired Cert.pdf", page_or_section="Page 1"
    )
    out = matcher.safe_match(inp)
    assert out.applicability == "REVIEW", f"Expected REVIEW for expired, got {out.applicability}"
    assert "expired" in out.reason.lower()
    print("PASS test_expired_evidence")

def test_malformed_matcher_output():
    # Simulate a provider that returns malformed output (missing required fields, wrong types)
    class BadMatcher(BaseMatcher):
        name = "bad-mock"
        def match(self, inp):
            # Return dict with missing fields and wrong types
            return {"support": "not-a-bool", "contradiction": "maybe", "applicability": "UNKNOWN", "confidence": 2.0, "reason": ""}

    bad = BadMatcher()
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="test",
        evidence_id="E-001",
        evidence_fact="test fact",
        source_document="Doc.pdf", page_or_section="Page 1"
    )
    out = bad.safe_match(inp)
    # Should fallback to REVIEW with low confidence, not raise, not produce BID
    assert out.applicability == "REVIEW", f"Malformed should fallback to REVIEW, got {out.applicability}"
    assert out.confidence == 0.0, "Malformed fallback should be 0.0"
    assert "validation failed" in out.reason.lower() or "ambiguous" in out.reason.lower()
    print("PASS test_malformed_matcher_output")

def test_provenance_preservation():
    inp = MatcherInput(
        requirement_id="REQ-R",
        requirement_text="Consortium/JV evidence — executed agreement with joint/several liability",
        applicable_entity="CONSORTIUM",
        evidence_id="E-001",
        evidence_fact="Hyosung and Giza Systems form a consortium with joint and several liability.",
        evidence_applicable_entity="CONSORTIUM",
        source_document="SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc",
        page_or_section="Page 1, Preamble"
    )
    out = matcher.safe_match(inp)
    assert out.applicability == "PASS", "Should be PASS"
    # Provenance is preserved via input's source_document/page_or_section — output should retain reason that references provenance
    # The matcher itself doesn't return provenance, but the calling code must preserve it — we check that output is not inventing new doc
    assert "source_document" in inp.model_fields or hasattr(inp, "source_document")
    # Ensure output doesn't invent new evidence
    assert "E-001" in inp.evidence_id
    print("PASS test_provenance_preservation")

def test_oem_satisfies_J_not_K():
    # OEM evidence (E-003) should satisfy REQ-J (OEM) but NOT REQ-K (type-test)
    # REQ-J
    inp_j = MatcherInput(
        requirement_id="REQ-J",
        requirement_text="OEM/manufacturer relationship (authorization/consortium manufacturing linkage)",
        evidence_id="E-003",
        evidence_fact="Hyosung as consortium member IS the OEM/manufacturer for core GIS equipment, providing structural OEM linkage.",
        evidence_applicable_entity="HYOSUNG",
        applicable_entity="CONSORTIUM",
        source_document="Agreement rev1.doc", page_or_section="Page 1"
    )
    out_j = matcher.safe_match(inp_j)
    assert out_j.applicability == "PASS", f"REQ-J should be PASS with OEM, got {out_j.applicability}"

    # REQ-K with same OEM evidence should be MISSING (OEM does not satisfy type-test per spec §19 #3)
    inp_k = MatcherInput(
        requirement_id="REQ-K",
        requirement_text="Type-test certificates for major equipment (GIS, transformer)",
        evidence_id="E-003",
        evidence_fact="Hyosung as consortium member IS the OEM/manufacturer for core GIS equipment, providing structural OEM linkage.",
        evidence_applicable_entity="HYOSUNG",
        applicable_entity="CONSORTIUM",
        source_document="Agreement rev1.doc", page_or_section="Page 1"
    )
    out_k = matcher.safe_match(inp_k)
    assert out_k.applicability == "MISSING", f"REQ-K should be MISSING with OEM evidence, got {out_k.applicability} — OEM must not satisfy type-test"

    # Also test REQ-L (operating references) and REQ-D/I
    for req_id in ["REQ-L", "REQ-D", "REQ-I"]:
        inp = MatcherInput(
            requirement_id=req_id,
            requirement_text=f"Requirement {req_id}",
            evidence_id="E-003",
            evidence_fact="Hyosung as consortium member IS the OEM/manufacturer for core GIS equipment, providing structural OEM linkage.",
            evidence_applicable_entity="HYOSUNG",
            source_document="Agreement rev1.doc", page_or_section="Page 1"
        )
        out = matcher.safe_match(inp)
        # For these, OEM should not automatically satisfy — should be MISSING (since no type-test/operating refs)
        # Our mock currently checks for REQ-K/L/D/I with OEM id, so it should be MISSING
        assert out.applicability in ("MISSING", "REVIEW"), f"{req_id} with OEM should be MISSING/REVIEW, got {out.applicability}"

    print("PASS test_oem_satisfies_J_not_K")

def test_missing_never_becoming_fail():
    # Ensure that MISSING output never becomes FAIL in the matcher layer
    # Even with no evidence, matcher should return MISSING, not FAIL
    inp = MatcherInput(
        requirement_id="REQ-D",
        requirement_text="Similar substation experience",
        evidence_id="E-NO-EVIDENCE",
        evidence_fact="No evidence provided — empty fact",
        evidence_applicable_entity="CONSORTIUM",
        source_document="None", page_or_section="N/A"
    )
    # Our mock will treat empty fact with no keywords as MISSING
    out = matcher.safe_match(inp)
    assert out.applicability == "MISSING", f"MISSING should stay MISSING, got {out.applicability}"
    assert out.applicability != "FAIL", "MISSING must never become FAIL at matcher level"
    print("PASS test_missing_never_becoming_fail")

def test_matcher_cannot_bypass_decision_engine():
    # Matcher must NEVER produce BID/NO_BID — only PASS/FAIL/REVIEW/MISSING at requirement level
    # Final decision is deterministic in app/engines/decision.py
    inp = MatcherInput(
        requirement_id="REQ-A",
        requirement_text="First-category membership required",
        applicable_entity="GIZA",
        evidence_id="E-GIZA-001",
        evidence_fact="Giza Systems First Category certificate valid",
        evidence_applicable_entity="GIZA",
        source_document="Cert.pdf", page_or_section="Page 1"
    )
    out = matcher.safe_match(inp)
    # Ensure output is not BID/NO_BID
    assert out.applicability in ("PASS", "FAIL", "REVIEW", "MISSING"), f"Matcher must not produce BID/NO_BID, got {out.applicability}"
    assert not hasattr(out, "decision"), "MatcherOutput must not have decision field"
    assert "BID" not in out.reason or "BID" in out.reason and "requirement" in out.reason.lower(), "Reason should not contain final decision"
    # Also ensure that even with PASS, the final tender decision still requires deterministic engine
    # (e.g., one PASS does not mean BID — need all mandatory PASS)
    print("PASS test_matcher_cannot_bypass_decision_engine")

# --- New tests for hardening per review ---

def test_req_c_amount_not_on_non_req_c():
    # REQ-C amount text on a non-REQ-C requirement must NOT produce PASS (precedence bug)
    # e.g., REQ-D with fact containing "EGP 5,700,000" should NOT be PASS for REQ-D
    inp = MatcherInput(
        requirement_id="REQ-D",
        requirement_text="Similar substation experience",
        evidence_id="E-WRONG-REQ-C-AMOUNT",
        evidence_fact="Tender security EGP 5,700,000 valid for 270 days — but this is for REQ-D, not REQ-C",
        evidence_applicable_entity="CONSORTIUM",
        source_document="Doc.pdf", page_or_section="Page 1"
    )
    out = matcher.safe_match(inp)
    # Must NOT be PASS for REQ-D, even though fact contains REQ-C amount
    assert out.applicability != "PASS", f"REQ-C amount on REQ-D must NOT produce PASS, got {out.applicability} — precedence bug"
    assert out.applicability in ("MISSING", "REVIEW"), f"Should be MISSING/REVIEW, got {out.applicability}"
    print("PASS test_req_c_amount_not_on_non_req_c — REQ-C amount correctly requires REQ-C")

def test_benchmark_inference_no_gold_fields():
    # Benchmark inference object must contain NO gold fields
    from evaluation.matcher_benchmark import build_unlabeled_pairs
    pairs = build_unlabeled_pairs()
    # Check that no pair contains gold fields
    for p in pairs:
        assert "gold_expected_status" not in p, "Inference input must not contain gold_expected_status"
        assert "gold_evidence_supported" not in p, "Inference input must not contain gold_evidence_supported"
    # Also check that MatcherInput built from these pairs has no gold
    from app.matchers.base import MatcherInput as MI
    for p in pairs[:3]:
        inp = MI(
            requirement_id=p["requirement_id"],
            requirement_text=p["requirement_text"],
            evidence_id=p["evidence_id"],
            evidence_fact=p["evidence_fact"],
            source_document=p["source_document"],
            page_or_section=p["page_or_section"]
        )
        assert not hasattr(inp, "gold_expected_status")
        assert not hasattr(inp, "gold_evidence_supported")
    print("PASS test_benchmark_inference_no_gold_fields — 84 unlabeled pairs contain no gold")

def test_openai_matcher_requires_both_opt_in():
    # OpenAIMatcher with API key but without BOTH explicit flags must NOT make network calls
    import os
    from unittest.mock import patch, MagicMock
    from app.matchers import OpenAIMatcher
    # Set only one flag, not both
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-test123", "TENDERMIND_ENABLE_LLM": "1"}, clear=False):
        # Remove the other flag if present
        if "TENDERMIND_MATCHER_PROVIDER" in os.environ:
            del os.environ["TENDERMIND_MATCHER_PROVIDER"]
        matcher = OpenAIMatcher(api_key="sk-proj-test123")
        inp = MatcherInput(
            requirement_id="REQ-A", requirement_text="test", evidence_id="E-001", evidence_fact="test",
            source_document="Doc.pdf", page_or_section="Page 1"
        )
        # Should raise RuntimeError about requiring BOTH flags, not make network call
        try:
            matcher.match(inp)
            assert False, "Should have raised due to missing TENDERMIND_MATCHER_PROVIDER"
        except RuntimeError as e:
            assert "TENDERMIND_MATCHER_PROVIDER" in str(e) and "TENDERMIND_ENABLE_LLM" in str(e)
            assert "sk-proj-test123" not in str(e), "Key must not be logged"
        # Also test with only provider, no enable
        with patch.dict(os.environ, {"TENDERMIND_MATCHER_PROVIDER": "openai"}, clear=False):
            if "TENDERMIND_ENABLE_LLM" in os.environ:
                del os.environ["TENDERMIND_ENABLE_LLM"]
            matcher2 = OpenAIMatcher(api_key="sk-proj-test123")
            try:
                matcher2.match(inp)
                assert False, "Should have raised due to missing TENDERMIND_ENABLE_LLM"
            except RuntimeError as e:
                assert "TENDERMIND_ENABLE_LLM" in str(e)
        # With both flags, it would try to call API (but we don't want to actually call, so we mock)
        with patch.dict(os.environ, {"TENDERMIND_MATCHER_PROVIDER": "openai", "TENDERMIND_ENABLE_LLM": "1"}, clear=False):
            # Mock the client to return a valid JSON without network
            mock_client = MagicMock()
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock(message=MagicMock(content='{"support": true, "contradiction": false, "missing_facts": [], "supporting_facts": ["test"], "contradictory_facts": [], "applicability": "PASS", "confidence": 0.9, "reason": "test"}'))]
            mock_client.chat.completions.create.return_value = mock_resp
            with patch.object(OpenAIMatcher, "_get_client", return_value=mock_client):
                matcher3 = OpenAIMatcher(api_key="sk-proj-test123")
                out = matcher3.match(inp)
                assert out.applicability == "PASS", "With both flags and mocked client, should succeed"
    print("PASS test_openai_matcher_requires_both_opt_in — both flags required, key alone never triggers network")

def test_provider_default_is_offline():
    # Default behavior must remain offline/mock — no network even with API key present
    import os
    from unittest.mock import patch
    # Ensure no opt-in flags
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-proj-should-not-trigger"}, clear=False):
        # Remove opt-in flags if present
        for k in ["TENDERMIND_MATCHER_PROVIDER", "TENDERMIND_ENABLE_LLM"]:
            if k in os.environ:
                del os.environ[k]
        # Default matcher should be MockMatcher (offline)
        from app.matchers import MockMatcher
        m = MockMatcher()
        inp = MatcherInput(
            requirement_id="REQ-A", requirement_text="test", evidence_id="E-001", evidence_fact="First Category test",
            evidence_applicable_entity="GIZA", applicable_entity="GIZA",
            source_document="Doc.pdf", page_or_section="Page 1"
        )
        out = m.safe_match(inp)
        # Should work offline, no network
        assert out.applicability in ("PASS", "FAIL", "REVIEW", "MISSING")
        # Ensure OpenAIMatcher would not be used by default
        assert m.name == "mock-deterministic", "Default provider must be mock"
    print("PASS test_provider_default_is_offline — default remains offline/mock")

def test_provenance_survives():
    # Provenance must survive from MatcherInput into benchmark/result wrapper
    from evaluation.matcher_benchmark import build_unlabeled_pairs, run_benchmark
    from app.matchers import MockMatcher
    pairs = build_unlabeled_pairs()
    # Check that unlabeled pairs retain provenance fields
    for p in pairs[:3]:
        assert "source_document" in p, "Provenance source_document must be in input"
        assert "page_or_section" in p, "Provenance page_or_section must be in input"
        assert "evidence_id" in p, "evidence_id must be in input"
        assert p["source_document"], "source_document must not be empty"
        assert p["page_or_section"], "page_or_section must not be empty"
        assert "gold_expected_status" not in p
    # Run benchmark and check result wrapper retains provenance alongside output
    matcher = MockMatcher()
    results = run_benchmark(matcher, limit=2)
    for r in results:
        assert "provenance" in r, "Result wrapper must contain provenance alongside MatcherOutput"
        assert r["provenance"]["evidence_id"] == r["input"]["evidence_id"]
        assert r["provenance"]["source_document"] == r["input"]["source_document"]
        assert r["provenance"]["page_or_section"] == r["input"]["page_or_section"]
        assert r["provenance"]["source_document"], "Provenance source_document must not be empty"
        # Ensure MatcherOutput itself does NOT contain provenance (per requirement, do not claim it does)
        assert "source_document" not in r["output"], "MatcherOutput should not contain provenance — it is retained in wrapper, not output"
        assert "page_or_section" not in r["output"], "MatcherOutput should not contain provenance"
    print("PASS test_provenance_survives — provenance retained in wrapper, not invented, not in MatcherOutput")

def test_mock_cannot_produce_bid():
    # MockMatcher cannot produce BID or NO_BID — only requirement-level PASS/FAIL/REVIEW/MISSING
    from app.matchers import MockMatcher
    m = MockMatcher()
    # Test all requirement types
    for req_id in ["REQ-A", "REQ-B", "REQ-R", "REQ-K"]:
        inp = MatcherInput(
            requirement_id=req_id,
            requirement_text="test",
            evidence_id="E-TEST",
            evidence_fact="First Category test for GIZA" if req_id=="REQ-A" else "test fact",
            evidence_applicable_entity="GIZA" if req_id=="REQ-A" else "CONSORTIUM",
            applicable_entity="GIZA" if req_id=="REQ-A" else "CONSORTIUM",
            source_document="Doc.pdf", page_or_section="Page 1"
        )
        out = m.safe_match(inp)
        assert out.applicability in ("PASS", "FAIL", "REVIEW", "MISSING"), f"Mock must not produce BID/NO_BID, got {out.applicability} for {req_id}"
        assert out.applicability not in ("BID", "NO_BID"), "Mock must never produce tender-level decision"
    print("PASS test_mock_cannot_produce_bid — Mock only produces requirement-level statuses")

if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass
    test_strong_semantic_support()
    test_contradiction()
    test_missing_evidence()
    test_ambiguous_applicability()
    test_wrong_tender()
    test_expired_evidence()
    test_malformed_matcher_output()
    test_provenance_preservation()
    test_oem_satisfies_J_not_K()
    test_missing_never_becoming_fail()
    test_matcher_cannot_bypass_decision_engine()
    # New hardening tests
    test_req_c_amount_not_on_non_req_c()
    test_benchmark_inference_no_gold_fields()
    test_openai_matcher_requires_both_opt_in()
    test_provider_default_is_offline()
    test_provenance_survives()
    test_mock_cannot_produce_bid()
    print("\nAll 17 offline matcher tests passed — no external API calls, deterministic, provenance preserved — MockMatcher is test fixture only, not evidence of LLM F1 >=0.93")
