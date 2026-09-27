"""Stage 4A — architecture hardening tests (fast: no Ollama, no Sarai OCR).

Covers: contracts/flags/routing; deterministic discovery; compression safety;
minimal-contract provider; deterministic post-processing; provenance validator;
job terminal states + telemetry; structured XLSX adapter; format matrix;
flag-off preservation; Variant B + decision-engine regression guards.
"""
import io
import os
from pathlib import Path

import pytest

from app.pipeline import ai_router as R
from app.pipeline.ai_router import AITask, QwenMinimalContractProvider, Router
from app.pipeline import candidate_compression as CC
from app.pipeline import candidate_discovery as CD
from app.pipeline import capabilities as CAP
from app.pipeline import config as CFG
from app.pipeline import format_extraction as FE
from app.pipeline import jobs as J
from app.pipeline import postprocessing as PP
from app.pipeline import provenance as PV
from app.pipeline import reconciliation as REC
from app.pipeline import risk as RK
from app.pipeline import structured_data as SD
from app.pipeline import two_stage_runner as TSR
from app.pipeline.contracts import (
    LLMNormalizationResult,
    NOT_CONFIGURED,
    RequirementCandidate,
    SourceText,
)

P = Path(__file__).resolve().parents[1]


def _cand(cid, doc="Vol I.pdf", page=1, text="The transformer must be 220kV GIS type.",
          signals=None, parent="chunk-0001"):
    return RequirementCandidate(candidate_id=cid, parent_chunk_id=parent,
                                source_document=doc, page=page, source_text=text,
                                span=[0, len(text)],
                                deterministic_signal_categories=list(signals or ["TECHNICAL"]))


def _ok_transport(summary="The transformer must be 220kV GIS type.", category="TECHNICAL"):
    def _t(candidate):
        return ({"summary": summary, "category": category, "mandatory": None,
                 "applicable_entity": None, "candidate_id": "FORGED",
                 "source_document": "FORGED.pdf"},
                "ok", 0.05, "{}")
    return _t


# ---------------------------------------------------------------- architecture
def test_contracts_import_and_minimal_shape():
    r = LLMNormalizationResult(summary="s", category="TECHNICAL")
    assert set(r.to_dict()) == {"summary", "category", "mandatory", "applicable_entity"}


def test_not_configured_is_falsy_sentinel():
    assert not NOT_CONFIGURED
    assert repr(NOT_CONFIGURED) == "NOT_CONFIGURED"


def test_flag_defaults_off_and_env_on():
    assert CFG.load_config({}).two_stage_enabled is False
    assert CFG.load_config({"TENDERMIND_TWO_STAGE_LLM": "1"}).two_stage_enabled is True
    assert CFG.load_config({"TENDERMIND_TWO_STAGE_LLM": "0"}).two_stage_enabled is False


def test_config_defaults_portable():
    c = CFG.load_config({})
    assert c.ollama_model == "qwen2.5:3b"
    assert c.llm_timeout_s == 90
    # Portable BY DERIVATION: defaults resolve from the repo root at runtime,
    # never from a literal machine path baked into source (see next test).
    root = Path(CFG.__file__).resolve().parents[2]
    assert c.storage_root == str(root / "uploads")
    assert c.database_url == f"sqlite:///{root / 'tender.db'}"


def test_no_hardcoded_dev_paths_in_new_pipeline():
    bad = ("C:\\", "C:/", "EgyTech", "Desktop", "/home/", "/Users/")
    for f in (P / "app" / "pipeline").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        for b in bad:
            assert b not in src, f"{f.name} contains {b!r}"


# ---------------------------------------------------------------- router
def test_router_routes_normalization_only():
    router = R.default_router()
    assert router.route(AITask.REQUIREMENT_NORMALIZATION) is not NOT_CONFIGURED
    for t in (AITask.CLAUSE_INTERPRETATION, AITask.AMBIGUITY_ANALYSIS,
              AITask.RECONCILIATION, AITask.SYNTHESIS):
        assert router.route(t) is NOT_CONFIGURED
        assert router.selection_metadata(t)["status"] == "NOT_CONFIGURED"
        res, status, _, _ = router.normalize(t, _cand("c1"))
        assert res is None and status == "not_configured"


def test_provider_whitelist_drops_model_forgeries():
    p = QwenMinimalContractProvider(transport=_ok_transport())
    res, status, _, _ = p.normalize_requirement(_cand("c1"))
    assert status == "ok"
    assert set(res.to_dict()) == {"summary", "category", "mandatory", "applicable_entity"}


