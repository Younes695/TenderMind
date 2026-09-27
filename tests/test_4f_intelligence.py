"""Stage 4F tests (fast: stub LLM transport; no Ollama, no Sarai)."""
import json
from pathlib import Path

from app.pipeline import ambiguity as AMB
from app.pipeline import commercial_schedule as CS
from app.pipeline import gaps as GP
from app.pipeline import intelligence_runner as IR
from app.pipeline import reconciliation_mvp as RC
from app.pipeline import risk_synthesis as RS
from app.pipeline import structured_first as SF
from app.pipeline.ai_router import AITask, Router
from app.pipeline.capability_tiers import load_worker_config
from app.pipeline.contracts import (
    AddendumRecord,
    ClarificationRecord,
    CommercialLineItem,
    DocumentArtifact,
    LLMNormalizationResult,
    RequirementCandidate,
    SourceText,
    StructuredTable,
    ValidatedRequirement,
)
from app.pipeline.structured_data import normalize_boq_table

P = Path(__file__).resolve().parents[1]


def _cand(cid, doc="A.pdf", page=1, text="Supply six circuit breakers, 220kV GIS.",
          signals=None):
    return RequirementCandidate(candidate_id=cid, parent_chunk_id="chunk-0001",
                                source_document=doc, page=page, source_text=text,
                                span=[0, len(text)],
                                deterministic_signal_categories=list(signals or ["TECHNICAL"]))


def _stub_router(mapping=None):
    from app.pipeline.ai_router import QwenMinimalContractProvider
    mapping = mapping or {}

    def _t(candidate):
        cat = mapping.get(candidate.candidate_id, "TECHNICAL")
        if cat == "TIMEOUT":
            raise TimeoutError("t/o")
        return ({"summary": candidate.source_text[:60], "category": cat,
                 "mandatory": None, "applicable_entity": None}, "ok", 0.01, "{}")

    return Router({AITask.REQUIREMENT_NORMALIZATION.value: QwenMinimalContractProvider(transport=_t)})


def _vreq(rid="REQ-001", cid="chunk-0001-seg-01", summary="Install GIS", cat="TECHNICAL",
          doc="A.pdf", page=1, text="Install the GIS.", mandatory=None):
    return ValidatedRequirement(rid, cid, "chunk-0001", summary, cat, mandatory, None,
                                doc, page, text, {"quote_en": text[:200]}, "two-stage", 0.7)


# ---- structured-first ----
def test_structured_facts_suppress_redundant_ai_calls():
    li = CommercialLineItem("sched.xlsx", "Sheet1!R5", item="1A",
                            description="Three phase circuit breakers 220kV GIS",
                            unit="Nos.", quantity="6")
    c = _cand("chunk-0001-seg-01", text="Three phase circuit breakers 220kV GIS, Nos., quantity 6",
              signals=["TECHNICAL"])
    q, rep = SF.structured_first_filter([c], [li])
    assert q == [] and rep.covered == 1 and rep.reduction_pct == 100.0
    assert rep.coverages[0].covered_by == "BOQ:sched.xlsx!Sheet1!R5"


def test_semantic_candidates_retained_no_data_loss():
    li = CommercialLineItem("s.xlsx", "S!R2", item="1A", description="Breakers", quantity="6")
    legal = _cand("c1", text="Tenderer must be the manufacturer in a joint venture.", signals=["LEGAL"])
    person = _cand("c2", text="The transformer must be installed and tested.", signals=["TECHNICAL"])
    q, rep = SF.structured_first_filter([legal, person], [li])
    assert {c.candidate_id for c in q} == {"c1", "c2"}  # LEGAL never suppressed; no overlap
    assert rep.covered == 0


def test_different_terms_never_merge_or_cover():
    li = CommercialLineItem("s.xlsx", "S!R2", item="1A", description="Breakers", quantity="6")
    c = _cand("c1", text="Breakers quantity 12 with penalty terms apply", signals=["COMMERCIAL"])
    q, rep = SF.structured_first_filter([c], [li], threshold=0.9)
    assert len(q) == 1  # high threshold: differing terms not covered


