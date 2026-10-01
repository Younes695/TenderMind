"""Stage 4A — flag-gated production two-stage runner.

Runs ONLY when TENDERMIND_TWO_STAGE_LLM=1 (checked by the caller via
config.is_two_stage_enabled()). Flag off -> this module is never invoked and
the legacy path in app/processing.py runs byte-identically.

Flow: SourceTexts -> discovery -> compression -> Router(AI) -> validation ->
provenance check -> TenderAnalysisResult + JobTelemetry. Every stage records
truthful counts; failures are isolated per candidate and listed, never hidden.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from app.pipeline import ai_router as router_mod
from app.pipeline.ai_router import AITask, Router
from app.pipeline.candidate_compression import compress_candidates
from app.pipeline.candidate_discovery import discover_from_sources
from app.pipeline.config import load_config
from app.pipeline.contracts import (
    DocumentArtifact,
    ProcessingStageResult,
    RequirementCandidate,
    SourceText,
    TenderAnalysisResult,
)
from app.pipeline.jobs import (
    JobTelemetry,
    PipelineStage,
    pipeline_version_metadata,
    resolve_terminal_status,
)
from app.pipeline.postprocessing import post_process
from app.pipeline.provenance import validate_provenance


def document_artifacts(extras: Dict[str, Any]) -> List[DocumentArtifact]:
    """The per-document entries of adapt_doc_results as the gap analysis reads them."""
    return [DocumentArtifact(filename=e.get("filename", ""), full_path="", extension="",
                             status=str(e.get("extraction_status", "COMPLETE")),
                             page_count=int(e.get("page_count", 0) or 0),
                             total_text_chars=int(e.get("text_length", 0) or 0),
                             error=e.get("error"), failed_pages=list(e.get("failed_pages") or []))
            for e in extras.get("documents", [])]


def adapt_doc_results(doc_results: Dict[str, Any]) -> Tuple[List[SourceText], Dict[str, Any]]:
    """Adapt production extraction output to runner inputs.

    Returns (sources, extras) where extras carries documents_*, document
    failures and per-document entries for the analysis payload. Only pages
    with text become SourceTexts; FAILED/UNSUPPORTED docs are counted and
    listed, never silently dropped.
    """
    sources: List[SourceText] = []
    doc_entries: List[Dict[str, Any]] = []
    doc_failures: List[Dict[str, str]] = []
    total = processed = failed = unsupported = 0
    for filename in sorted(doc_results.keys()):
        d = doc_results[filename] or {}
        total += 1
        status = str(d.get("status", "COMPLETE")).upper()
        pages = d.get("pages", []) or []
        entry = {"filename": filename,
                 "document_type": "OTHER",
                 "extraction_status": status,
                 "page_count": d.get("page_count", len(pages)),
                 "text_length": d.get("total_text_chars", 0)}
        if d.get("error"):
            entry["error"] = str(d["error"])[:200]
        if d.get("failed_pages"):
            entry["failed_pages"] = list(d["failed_pages"])
        doc_entries.append(entry)
        if status == "UNSUPPORTED":
            unsupported += 1
            doc_failures.append({"filename": filename, "reason": "unsupported"})
            continue
        if status == "FAILED" or not pages:
            failed += 1
            doc_failures.append({"filename": filename,
                                 "reason": str(d.get("error", "extraction_failed"))[:200]})
            continue
        processed += 1
        for pg in pages:
            text = (pg or {}).get("text", "") or ""
            if not text.strip():
                continue
            sources.append(SourceText(
                source_document=filename,
                page_number=int((pg or {}).get("page_number")
                                or (pg or {}).get("source_page_number") or 1),
                text=text,
                method=str((pg or {}).get("method", "")),
                ocr_applied=bool((pg or {}).get("ocr_applied", False))))
    extras = {"documents": doc_entries, "document_failures": doc_failures,
              "documents_total": total, "documents_processed": processed,
              "documents_failed": failed, "documents_unsupported": unsupported}
    return sources, extras


def run_two_stage(
    tender_id: str,
    sources: List[SourceText],
    job_id: str = "",
    router: Optional[Router] = None,
    deterministic_extras: Optional[Dict[str, Any]] = None,
    max_ai_candidates: Optional[int] = None,
) -> Tuple[TenderAnalysisResult, JobTelemetry]:
    """Execute the hardened two-stage pipeline over page-level source texts."""
    t0 = time.time()
    cfg = load_config()
    router = router or router_mod.default_router(timeout_s=cfg.llm_timeout_s)
    extras = deterministic_extras or {}
    telem = JobTelemetry(job_id=job_id, tender_id=tender_id,
                         model_name=router_mod.active_model_name())
    stage_results: List[ProcessingStageResult] = []
    candidate_failures: List[Dict[str, str]] = []

    # BUILDING_CANDIDATES (deterministic)
    accepted, rejected, dmetrics = discover_from_sources(sources)
    telem.candidates_generated = len(accepted)
    telem.candidates_rejected = len(rejected)
    by_id = {c.candidate_id: c for c in accepted}
    stage_results.append(ProcessingStageResult(
        stage=PipelineStage.BUILDING_CANDIDATES.value, status="COMPLETED",
        counts={"parents": dmetrics.parents, "accepted": len(accepted),
                "rejected": len(rejected), "skipped_tiny": dmetrics.skipped_tiny}))

    # COMPRESSING_CANDIDATES (deterministic)
    ai_queue, creport = compress_candidates(accepted, max_ai_candidates=max_ai_candidates)
    telem.candidates_compressed = creport.metrics.merged_candidates
    telem.candidates_sent_to_ai = len(ai_queue)
    telem.compression_pct = creport.metrics.reduction_pct
    stage_results.append(ProcessingStageResult(
        stage=PipelineStage.COMPRESSING_CANDIDATES.value, status="COMPLETED",
        counts={"raw": creport.metrics.raw_candidates,
                "exact_dup": creport.metrics.exact_duplicates,
                "normalized_dup": creport.metrics.normalized_duplicates,
                "near_dup": creport.metrics.near_duplicates,
                "final_ai": creport.metrics.final_ai_candidates}))

    # AI_ANALYSIS (one call per queued candidate; failures isolated)
    pairs = []
    latencies: List[float] = []
    for cand in ai_queue:
        result, status, lat, _raw = router.normalize(AITask.REQUIREMENT_NORMALIZATION, cand)
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
    ai_status = ("COMPLETED" if not candidate_failures else
                 "PARTIAL" if pairs else "FAILED")
    stage_results.append(ProcessingStageResult(
        stage=PipelineStage.AI_ANALYSIS.value, status=ai_status,
        counts={"calls": telem.model_call_count, "ok": telem.success_count,
                "failed": telem.failure_count, "timeouts": telem.timeout_count}))

    # VALIDATING (deterministic)
    final_reqs, final_evs, val_failures = post_process(pairs) if pairs else ([], [], [])
    for f in val_failures:
        candidate_failures.append({"candidate_id": f.get("candidate_id", "?"),
                                   "reason": f.get("reason", "?")})
    violations = validate_provenance(final_reqs, final_evs, by_id)
    telem.requirements_final = len(final_reqs)
    telem.evidence_final = len(final_evs)
    val_status = "COMPLETED" if not violations and (final_reqs or not pairs) else "PARTIAL"
    stage_results.append(ProcessingStageResult(
        stage=PipelineStage.VALIDATING.value, status=val_status,
        counts={"requirements": len(final_reqs), "evidence": len(final_evs)},
        errors=[str(v) for v in violations]))

    # FINALIZING
    doc_failures = list(extras.get("document_failures", []))
    status = resolve_terminal_status(
        documents_total=int(extras.get("documents_total", 0)),
        documents_processed=int(extras.get("documents_processed", 0)),
        documents_failed=int(extras.get("documents_failed", 0)),
        documents_unsupported=int(extras.get("documents_unsupported", 0)),
        requirements_final=len(final_reqs))
    if violations:
        status = "PARTIAL" if status == "COMPLETED" else status
    telem.total_wall_s = round(time.time() - t0, 2)
    telem.stage_results = [s.stage for s in stage_results]
    processing = telem.to_dict()
    processing.update(pipeline_version_metadata(router_mod.active_model_name()))
    processing.update({"status": status, "job_id": job_id})
    stage_results.append(ProcessingStageResult(
        stage=PipelineStage.FINALIZING.value, status=status, counts={"requirements": len(final_reqs)}))

    result = TenderAnalysisResult(
        tender_id=tender_id, status=status,
        documents=list(extras.get("documents", [])),
        requirements=final_reqs, evidence=final_evs,
        deadlines=list(extras.get("deadlines", [])),
        commercial=extras.get("commercial"),
        risks=list(extras.get("risks", [])),
        derived_features=dict(extras.get("derived_features", {})),
        processing=processing, stage_results=stage_results,
        document_failures=doc_failures, candidate_failures=candidate_failures)
    return result, telem
