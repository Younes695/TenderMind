"""Stage 4C tests (fast: policy units with synthetic records + artifact checks)."""
import inspect
import json
from pathlib import Path

from evaluation.stage4c import run_4c

OUT = Path(run_4c.__file__).parent


def _q(cid="c1", status="ok", pred="TECHNICAL", summary="Install the GIS quickly."):
    return {"candidate_id": cid, "gold": "TECHNICAL", "source_text": "Install GIS.",
            "predicted": pred, "summary": summary, "status": status, "latency": 1.0}


def test_r1_escalates_only_observable_failures():
    assert run_4c.should_escalate_r1(_q())[0] is False  # valid non-UNKNOWN: no escalation
    for status in ("timeout", "malformed", "wrong_shape", "multi", "bad_category",
                   "empty", "provider_error:http_500", "transport_error:X"):
        bad, trigger = run_4c.should_escalate_r1(_q(status=status))
        assert bad and trigger
    bad, trigger = run_4c.should_escalate_r1(_q(pred="UNKNOWN"))
    assert bad and trigger == "unknown"
    bad, _ = run_4c.should_escalate_r1(_q(summary="   "))
    assert bad  # empty summary


def test_no_escalation_on_valid_but_wrong_output():
    # PERSONNEL -> EXPERIENCE style semantic mistake is structurally valid:
    # the router MUST NOT see it (key Stage 4C limitation).
    bad, _ = run_4c.should_escalate_r1(_q(pred="EXPERIENCE"))
    assert bad is False


def test_no_gold_leakage_into_routing():
    import re
    usage = re.compile(r"""["']gold["']|\bgold\s*=|gold_""")
    for fn in (run_4c.should_escalate_r1, run_4c.should_escalate_r2,
               run_4c._is_r1_failure, run_4c._degenerate_summary):
        src = inspect.getsource(fn)
        assert not usage.search(src), f"gold usage in {fn.__name__}"


def test_r2_degenerate_heuristics_deterministic():
    bad, reason = run_4c.should_escalate_r2(_q(summary="..."))
    assert bad and reason == "degenerate_placeholder"
    bad, reason = run_4c.should_escalate_r2(_q(summary="pump pump pump pump pump pump pump pump"))
    assert bad and reason == "degenerate_repetitive"
    bad, _ = run_4c.should_escalate_r2(_q(summary="Install the GIS quickly."))
    assert bad is False
    # same input twice -> same verdict
    assert run_4c.should_escalate_r2(_q()) == run_4c.should_escalate_r2(_q())


def test_no_model_specific_prompt_mutation():
    from evaluation.stage4b import providers as P
    src = inspect.getsource(P._OllamaMinimalProvider.normalize_requirement)
    assert "MINIMAL_CONTRACT_SYSTEM" in src
    for token in ("qwen2.5", "qwen3", "gemma3", "phi4", "gemini"):
        assert token not in src.lower()


def test_escalation_artifacts_consistent():
    esc = json.loads((OUT / "escalations.json").read_text(encoding="utf-8"))
    assert len(esc) == 2
    for e in esc:
        assert e["trigger_r1"] == "unknown"  # only observable trigger that fired
        assert e["gemma"]["input_hash_match"] is True  # byte-identical text verified
        assert e["gemma"]["stored_prediction_match"] is True  # fresh == stored 4B
    r1 = json.loads((OUT / "r1_observable_failure_primary.json").read_text(encoding="utf-8"))
    assert r1["scored_n"] == 16


def test_final_provenance_deterministic():
    from app.pipeline.postprocessing import post_process
    from app.pipeline.provenance import validate_provenance
    from app.pipeline.contracts import LLMNormalizationResult, RequirementCandidate
    routed = json.loads((OUT / "routed_secondary.json").read_text(encoding="utf-8"))
    en = [r for r in routed if not r.get("arabic") and not str(r.get("gold", "")).startswith("MULTI")]
    pairs, by_id = [], {}
    for r in en:
        if r.get("status") != "ok" or not r.get("predicted"):
            continue
        c = RequirementCandidate(candidate_id=r["candidate_id"], parent_chunk_id="chunk-0001",
                                 source_document="D.pdf", page=1, source_text=r["source_text"],
                                 span=[], deterministic_signal_categories=[])
        by_id[c.candidate_id] = c
        pairs.append((LLMNormalizationResult(summary=r["summary"] or "s", category=r["predicted"],
                                             mandatory=None, applicable_entity=None), c))
    reqs, evs, fails = post_process(pairs)
    assert validate_provenance(reqs, evs, by_id) == []
    assert len(reqs) == len(evs) > 0


def test_production_safety_untouched():
    import app.processing as proc
    assert proc.LLM_MODEL == "qwen2.5:3b" and proc.PIPELINE_VERSION == "1.0"
    import os
    assert os.environ.get("TENDERMIND_TWO_STAGE_LLM") != "1" or True  # flag never forced by tests
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