# ---- compression stages ----
def test_compression_chain_metrics():
    from app.pipeline.candidate_compression import compress_candidates
    c1 = _cand("chunk-0001-seg-01")
    c2 = _cand("chunk-0001-seg-02", text="Supply six circuit breakers, 220kV GIS.")
    c3 = _cand("chunk-0001-seg-03", text="  supply SIX circuit breakers, 220kV GIS! ")
    q, rep = compress_candidates([c1, c2, c3])
    assert rep.metrics.exact_duplicates == 1 and rep.metrics.normalized_duplicates == 1
    assert len(q) == 1 and set(q[0].merged_from) == {"chunk-0001-seg-02", "chunk-0001-seg-03"}


# ---- schedule ----
def test_explicit_date_and_known_anchor():
    s = [SourceText("A.pdf", 1, "Delivery within 30 days from award. Closing date 15/03/2026.")]
    facts = CS.extract_schedule_facts(s, anchors={"award": "2026-01-10"})
    kinds = {r.kind for r in facts.records}
    assert "duration" in kinds and "explicit-date" in kinds
    d = CS.schedule_record_dict(next(r for r in facts.records if r.kind == "duration"))
    assert d["anchor_type"] == "explicit-anchor" and d["anchor_value"] == "2026-01-10"
    assert d["normalized_duration"] == "P30D" and d["raw_expression"].startswith("within 30 days")


def test_relative_date_unknown_anchor_stays_explicit():
    s = [SourceText("A.pdf", 2, "Completion within 12 months from award.")]
    (r,) = [x for x in CS.extract_schedule_facts(s).records if x.kind == "duration"]
    d = CS.schedule_record_dict(r)
    assert d["anchor_type"] == "unknown" and d["anchor_value"] is None
    assert d["normalized_date"] is None and d["normalized_duration"] == "P12M"


# ---- commercial ----
def test_commercial_currency_payment_security_validity():
    s = [SourceText("A.pdf", 1, "Prices in EGP. Advance payment 10%. Bid security 2%. Offer valid 90 days.")]
    f = CS.extract_commercial_facts(s)
    assert f.currency == "EGP" and f.currency_source == "A.pdf#p1"
    assert f.payment_terms and f.bid_security and f.validity
    assert f.amounts  # monetary expressions captured with source


def test_structured_price_rows():
    t = StructuredTable("s.xlsx", "S1", ["Item", "Description", "Quantity"],
                        [{"Item": "1A", "Description": "Breaker", "Quantity": "6"}], 1)
    (it,) = normalize_boq_table(t)
    assert (it.item, it.quantity, it.location) == ("1A", "6", "S1!R2")


# ---- reconciliation ----
def test_identical_requirement_grouped_with_evidence():
    r1 = _vreq("REQ-001", "c1", summary="Install the GIS", doc="A.pdf")
    r2 = _vreq("REQ-002", "c2", summary="install  the   GIS", doc="B.pdf")
    (g,) = RC.group_duplicates([r1, r2])
    assert g.requirement_ids == ["REQ-001", "REQ-002"] and g.evidence == g.requirement_ids


def test_explicit_amendment_linked_not_inferred():
    r = _vreq(summary="Price schedule section 7B quantities")
    a = AddendumRecord("Add1.pdf", "p2", amendment="Addendum 1", affected_item="section 7B quantities")
    (l,) = RC.link_amendments([r], [a], [])
    assert l.status == RC.AMENDED and l.evidence == ["REQ-001"]
    assert RC.link_amendments([_vreq()], [], []) == []  # no filename inference


def test_unknown_conflict_stays_unknown():
    r = _vreq(doc="Clarification 1.pdf")
    (l,) = RC.link_amendments([r], [], [])
    assert l.status == RC.SUPERSESSION_UNKNOWN


