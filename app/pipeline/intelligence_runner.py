"""Stage 4F — intelligence runner: lane-by-lane production flow (flag-gated).

UI upload -> inventory -> extraction (caller-supplied) -> structured tables ->
discovery -> compression -> STRUCTURED-FIRST filter -> bounded AI calls ->
validation/provenance -> commercial/schedule -> gaps -> ambiguity ->
reconciliation MVP -> risk signals -> synthesis MVP -> extended result.

Separation preserved: extraction / interpretation / synthesis never collapse
into one call. AI concurrency is bounded (WorkerConfig, default sequential
unless explicitly enabled with max_workers>1).
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

from app.pipeline import ai_router as router_mod
from app.pipeline.ai_router import AITask, Router
from app.pipeline.ambiguity import ambiguity_dicts, analyze_ambiguity
from app.pipeline.candidate_compression import compress_candidates
from app.pipeline.candidate_discovery import discover_from_sources
from app.pipeline.capability_tiers import WorkerConfig, load_worker_config
from app.pipeline.commercial_schedule import (
    CommercialFacts,
    extract_commercial_facts,
    extract_schedule_facts,
    schedule_record_dict,
)
from app.pipeline.config import load_config
from app.pipeline.contracts import (
    AddendumRecord,
    ClarificationRecord,
    CommercialLineItem,
    DocumentArtifact,
    EvidenceLink,
    ProcessingStageResult,
    RequirementCandidate,
    SourceText,
    StructuredTable,
    TenderAnalysisResult,
    ValidatedRequirement,
)
from app.pipeline.gaps import analyze_package_gaps, gap_dicts
from app.pipeline.jobs import JobTelemetry, PipelineStage, pipeline_version_metadata
from app.pipeline.postprocessing import post_process
from app.pipeline.provenance import validate_provenance
from app.pipeline.reconciliation_mvp import (
    find_boq_conflicts,
    group_duplicates,
    link_amendments,
    requirement_lifecycle,
)
from app.pipeline.risk_synthesis import derive_risk_signals, risk_dicts, synthesize
from app.pipeline.structured_data import normalize_boq_table
from app.pipeline.structured_first import structured_first_filter


def collect_structured(tables: List[StructuredTable]) -> Tuple[List[CommercialLineItem], Dict[str, int]]:
    items: List[CommercialLineItem] = []
    for t in tables:
        items.extend(normalize_boq_table(t))
    return items, {"tables": len(tables), "line_items": len(items)}


def _ai_call(router: Router, cand: RequirementCandidate):
    return cand, router.normalize(AITask.REQUIREMENT_NORMALIZATION, cand)


def run_intelligence(
    tender_id: str,
    sources: List[SourceText],
    documents: Optional[List[DocumentArtifact]] = None,
    tables: Optional[List[StructuredTable]] = None,
    addenda: Optional[List[AddendumRecord]] = None,
    clarifications: Optional[List[ClarificationRecord]] = None,
    job_id: str = "",
    router: Optional[Router] = None,
    workers: Optional[WorkerConfig] = None,
    deterministic_extras: Optional[Dict[str, Any]] = None,
    structured_threshold: float = 0.6,
    ai_cache: Optional[Any] = None,
) -> Tuple[Dict[str, Any], JobTelemetry]:
    """Full lane flow. Returns (extended_analysis_dict, telemetry)."""
    t0 = time.time()
    cfg = load_config()
    router = router or router_mod.default_router(timeout_s=cfg.llm_timeout_s)
    workers = workers or WorkerConfig()
    documents = documents or []
    extras = deterministic_extras or {}
    telem = JobTelemetry(job_id=job_id, tender_id=tender_id,
                         model_name=router_mod.active_model_name(),
                         max_workers=workers.max_workers if workers.enabled else 1)
    stages: List[ProcessingStageResult] = []
    candidate_failures: List[Dict[str, str]] = []

    accepted, rejected, dmetrics = discover_from_sources(sources)
    by_id = {c.candidate_id: c for c in accepted}
    telem.candidates_generated = len(accepted)
    telem.candidates_rejected = len(rejected)
    stages.append(ProcessingStageResult(stage="BUILDING_CANDIDATES", status="COMPLETED",
                                        counts={"accepted": len(accepted), "rejected": len(rejected)}))

    ai_queue, creport = compress_candidates(accepted)
    telem.candidates_compressed = creport.metrics.merged_candidates
    stages.append(ProcessingStageResult(stage="COMPRESSING_CANDIDATES", status="COMPLETED",
                                        counts={"raw": creport.metrics.raw_candidates,
                                                "final_ai": creport.metrics.final_ai_candidates}))

    # Structured-first: facts from tables + deterministic extractors.
    line_items, struct_counts = collect_structured(tables or [])
    telem.structured_tables = struct_counts["tables"]
    telem.structured_line_items = struct_counts["line_items"]
    commercial = extract_commercial_facts(sources)
    fact_texts = []
    if commercial.currency:
        fact_texts.append({"kind": "commercial-fact", "text": f"currency {commercial.currency}",
                           "source_document": commercial.currency_source or "", "location": "",
                           "identity": "COMMERCIAL:currency"})
    ai_queue2, sreport = structured_first_filter(ai_queue, line_items, fact_texts,
                                                 threshold=structured_threshold)
    telem.candidates_structured_covered = sreport.covered
    telem.candidates_sent_to_ai = len(ai_queue2)
    stages.append(ProcessingStageResult(stage="STRUCTURED_FIRST", status="COMPLETED",
                                        counts={"before": sreport.before, "covered": sreport.covered,
                                                "sent_to_ai": sreport.sent_to_ai}))

    # Bounded AI calls (sequential default; threads only when explicitly enabled).
    pairs, latencies = [], []
    from app.pipeline.progress import report as _report
    total_ai = len(ai_queue2)
    calls = []
    # Stage 5H: answers saved by an earlier, interrupted run are reused; only the
    # rest go to the model, and every new success is saved as it arrives.
    todo = []
    for c in ai_queue2:
        hit = ai_cache.get(c.source_text) if ai_cache is not None else None
        if hit is not None:
            from app.pipeline.contracts import LLMNormalizationResult
            calls.append((c, (LLMNormalizationResult(**hit), "ok", 0.0, None)))
        else:
            todo.append(c)
    telem.ai_cache_hits = len(calls)
    if calls:
        _report("ai", len(calls), total_ai)

    provider = router.route(AITask.REQUIREMENT_NORMALIZATION) if hasattr(router, "route") else None
    batch_escalation = hasattr(provider, "primary_only") and hasattr(provider, "escalate")
    pending = []  # (index in calls, candidate, primary outcome) awaiting the second model

    def _progress(frac):
        _report("ai", int(1000 * min(frac, 1.0)), 1000)

    def _keep(call):
        cand, (res, status, _lat, _raw) = call
        if batch_escalation and provider.needs_escalation(res, status):
            pending.append((len(calls), cand, (res, status, _lat, _raw)))
        elif ai_cache is not None and status == "ok" and res is not None:
            ai_cache.put(cand.source_text, res)
        calls.append(call)
        # first pass = 85% of the AI bar when a second pass may follow
        _progress((len(calls)) / max(total_ai, 1) * (0.85 if batch_escalation else 1.0))

    first = (lambda c: (c, provider.primary_only(c))) if batch_escalation else (lambda c: _ai_call(router, c))
    # Results are consumed on this thread so the job's progress listener sees them.
    if workers.enabled and workers.max_workers > 1:
        with ThreadPoolExecutor(max_workers=workers.max_workers) as ex:
            for call in ex.map(first, todo):
                _keep(call)
    else:
        for c in todo:
            _keep(first(c))
    # Second pass: only the unsettled candidates, one model load.
    for n, (idx, cand, outcome) in enumerate(pending, 1):
        try:
            final = provider.escalate(cand, *outcome)
        except Exception:
            final = outcome
        calls[idx] = (cand, final)
        res, status = final[0], final[1]
        if ai_cache is not None and status == "ok" and res is not None:
            ai_cache.put(cand.source_text, res)
        _progress(0.85 + 0.15 * n / len(pending))
    _progress(1.0)

    for cand, (result, status, lat, _raw) in calls:
        latencies.append(lat)
        telem.model_call_count += 1
        if status == "ok" and result is not None:
            telem.success_count += 1
            pairs.append((result, cand))
        else:
            telem.failure_count += 1
            if status == "timeout":
                telem.timeout_count += 1
            candidate_failures.append({"candidate_id": cand.candidate_id, "reason": status})
    if latencies:
        ordered = sorted(latencies)
        telem.avg_latency_s = round(sum(ordered) / len(ordered), 2)
        telem.p95_latency_s = round(ordered[int(len(ordered) * 0.95)], 2)
    stages.append(ProcessingStageResult(
        stage="AI_ANALYSIS", status="COMPLETED" if pairs else ("FAILED" if ai_queue2 else "COMPLETED"),
        counts={"calls": telem.model_call_count, "ok": telem.success_count,
                "failed": telem.failure_count}))

    final_reqs, final_evs, val_failures = post_process(pairs) if pairs else ([], [], [])
    for f in val_failures:
        candidate_failures.append({"candidate_id": f.get("candidate_id", "?"),
                                   "reason": f.get("reason", "?")})
    violations = validate_provenance(final_reqs, final_evs, by_id)
    telem.requirements_final = len(final_reqs)
    telem.evidence_final = len(final_evs)
    stages.append(ProcessingStageResult(
        stage="VALIDATING", status="COMPLETED" if not violations else "PARTIAL",
        counts={"requirements": len(final_reqs), "evidence": len(final_evs)},
        errors=[str(v) for v in violations]))

    # Lanes B-E (all deterministic in 4F).
    sched = extract_schedule_facts(sources)
    gaps = analyze_package_gaps(documents, sources)
    ambiguities = analyze_ambiguity(final_reqs)
    # Stage 4H: deterministic aggregation for presentation (raw preserved).
    from app.pipeline.ambiguity_groups import aggregate_ambiguities, group_dicts
    amb_groups, amb_report = aggregate_ambiguities(ambiguities)
    grouped_ambiguities = group_dicts(amb_groups)
    dup_groups = group_duplicates(final_reqs)
    boq_conflicts = find_boq_conflicts(line_items)
    amend_links = link_amendments(final_reqs, addenda or [], clarifications or [])
    lifecycle = requirement_lifecycle(final_reqs, amend_links)
    risks = derive_risk_signals(gaps, ambiguities, boq_conflicts, commercial, final_reqs)
    doc_status = {"total": len(documents),
                  "complete": sum(1 for d in documents if d.status == "COMPLETE"),
                  "partial": sum(1 for d in documents if d.status == "PARTIAL"),
                  "failed": sum(1 for d in documents if d.status == "FAILED"),
                  "unsupported": sum(1 for d in documents if d.status == "UNSUPPORTED")}
    synthesis = synthesize(final_reqs, list(extras.get("deadlines", [])), commercial,
                           gaps, ambiguities, boq_conflicts, risks, doc_status)
    telem.gaps_final = len(gaps)
    telem.ambiguities_final = len(amb_groups)
    telem.conflicts_final = len(boq_conflicts) + len(dup_groups)
    telem.risk_signals_final = len(risks)
    telem.synthesis_status = synthesis["status"]
    telem.total_wall_s = round(time.time() - t0, 2)
    telem.stage_results = [s.stage for s in stages]
    processing = telem.to_dict()
    processing.update(pipeline_version_metadata(router_mod.active_model_name()))
    processing["status"] = extras.get("status", "COMPLETED")

    analysis = {
        "tender_id": tender_id,
        "requirements": [asdict(r) for r in final_reqs],
        "evidence": [asdict(e) for e in final_evs],
        "deadlines": list(extras.get("deadlines", [])),
        "commercial": extras.get("commercial"),
        "risks": list(extras.get("risks", [])),
        "derived_features": dict(extras.get("derived_features", {})),
        "processing": processing,
        "stage_results": [s.stage for s in stages],
        "candidate_failures": candidate_failures,
        # 4F additive sections (UI reads these; absent keys = unavailable, never faked)
        "commercial_facts": {"currency": commercial.currency,
                             "currency_source": commercial.currency_source,
                             "payment_terms": commercial.payment_terms,
                             "payment_source": commercial.payment_source,
                             "bid_security": commercial.bid_security,
                             "bid_security_source": commercial.bid_security_source,
                             "validity": commercial.validity,
                             "validity_source": commercial.validity_source,
                             "amounts": commercial.amounts[:20],
                             "line_items": [asdict(li) for li in line_items]},
        "schedule_facts": [schedule_record_dict(r) for r in sched.records],
        "clarifications": [asdict(c) for c in (clarifications or [])],
        "addenda": [asdict(a) for a in (addenda or [])],
        "gaps": gap_dicts(gaps),
        "ambiguities": grouped_ambiguities,
        "ambiguities_raw": ambiguity_dicts(ambiguities),
        "ambiguity_report": amb_report,
        "conflicts": [{"conflict_id": c.conflict_id, "side_a": c.side_a, "side_b": c.side_b,
                       "reason": c.reason, "evidence": c.evidence,
                       "resolution": c.resolution} for c in boq_conflicts],
        "duplicate_groups": [{"group_id": g.group_id, "requirement_ids": g.requirement_ids,
                              "relation": g.relation, "evidence": g.evidence} for g in dup_groups],
        "amendment_links": [{"requirement_id": l.requirement_id,
                             "amendment_source": l.amendment_source, "status": l.status,
                             "evidence": l.evidence} for l in amend_links],
        "lifecycle": lifecycle,
        "risk_signals": risk_dicts(risks),
        "synthesis": synthesis,
        "structured_coverage": [{"candidate_id": c.candidate_id, "covered_by": c.covered_by,
                                 "kind": c.kind, "overlap": c.overlap,
                                 "source_document": c.source_document, "location": c.location}
                                for c in sreport.coverages],
    }
    return analysis, telem
