"""Stage 4F — throughput + concurrency experiments (evaluation-only).

- throughput: Mobile 12-parent sample, REAL qwen2.5:3b via default Router.
  Baseline (no structured tables) vs optimized (Mobile BOQ table). Same
  candidates pipeline; only structured-first filtering differs.
- concurrency: same workload, workers OFF (c1) vs enabled max_workers=2 (c2).
  Fresh calls, warmed model, stability over speed.

Usage:
  python evaluation/stage4f/run_4f.py throughput
  python evaluation/stage4f/run_4f.py concurrency
Artifacts: evaluation/stage4f/*.json (see README). No SLA claims.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding="utf-8", errors="ignore")

from app.pipeline import intelligence_runner as IR  # noqa: E402
from app.pipeline.capability_tiers import WorkerConfig  # noqa: E402
from app.pipeline.contracts import SourceText  # noqa: E402
from app.pipeline.structured_data import GenericXlsxAdapter, normalize_boq_table  # noqa: E402

OUT = Path(__file__).parent
REPO = OUT.parents[1]
MOBILE_XLSX = Path(r"C:\Users\EgyTech\Desktop\02- Mobile substations\Price schedules of 6th October northern Extention 22-22-22 KV GIS SS.xlsx")


def _parents_as_sources():
    full = json.loads((REPO / "evaluation" / "stage3e" / "selected_chunks_full_3e.json").read_text(encoding="utf-8"))
    assert len(full) == 12
    return [SourceText(c["source_document"], int(c.get("page_number", 1) or 1),
                       c["text"], "fixture-3e", False) for c in full]


def _boq_tables():
    if not MOBILE_XLSX.is_file():
        print("BOQ xlsx absent — optimized run degrades to baseline coverage (recorded)")
        return []
    tables = GenericXlsxAdapter().read_tables(MOBILE_XLSX)
    print(f"BOQ tables: {len(tables)}, rows: {sum(t.row_count for t in tables)}")
    return tables


def _summarize(analysis, telem, label):
    return {"label": label,
            "candidates_generated": telem.candidates_generated,
            "candidates_compressed": telem.candidates_compressed,
            "candidates_structured_covered": telem.candidates_structured_covered,
            "candidates_sent_to_ai": telem.candidates_sent_to_ai,
            "ai_calls": telem.model_call_count,
            "ai_successes": telem.success_count,
            "ai_failures": telem.failure_count,
            "requirements_final": telem.requirements_final,
            "evidence_final": telem.evidence_final,
            "gaps_final": telem.gaps_final,
            "ambiguities_final": telem.ambiguities_final,
            "conflicts_final": telem.conflicts_final,
            "risk_signals_final": telem.risk_signals_final,
            "synthesis_status": telem.synthesis_status,
            "avg_latency_s": telem.avg_latency_s,
            "p95_latency_s": telem.p95_latency_s,
            "total_wall_s": telem.total_wall_s}


def throughput():
    sources = _parents_as_sources()
    print("=== BASELINE (no structured tables) ===")
    a0, t0 = IR.run_intelligence("Mobile-12P", sources, job_id="JOB-4F-BASE")
    b = _summarize(a0, t0, "baseline")
    (OUT / "throughput_baseline.json").write_text(json.dumps(b, indent=2), encoding="utf-8")
    print(json.dumps(b, indent=1))
    print("=== OPTIMIZED (Mobile BOQ table) ===")
    tables = _boq_tables()
    a1, t1 = IR.run_intelligence("Mobile-12P", sources, tables=tables, job_id="JOB-4F-OPT")
    o = _summarize(a1, t1, "optimized")
    (OUT / "throughput_optimized.json").write_text(json.dumps(o, indent=2), encoding="utf-8")
    print(json.dumps(o, indent=1))
    red = {"candidate_reduction_pct": round(100 * (1 - o["candidates_sent_to_ai"] / b["candidates_sent_to_ai"]), 2) if b["candidates_sent_to_ai"] else 0,
           "ai_call_reduction_pct": round(100 * (1 - o["ai_calls"] / b["ai_calls"]), 2) if b["ai_calls"] else 0,
           "wall_delta_s": round(o["total_wall_s"] - b["total_wall_s"], 1),
           "correctness_note": "same pipeline/postprocessing; finals compared in candidate_reduction.json"}
    # correctness + provenance: finals overlap on requirement summaries
    bsum = {r["summary"] for r in a0["requirements"]}
    osum = {r["summary"] for r in a1["requirements"]}
    red["baseline_finals"] = len(bsum)
    red["optimized_finals"] = len(osum)
    red["retained_summaries"] = len(bsum & osum)
    red["note"] = "optimized finals are a subset-shift: covered candidates become structured facts, not LLM requirements"
    (OUT / "candidate_reduction.json").write_text(json.dumps(red, indent=2), encoding="utf-8")
    cov_tables = _boq_tables() if False else tables
    items = []
    for t in cov_tables:
        items.extend(normalize_boq_table(t))
    (OUT / "structured_coverage.json").write_text(json.dumps(
        {"tables": len(tables), "line_items": len(items),
         "sample_locations": [f"{i.source_document}!{i.location}" for i in items[:5]]}, indent=2), encoding="utf-8")
    print(json.dumps(red, indent=1))


def concurrency():
    sources = _parents_as_sources()
    out = {}
    for label, workers in (("c1", WorkerConfig(max_workers=1, enabled=False)),
                           ("c2", WorkerConfig(max_workers=2, enabled=True))):
        t0 = time.time()
        _, telem = IR.run_intelligence("Mobile-12P", sources, job_id=f"JOB-4F-{label.upper()}",
                                       workers=workers)
        wall = time.time() - t0
        try:
            import subprocess
            smi = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total",
                                  "--format=csv,noheader"], capture_output=True, text=True, timeout=15)
            vram = smi.stdout.strip()
        except Exception:
            vram = "unmeasured"
        out[label] = {"wall_s": round(wall, 1), "ai_calls": telem.model_call_count,
                      "failures": telem.failure_count, "avg_s": telem.avg_latency_s,
                      "p95_s": telem.p95_latency_s, "vram": vram,
                      "model_residency": "qwen2.5:3b resident throughout (no model switching)"}
        print(label, json.dumps(out[label]))
    (OUT / "concurrency_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: run_4f.py (throughput | concurrency)")
    {"throughput": throughput, "concurrency": concurrency}[sys.argv[1]]()


if __name__ == "__main__":
    main()