def test_provider_timeout_makes_no_requirement():
    def _t(c):
        raise TimeoutError("timed out")
    p = QwenMinimalContractProvider(transport=_t)
    res, status, _, _ = p.normalize_requirement(_cand("c1"))
    assert res is None and status == "timeout"
    assert p.metrics()["timeouts"] == 1


def test_provider_contract_violations_rejected():
    for status_in, summary, category in [("malformed", "", "TECHNICAL"),
                                         ("bad_category", "x", "NOPE"),
                                         ("multi", "", "TECHNICAL")]:
        def _t(c, s=status_in):
            return None, s, 0.01, "raw"
        p = QwenMinimalContractProvider(transport=_t)
        res, status, _, _ = p.normalize_requirement(_cand("c1"))
        assert res is None and status == status_in


def test_provider_preserves_unknown_never_false():
    p = QwenMinimalContractProvider(transport=_ok_transport(category="UNKNOWN"))
    res, status, _, _ = p.normalize_requirement(_cand("c1"))
    assert status == "ok" and res.category == "UNKNOWN"


def test_registry_only_normalization_enabled():
    assert CAP.enabled_tasks() == ["REQUIREMENT_NORMALIZATION"]
    assert CAP.get_capability("RECONCILIATION")["enabled"] is False
    assert CAP.get_capability("REQUIREMENT_NORMALIZATION")["confidence"] == "none"


# ---------------------------------------------------------------- discovery
def _parent(pid="chunk-0001", doc="Vol I.pdf", page=3, text=""):
    return {"chunk_id": pid, "source_document": doc, "page_number": page, "text": text}


def test_discovery_deterministic_under_shuffle():
    texts = ("The 220kV GIS transformer must be installed and tested. "
             "Delivery and completion shall occur within twelve months. "
             "Payment terms are thirty days after invoice. " * 4)
    a = [_parent("chunk-0002", "B.pdf", 2, texts), _parent("chunk-0001", "A.pdf", 1, texts)]
    b = list(reversed(a))
    acc1, _, _ = CD.discover_from_parents(a)
    acc2, _, _ = CD.discover_from_parents(b)
    assert [(c.candidate_id, c.source_text) for c in acc1] == [(c.candidate_id, c.source_text) for c in acc2]


def test_discovery_native_ids_spans_signals_quality():
    text = ("The 220kV GIS transformer must be installed. " * 8
            + "Bid validity shall be 90 days from submission. " * 8)
    acc, rej, m = CD.discover_from_parents([_parent(text=text)])
    assert acc and all(c.candidate_id.startswith("chunk-0001-seg-") for c in acc)
    assert all(c.span and c.source_document == "Vol I.pdf" and c.page == 3 for c in acc)
    assert all(c.deterministic_signal_categories for c in acc)
    assert m.accepted == len(acc)


def test_discovery_tiny_parent_skipped():
    acc, rej, m = CD.discover_from_parents([_parent(text="short")])
    assert acc == [] and m.skipped_tiny == 1


def test_discovery_rejects_garbage_and_multisignal():
    ok_line = ("The 220kV GIS transformer must be installed and tested. " * 8).strip()
    garbage_line = ("JG\x00\x01\x02" * 40 + " end of line here.").strip()
    multi_line = ("The 220kV transformer delivery requires similar project experience "
                  "within twelve months guaranteed. " * 4).strip()
    assert len(CD.pattern_hits(multi_line)) > 2  # guard: genuinely multi-signal
    text = "\n".join([ok_line, garbage_line, multi_line])
    acc, rej, m = CD.discover_from_parents([_parent(text=text)])
    reasons = {r["rejection_reason"] for r in rej}
    assert "ocr_garbage" in reasons and "mixed_multi_category" in reasons
    assert acc  # the clean line still yields candidates


# ---------------------------------------------------------------- compression
def test_exact_and_normalized_dedup_with_provenance():
    c1 = _cand("chunk-0001-seg-01", text="The transformer must be 220kV GIS type.")
    c2 = _cand("chunk-0001-seg-02", text="The transformer must be 220kV GIS type.")
    c3 = _cand("chunk-0002-seg-01", text="  THE transformer must be 220kV GIS type! ")
    q, rep = CC.compress_candidates([c1, c2, c3])
    assert len(q) == 1 and q[0].candidate_id == "chunk-0001-seg-01"
    assert rep.metrics.exact_duplicates == 1 and rep.metrics.normalized_duplicates == 1
    assert set(q[0].merged_from) == {"chunk-0001-seg-02", "chunk-0002-seg-01"}
    assert rep.metrics.reduction_pct == pytest.approx(66.67, abs=0.01)