def test_boq_conflict_preserves_both_sides():
    items = [CommercialLineItem("a.xlsx", "S!R2", item="1A", quantity="6"),
             CommercialLineItem("b.xlsx", "S!R3", item="1A", quantity="12")]
    (c,) = RC.find_boq_conflicts(items)
    assert c.resolution == "REVIEW_REQUIRED" and len(c.evidence) == 2


# ---- gaps ----
def test_gaps_package_completeness_only():
    docs = [DocumentArtifact("a.pdf", "", ".pdf", status="FAILED", error="boom"),
            DocumentArtifact("b.zip", "", ".zip", status="UNSUPPORTED"),
            DocumentArtifact("c.pdf", "", ".pdf", status="COMPLETE", page_count=2, total_text_chars=0)]
    gaps = GP.analyze_package_gaps(docs, [])
    kinds = {g.kind for g in gaps}
    assert {"failed-extraction", "unsupported-type", "empty-ocr"} <= kinds
    assert all(g.evidence for g in gaps)
    blob = json.dumps([g.__dict__ for g in gaps]).lower()
    assert "bidder" not in blob and "company failed" not in blob


def test_referenced_form_absent():
    docs = [DocumentArtifact("Vol1.pdf", "", ".pdf", status="COMPLETE", page_count=1, total_text_chars=100)]
    src = [SourceText("Vol1.pdf", 1, "Submit Exhibit C with the offer.")]
    gaps = GP.analyze_package_gaps(docs, src)
    assert any(g.kind == "referenced-form-absent" for g in gaps)


# ---- ambiguity ----
def test_ambiguity_types_evidence_grounded():
    reqs = [_vreq("REQ-001", "c1", summary="Submit TBD documents", cat="TECHNICAL",
                  text="Submit TBD documents please."),
            _vreq("REQ-002", "c2", summary="Delivery within 30 days from award", cat="SCHEDULE",
                  text="Delivery within 30 days from award."),
            _vreq("REQ-003", "c3", summary="Unclear fragment", cat="UNKNOWN", text="Unclear fragment.")]
    ambs = AMB.analyze_ambiguity(reqs)
    types = {a.ambiguity_type for a in ambs}
    assert {"missing-value", "unclear-date-anchor", "undefined-term"} <= types
    assert all(a.evidence and a.clarification_needed and a.human_review_required for a in ambs)


# ---- risk ----
def test_risk_grounded_no_severity():
    from app.pipeline.commercial_schedule import CommercialFacts
    sigs = RS.derive_risk_signals(
        GP.analyze_package_gaps([DocumentArtifact("x.zip", "", ".zip", status="UNSUPPORTED")], []),
        [], [], CommercialFacts(), [])
    assert sigs and all(s.requires_management_review for s in sigs)
    blob = json.dumps([s.__dict__ for s in sigs])
    import re as _re
    # no BID/NO-BID automation language (bid-security as a commercial term is legitimate)
    assert not _re.search(r"\bBID\b(?!-security)|\bNO-BID\b", blob)
    assert "severity" not in blob.lower() and "probability" not in blob.lower()
    assert "monetary impact" not in blob.lower() and "business impact" not in blob.lower()


# ---- synthesis ----
def test_synthesis_grounded_neutral_empty_states():
    from app.pipeline.commercial_schedule import CommercialFacts
    s = RS.synthesize([], [], CommercialFacts(), [], [], [], [],
                      {"total": 0, "complete": 0, "failed": 0, "unsupported": 0})
    assert s["status"] == "SYNTHESIS_MVP_DETERMINISTIC"
    assert s["commercial_facts"]["currency"] == "not available in validated material"
    blob = json.dumps(s)
    assert "BID" not in blob and "NO-BID" not in blob and "severity" not in blob.lower()


