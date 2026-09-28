"""Stage 5K — deterministic fallback for requirements the model left UNKNOWN."""
import pytest

from app.pipeline.rule_category import rule_category


@pytest.mark.parametrize("text,expected", [
    ("HICO POWER TRANSFORMER FOUNDATION", "TECHNICAL"),
    ("Nominal System Voltage (kVrms)", "TECHNICAL"),
    ("EXACT CABLES TERMINATION BOX BE PROVIDED", "TECHNICAL"),        # cable termination, not contract
    ("No direct termination will be allowed of OSP", "TECHNICAL"),
    ("designed to disappear into the side building environment", "TECHNICAL"),  # not HSE
    ("22.1 Basis of Liquidated Damages Assessment", "COMMERCIAL"),
    ("Decrease in customs duties as provided in Schedule C", "COMMERCIAL"),
    ("Termination at the convenience of the company", "LEGAL"),
    ("27.4 Force Majeure Affecting SUBCONTRACTOR", "LEGAL"),
    ("Approval of subcontractors by the COMPANY", "SUBCONTRACTOR"),
    ("Health, safety and environmental requirements", "HSE"),
    ("Termination at COMPANY Convenience", "LEGAL"),
    ("25.3 Effective Date of Termination", "LEGAL"),
    ("1.29 \u201cServices\u201d means the engineering and design", "LEGAL"),
    ("Standard Sign Danger High Voltage", "HSE"),
    ("Door Schedule & Details", None),
    ("", None),
])
def test_rule_category(text, expected):
    assert rule_category(text) == expected


def test_source_text_wins_over_model_paraphrase():
    # model summary invented "payment"; the source says it is about foundations
    assert rule_category("TRANSFORMERS SHALL BE POSITIONED ON FOUNDATION",
                         "Transformers installed with payment by contractor") == "TECHNICAL"
    assert rule_category("x y z", "Liquidated damages for delay") == "COMMERCIAL"


def test_fallback_only_replaces_unknown_in_binding():
    from app.pipeline.contracts import LLMNormalizationResult, RequirementCandidate
    from app.pipeline.postprocessing import bind_requirement
    cand = RequirementCandidate(candidate_id="C1", parent_chunk_id="K1", source_document="SOW.pdf", page=3,
                                source_text="132 kV GIS switchgear bay")
    unk = bind_requirement(LLMNormalizationResult(summary="GIS bay", category="UNKNOWN"), cand)
    assert unk.category == "TECHNICAL" and unk.extraction_method == "two-stage+rule"
    kept = bind_requirement(LLMNormalizationResult(summary="GIS bay", category="EXPERIENCE"), cand)
    assert kept.category == "EXPERIENCE" and kept.extraction_method == "two-stage"