def test_cross_document_never_merges_by_default():
    c1 = _cand("chunk-0001-seg-01", doc="A.pdf")
    c2 = _cand("chunk-0002-seg-01", doc="B.pdf")
    q, rep = CC.compress_candidates([c1, c2])
    assert len(q) == 2 and rep.metrics.merged_candidates == 0


def test_cross_document_merge_needs_flag_and_justification():
    c1 = _cand("chunk-0001-seg-01", doc="A.pdf")
    c2 = _cand("chunk-0002-seg-01", doc="B.pdf")
    q, rep = CC.compress_candidates([c1, c2], allow_cross_document=True,
                                    cross_document_justification="same addendum reprint")
    assert len(q) == 1
    assert rep.merge_groups[0]["justification"] == "same addendum reprint"


def test_disjoint_signals_never_merge_false_merge_safety():
    c1 = _cand("chunk-0001-seg-01", text="The 220kV transformer must be installed and tested ok.",
               signals=["TECHNICAL"])
    c2 = _cand("chunk-0001-seg-02", text="The 220kV transformer must be installed and tested ok!",
               signals=["SCHEDULE"])
    q, rep = CC.compress_candidates([c1, c2])
    assert len(q) == 2  # near-identical text, clearly different requirements


def test_near_duplicate_merges_same_document():
    base = "Supply and install one 220kV GIS transformer bay complete with testing"
    c1 = _cand("chunk-0001-seg-01", text=base + " works.")
    c2 = _cand("chunk-0001-seg-02", text=base + " works please.")
    q, rep = CC.compress_candidates([c1, c2])
    assert len(q) == 1 and rep.metrics.near_duplicates == 1


def test_priority_filter_and_cap_are_deterministic():
    tech = _cand("chunk-0001-seg-01", signals=["TECHNICAL"])
    sched = _cand("chunk-0001-seg-02", text="Delivery within twelve months please confirm.",
                  signals=["SCHEDULE"])
    q, rep = CC.compress_candidates([tech, sched], priority_categories=["SCHEDULE"])
    assert [c.candidate_id for c in q] == ["chunk-0001-seg-02"]
    # Cap: deterministic order = more signals, then longer text, then id.
    # Here signals tie 1-1 so the longer text (sched, 45 chars) wins the single slot.
    q2, _ = CC.compress_candidates([tech, sched], max_ai_candidates=1)
    assert [c.candidate_id for c in q2] == ["chunk-0001-seg-02"]
    q3, _ = CC.compress_candidates([sched, tech], max_ai_candidates=1)
    assert [c.candidate_id for c in q3] == ["chunk-0001-seg-02"]  # input order irrelevant


# ---------------------------------------------------------------- postprocessing
def test_postprocess_end_to_end_ids_evidence():
    pairs = [(LLMNormalizationResult(summary="Install GIS", category="TECHNICAL"), _cand("chunk-0002-seg-01")),
             (LLMNormalizationResult(summary="Pay in 30 days", category="COMMERCIAL"), _cand("chunk-0001-seg-01", page=2, signals=["COMMERCIAL"]))]
    reqs, evs, fails = PP.post_process(pairs)
    assert [r.requirement_id for r in reqs] == ["REQ-001", "REQ-002"]  # sorted by doc/page/summary
    assert len(evs) == 2 and fails == []
    assert all(e.fact == r.summary and e.requirement_id == r.requirement_id
               for e, r in zip(sorted(evs, key=lambda e: e.requirement_id), reqs))


def test_postprocess_rejects_bad_category_and_keeps_unknown():
    ok_u = (LLMNormalizationResult(summary="Unclear fragment here please", category="UNKNOWN"), _cand("chunk-0001-seg-01"))
    bad = (LLMNormalizationResult(summary="x", category="NOPE"), _cand("chunk-0001-seg-02"))
    reqs, evs, fails = PP.post_process([ok_u, bad])
    assert len(reqs) == 1 and reqs[0].category == "UNKNOWN"
    assert any(f["reason"] == "bad_category" for f in fails)


def test_grounding_score_measured_not_hard_gate():
    assert PP.grounding_score("Install the GIS", "Install the GIS quickly") > 0
    assert PP.grounding_score("", "anything") == 0.0


# ---------------------------------------------------------------- provenance
def _final_pair():
    cand = _cand("chunk-0001-seg-01")
    req, _, _ = PP.post_process([(LLMNormalizationResult(summary="Install GIS", category="TECHNICAL"), cand)])
    ev = PP.derive_evidence(req[0])
    return req, [ev], {"chunk-0001-seg-01": cand}