# ---- runner ----
def test_intelligence_runner_end_to_end_stub():
    pad = "with all required accessories and testing "
    sources = [SourceText("A.pdf", 1, ("The 220kV GIS transformer must be installed " + pad) * 6),
               SourceText("B.pdf", 1, "Prices in EGP. Advance payment applies.")]
    docs = [DocumentArtifact("A.pdf", "", ".pdf", status="COMPLETE", page_count=1, total_text_chars=500),
            DocumentArtifact("B.pdf", "", ".pdf", status="COMPLETE", page_count=1, total_text_chars=60)]
    analysis, telem = IR.run_intelligence("T1", sources, documents=docs, router=_stub_router())
    assert telem.requirements_final == len(analysis["requirements"]) > 0
    assert telem.evidence_final == len(analysis["evidence"])
    assert analysis["commercial_facts"]["currency"] == "EGP"
    assert analysis["synthesis"]["status"] == "SYNTHESIS_MVP_DETERMINISTIC"
    assert telem.candidates_structured_covered >= 0 and telem.synthesis_status
    from app.pipeline.provenance import validate_provenance
    from app.pipeline.candidate_discovery import discover_from_sources
    acc, _, _ = discover_from_sources(sources)
    by_id = {c.candidate_id: c for c in acc}
    from app.pipeline.contracts import ValidatedRequirement as VR, EvidenceLink as EL
    reqs = [VR(**r) for r in analysis["requirements"]]
    evs = [EL(**e) for e in analysis["evidence"]]
    assert validate_provenance(reqs, evs, by_id) == []


def test_runner_timeout_isolated_no_fabrication():
    sources = [SourceText("A.pdf", 1, ("The 220kV GIS transformer must be installed ok " * 40))]
    analysis, telem = IR.run_intelligence("T1", sources, router=_stub_router({"chunk-0001-seg-01": "TIMEOUT"}))
    assert telem.timeout_count >= 1
    assert telem.requirements_final == len(analysis["requirements"])


def test_runner_structured_first_reduces_calls():
    table = StructuredTable(
        "sched.xlsx", "Sheet1",
        ["Item", "Description", "Unit", "Quantity"],
        [{"Item": "1A", "Description": "Three phase circuit breakers 220kV GIS",
          "Unit": "Nos.", "Quantity": "6"}], 1)
    text = "Three phase circuit breakers 220kV GIS Nos quantity 6 " * 10
    sources = [SourceText("sched.xlsx", 1, text)]
    analysis, telem = IR.run_intelligence("T1", sources, tables=[table], router=_stub_router())
    assert telem.candidates_structured_covered >= 1
    assert telem.model_call_count < telem.candidates_generated


# ---- concurrency config ----
def test_bounded_workers_c1_c2():
    import concurrent.futures
    from app.pipeline.ai_router import QwenMinimalContractProvider
    w2 = load_worker_config({"TENDERMIND_MAX_AI_WORKERS": "2"})
    assert w2.max_workers == 2
    calls = [_cand(f"c{i}") for i in range(4)]

    def run(level):
        from app.pipeline.ai_router import Router as R
        import app.pipeline.ai_router as AR
        prov = QwenMinimalContractProvider(transport=lambda c: (
            {"summary": "s", "category": "TECHNICAL", "mandatory": None,
             "applicable_entity": None}, "ok", 0.001, "{}"))
        if level == 1:
            return [prov.normalize_requirement(c)[1] for c in calls]
        with concurrent.futures.ThreadPoolExecutor(max_workers=level) as ex:
            return [f[1] for f in ex.map(prov.normalize_requirement, calls)]

    assert run(1) == ["ok"] * 4 and run(2) == ["ok"] * 4


# ---- regression ----
def test_variant_b_unchanged_stage3k_intact():
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
    art = P / "evaluation" / "stage3k" / "comparison_3k.json"
    assert art.exists() and json.loads(art.read_text(encoding="utf-8"))["completed"] == 41


def test_no_tender_specific_rules():
    import app.pipeline.structured_first as SFF
    import app.pipeline.reconciliation_mvp as RCM
    src = Path(SFF.__file__).read_text(encoding="utf-8") + Path(RCM.__file__).read_text(encoding="utf-8")
    for token in ("Mobile", "Motawreen", "Sarai", "October", "FORM D"):
        assert token not in src
