"""Stage 5A — minimal-2 prompt, per-task escalation, real model/prompt metadata."""
from app.pipeline import ai_router as R
from app.pipeline.ai_router import AITask, EscalatingProvider, QwenMinimalContractProvider
from app.pipeline.contracts import RequirementCandidate
from app.pipeline.prompts import REQUIREMENT_NORMALIZATION_SYSTEM


def _cand(text="Tender security EGP 500,000."):
    return RequirementCandidate(candidate_id="c1", parent_chunk_id="p1", source_document="d.pdf",
                                page=1, source_text=text, span=[0, len(text)],
                                deterministic_signal_categories=[])


def _stub(category, status="ok"):
    def t(_c):
        if status != "ok":
            return None, status, 0.01, None
        return {"summary": "s", "category": category, "mandatory": None,
                "applicable_entity": None}, "ok", 0.01, "{}"
    return t


def test_prompt_v2_keeps_minimal_contract_and_defines_every_category():
    p = REQUIREMENT_NORMALIZATION_SYSTEM
    for key in ('"summary"', '"category"', '"mandatory"', '"applicable_entity"'):
        assert key in p
    for forbidden in ('"candidate_id"', '"evidence"', '"provenance"', '"source_document"'):
        assert forbidden not in p
    for cat in ("LEGAL", "TECHNICAL", "EXPERIENCE", "EQUIPMENT", "FINANCIAL", "SCHEDULE",
                "COMMERCIAL", "HSE", "QA_QC", "PERSONNEL", "SUBCONTRACTOR", "SUBMISSION", "UNKNOWN"):
        assert f"- {cat}:" in p, cat


def test_prompt_version_default_and_rollback(monkeypatch):
    monkeypatch.delenv("TENDERMIND_PROMPT_VERSION", raising=False)
    assert R.active_prompt_version() == "minimal-2"
    assert R.active_system_prompt() == REQUIREMENT_NORMALIZATION_SYSTEM
    monkeypatch.setenv("TENDERMIND_PROMPT_VERSION", "minimal-1")
    assert R.active_prompt_version() == "minimal-1"
    assert R.active_system_prompt() != REQUIREMENT_NORMALIZATION_SYSTEM


def test_model_name_follows_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "some-model:7b")
    assert QwenMinimalContractProvider(transport=_stub("LEGAL")).model_name == "some-model:7b"


def test_escalation_not_called_for_confident_answer():
    calls = []
    esc = EscalatingProvider(QwenMinimalContractProvider(transport=_stub("COMMERCIAL")), "big",
                             transport=lambda c: calls.append(c) or _stub("LEGAL")(c))
    res, status, _, _ = esc.normalize_requirement(_cand())
    assert status == "ok" and res.category == "COMMERCIAL" and not calls
    assert esc.escalations == 0


def test_escalation_replaces_unknown_with_valid_answer():
    esc = EscalatingProvider(QwenMinimalContractProvider(transport=_stub("UNKNOWN")), "big",
                             transport=_stub("TECHNICAL"))
    res, status, _, _ = esc.normalize_requirement(_cand())
    assert status == "ok" and res.category == "TECHNICAL"
    assert esc.escalations == 1 and esc.escalation_wins == 1


def test_escalation_failure_keeps_primary_outcome():
    esc = EscalatingProvider(QwenMinimalContractProvider(transport=_stub("UNKNOWN")), "big",
                             transport=_stub(None, status="timeout"))
    res, status, _, _ = esc.normalize_requirement(_cand())
    assert status == "ok" and res.category == "UNKNOWN"
    esc2 = EscalatingProvider(QwenMinimalContractProvider(transport=_stub(None, status="malformed")),
                              "big", transport=_stub("UNKNOWN"))
    res2, status2, _, _ = esc2.normalize_requirement(_cand())
    assert res2 is None and status2 == "malformed"  # no fabricated requirement


def test_default_router_escalation_is_opt_in(monkeypatch):
    monkeypatch.delenv("TENDERMIND_ESCALATION_MODEL", raising=False)
    assert isinstance(R.default_router().route(AITask.REQUIREMENT_NORMALIZATION),
                      QwenMinimalContractProvider)
    monkeypatch.setenv("TENDERMIND_ESCALATION_MODEL", "gemma3:12b")
    assert isinstance(R.default_router().route(AITask.REQUIREMENT_NORMALIZATION),
                      EscalatingProvider)


def test_processing_passes_worker_config():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "app" / "processing.py").read_text(encoding="utf-8")
    assert "workers=_lwc()" in src
    assert 'model_name = "qwen2.5:3b"' not in src


def test_two_stage_null_confidence_passes_strict_schema():
    """Regression (5A live E2E): two-stage requirements/evidence carry
    confidence=None by design; strict jsonschema used to reject every AI run."""
    import json
    from dataclasses import asdict
    from pathlib import Path
    import jsonschema
    from app.pipeline.contracts import LLMNormalizationResult
    from app.pipeline.postprocessing import post_process
    reqs, evs, _ = post_process([(LLMNormalizationResult(summary="s", category="TECHNICAL",
                                                         mandatory=None, applicable_entity=None), _cand())])
    assert reqs[0].confidence is None
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" /
                         "tender_agnostic_schema_2stage.json").read_text(encoding="utf-8"))
    for sec, rows in (("requirements", reqs), ("evidence", evs)):
        item_schema = schema["properties"][sec]["items"]["properties"]["confidence"]
        jsonschema.validate(asdict(rows[0])["confidence"], item_schema)


def test_tesseract_routing_pages_keep_real_page_numbers(monkeypatch):
    """Regression (5B real-tender run): routing returns source_page_number,
    every consumer reads page_number -> all provenance collapsed to page 1."""
    import evaluation.run_real_benchmark as rb
    from app.pipeline.two_stage_runner import adapt_doc_results
    fake = [{"source_page_number": n, "text": f"page {n} text " * 20, "method": "fitz"} for n in (1, 2, 3)]

    class _Mod:
        @staticmethod
        def extract_pdf_with_tesseract_routing(_p):
            return [dict(x) for x in fake]

    import importlib.util
    monkeypatch.setattr(importlib.util, "module_from_spec", lambda spec: _Mod)
    monkeypatch.setattr(importlib.util, "spec_from_file_location",
                        lambda *a, **k: type("S", (), {"loader": type("L", (), {"exec_module": staticmethod(lambda m: None)})()})())
    pages = rb._call_tesseract_routing("x.pdf")
    assert [p["page_number"] for p in pages] == [1, 2, 3]
    # and the AI adapter honours source_page_number even if page_number is absent
    sources, _ = adapt_doc_results({"a.pdf": {"status": "COMPLETE", "pages": [dict(x) for x in fake]}})
    assert [s.page_number for s in sources] == [1, 2, 3]