def test_provenance_clean_case():
    reqs, evs, by_id = _final_pair()
    assert PV.validate_provenance(reqs, evs, by_id) == []


def test_provenance_detects_drift_and_mismatch():
    reqs, evs, by_id = _final_pair()
    drifted = [type(r)(**{**r.__dict__, "source_document": "Other.pdf"}) for r in reqs]
    v = PV.validate_provenance(drifted, evs, by_id)
    assert any(x["reason"] == "cross_document_drift" for x in v)
    bad_ev = [type(e)(**{**e.__dict__, "fact": "forged"}) for e in evs]
    v2 = PV.validate_provenance(reqs, bad_ev, by_id)
    assert any(x["reason"] == "fact_summary_mismatch" for x in v2)
    v3 = PV.validate_provenance(reqs, evs, {})
    assert any(x["reason"] == "unknown_candidate" for x in v3)


# ---------------------------------------------------------------- jobs
def test_terminal_states():
    assert J.resolve_terminal_status(5, 5, 0, 0) == "COMPLETED"
    assert J.resolve_terminal_status(5, 4, 1, 0) == "PARTIAL"
    assert J.resolve_terminal_status(5, 0, 5, 0) == "FAILED"
    assert J.resolve_terminal_status(2, 0, 0, 2) == "PARTIAL"  # unsupported-only honest
    assert J.resolve_terminal_status(0, 0, 0, 0) == "COMPLETED"


def test_version_metadata_pinned():
    m = J.pipeline_version_metadata("qwen2.5:3b")
    assert m["pipeline_version"] == "2-stage-1.0"
    assert m["normalizer_contract_version"] == "minimal-1"


# ---------------------------------------------------------------- runner
def _stub_router(mapping):
    def _t(candidate):
        cat = mapping.get(candidate.candidate_id, "TECHNICAL")
        if cat == "TIMEOUT":
            raise TimeoutError("t/o")
        return ({"summary": candidate.source_text[:60], "category": cat,
                 "mandatory": None, "applicable_entity": None}, "ok", 0.01, "{}")
    return Router({AITask.REQUIREMENT_NORMALIZATION.value: QwenMinimalContractProvider(transport=_t)})


def _sources():
    pad = "with all required accessories and testing "
    return [SourceText("A.pdf", 1, ("The 220kV GIS transformer must be installed " + pad) * 6),
            SourceText("B.pdf", 1, ("Delivery and completion within twelve months " + pad) * 6)]


def test_runner_happy_path_telemetry():
    res, tel = TSR.run_two_stage("T1", _sources(), job_id="JOB-1", router=_stub_router({}))
    assert res.status == "COMPLETED"
    assert tel.requirements_final == len(res.requirements) > 0
    assert tel.evidence_final == len(res.evidence) == len(res.requirements)
    assert tel.model_call_count == tel.candidates_sent_to_ai > 0
    assert res.processing["pipeline_version"] == "2-stage-1.0"


def _sources_as_candidates(res):
    from app.pipeline.contracts import RequirementCandidate as RC
    return [RC(candidate_id=r.candidate_id, parent_chunk_id=r.parent_chunk_id or "",
               source_document=r.source_document, page=r.page_number,
               source_text=r.source_text,
               deterministic_signal_categories=[]) for r in res.requirements]


def test_runner_provenance_strict():
    res, _ = TSR.run_two_stage("T1", _sources(), router=_stub_router({}))
    by_id = {r.candidate_id: type("C", (), {"source_document": r.source_document, "page": r.page_number,
                                            "source_text": r.source_text,
                                            "parent_chunk_id": r.parent_chunk_id or "p"})()
             for r in res.requirements}
    # rebuild real candidates via discovery for a strict check
    from app.pipeline.candidate_discovery import discover_from_sources
    acc, _, _ = discover_from_sources(_sources())
    strict = {c.candidate_id: c for c in acc}
    assert PV.validate_provenance(res.requirements, res.evidence, strict,
                                  require_canonical_ids=True) == []


def test_runner_partial_on_doc_and_candidate_failure():
    doc_results = {
        "A.pdf": {"status": "COMPLETE", "page_count": 1, "total_text_chars": 2000,
                  "pages": [{"page_number": 1, "text": ("The 220kV GIS must be installed ok " * 40),
                             "method": "txt", "ocr_applied": False}]},
        "B.pdf": {"status": "FAILED", "page_count": 0, "total_text_chars": 0,
                  "pages": [], "error": "boom"},
        "C.zip": {"status": "UNSUPPORTED", "page_count": 0, "total_text_chars": 0, "pages": []},
    }
    sources, extras = TSR.adapt_doc_results(doc_results)
    assert extras["documents_failed"] == 1 and extras["documents_unsupported"] == 1
    res, tel = TSR.run_two_stage("T1", sources, router=_stub_router({}),
                                 deterministic_extras=extras)
    assert res.status == "PARTIAL"
    assert res.document_failures and len(res.document_failures) == 2


def test_runner_llm_failure_fabricates_nothing():
    res, tel = TSR.run_two_stage("T1", _sources(),
                                 router=_stub_router({"chunk-0001-seg-01": "TIMEOUT"}))
    assert tel.timeout_count >= 1
    assert all(r.summary for r in res.requirements)
    assert tel.requirements_final == len(res.requirements)


# ---------------------------------------------------------------- structured + formats
def test_xlsx_adapter_in_memory_no_paths():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Price"
    ws.append(["item", "description", "qty"])
    ws.append(["1", "GIS bay", "2"])
    ws.append(["", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.name = "schedule.xlsx"
    buf.seek(0)
    tables = SD.read_structured(buf)
    assert len(tables) == 1 and tables[0].sheet == "Price"
    assert tables[0].rows[0] == {"item": "1", "description": "GIS bay", "qty": "2"}


def test_xlsx_adapter_rejects_garbage():
    assert SD.read_structured(io.BytesIO(b"not a workbook")) == []
    assert SD.read_structured("/nonexistent/file.xlsx") == []


def test_format_matrix_policy():
    assert FE.classify_format("a.PDF") == FE.FormatKind.PDF
    assert FE.classify_format("b.xlsx") == FE.FormatKind.XLSX
    assert FE.classify_format("c.dwg") == FE.FormatKind.CAD
    assert FE.classify_format("d.zip") == FE.FormatKind.ARCHIVE
    assert FE.classify_format("noext") == FE.FormatKind.UNSUPPORTED
    assert FE.is_extractable("a.pdf") and not FE.is_extractable("a.zip")
    assert "tesseract" in FE.format_matrix()["PDF"].lower()


# ---------------------------------------------------------------- boundaries
def test_reconciliation_and_risk_not_configured():
    assert REC.reconcile(REC.ReconciliationInput()) is NOT_CONFIGURED
    assert RK.analyze_ambiguity([])["status"] == "NOT_CONFIGURED"
    assert RK.identify_risks([])["status"] == "NOT_CONFIGURED"
    assert RK.synthesize([])["status"] == "NOT_CONFIGURED"


def test_deterministic_gaps_no_severity():
    from app.pipeline.contracts import ValidatedRequirement as VR
    reqs = [VR("REQ-001", "c1", "p", "s", "TECHNICAL", None, None, "A.pdf", 1, "t"),
            VR("REQ-002", "c2", "p", "s", "UNKNOWN", True, None, "A.pdf", 1, "t")]
    g = RK.summarize_gaps(reqs)
    assert g.mandatory_unknown == 1 and g.unknown_category == 1
    assert set(g.requirement_ids_needing_review) == {"REQ-001", "REQ-002"}


# ---------------------------------------------------------------- regression guards
def test_variant_b_prompt_hash_unchanged():
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"


def test_decision_engine_interface_intact():
    import inspect
    import app.engines.decision as d
    assert callable(d.decide) and callable(d.get_or_create_decision)
    assert list(inspect.signature(d.decide).parameters) == ["db", "tender_id", "status_results"]


def test_two_stage_schema_permits_unknown_only_additively():
    base = (P / "schemas" / "tender_agnostic_schema.json").read_text(encoding="utf-8")
    new = (P / "schemas" / "tender_agnostic_schema_2stage.json").read_text(encoding="utf-8")
    import json
    b, n = json.loads(base), json.loads(new)
    b["properties"]["requirements"]["items"]["properties"]["category"]["enum"].append("UNKNOWN")
    b["properties"]["requirements"]["items"]["properties"]["extraction_method"]["enum"].append("two-stage")
    b["properties"]["requirements"]["items"]["properties"]["extraction_method"]["enum"].sort()
    # Stage 5A: two-stage never fabricates confidence -> null permitted on
    # requirements/evidence (live E2E failed persistence without this).
    for sec in ("requirements", "evidence"):
        conf = b["properties"][sec]["items"]["properties"]["confidence"]
        conf["type"] = ["number", "null"]
        conf["description"] = n["properties"][sec]["items"]["properties"]["confidence"]["description"]
    b["title"] = n["title"]
    b["description"] = n["description"]
    assert b == n  # ONLY documented deltas: UNKNOWN quarantine + two-stage method + null confidence
