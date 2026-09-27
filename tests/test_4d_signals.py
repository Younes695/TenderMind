"""Stage 4D tests (fast: signal units on synthetic rows + artifact checks)."""
import inspect
import json
import re
from pathlib import Path

from evaluation.stage4d import run_4d

OUT = Path(run_4d.__file__).parent


def _r(pred="TECHNICAL", gold="TECHNICAL", status="ok", summary="Install the GIS transformer.",
       latency=5.0, source="Install the GIS transformer."):
    return {"candidate_id": "c1", "gold": gold, "source_text": source, "predicted": pred,
            "summary": summary, "status": status, "latency": latency}


def test_every_signal_gold_free_and_deterministic():
    usage = re.compile(r"""["']gold["']|\bgold\s*=|gold_""")
    for name, fn in run_4d.SIGNALS.items():
        assert not usage.search(inspect.getsource(fn)), name
    ctx = {"signals": ["TECHNICAL"], "median_len": 60, "p95": 90.0, "source_text": "Install GIS."}
    for name, fn in run_4d.SIGNALS.items():
        assert fn(_r(), ctx) == fn(_r(), ctx), name  # deterministic


def test_signal_behaviors():
    ctx = {"signals": ["TECHNICAL"], "median_len": 60, "p95": 90.0, "source_text": "Install GIS."}
    assert run_4d.sig_unknown(_r(pred="UNKNOWN")) is True
    assert run_4d.sig_invalid(_r(status="bad_category")) is True
    assert run_4d.sig_invalid(_r()) is False
    assert run_4d.sig_signal_mismatch(_r(pred="EXPERIENCE"), ["TECHNICAL"]) is True
    assert run_4d.sig_signal_mismatch(_r(), ["TECHNICAL"]) is False
    assert run_4d.sig_summary_keyword_mismatch(
        _r(pred="TECHNICAL", summary="Require five years experience with similar projects.")) is True
    assert run_4d.sig_verbatim_copy(_r(summary="Install GIS.", ), "Install GIS.") is True
    assert run_4d.sig_slow(_r(latency=100.0), 90.0) is True


def test_no_gold_leakage_in_r3_gate_path():
    import evaluation.stage4c.run_4c as run_4c
    usage = re.compile(r"""["']gold["']|\bgold\s*=|gold_""")
    assert not usage.search(inspect.getsource(run_4c.should_escalate_r1))


def test_self_consistency_recorded():
    sc = json.loads((OUT / "self_consistency.json").read_text(encoding="utf-8"))
    assert len(sc) == 16
    assert all(set(r) >= {"candidate_id", "gold", "c1", "c2"} for r in sc)


def test_concurrency_safety_evidence():
    c = json.loads((OUT / "concurrency_results.json").read_text(encoding="utf-8"))
    assert set(c["levels"]) >= {"1", "2", "4"}
    for lvl, v in c["levels"].items():
        assert v["errors"] == 0, lvl
    assert c["levels"]["2"]["wall_s"] < c["levels"]["1"]["wall_s"]


def test_harder_gold_provenance_and_size():
    g = json.loads((OUT / "harder_gold.json").read_text(encoding="utf-8"))
    assert len(g) == 22
    assert all("gold_provenance" in r and "gold_confidence" in r for r in g)
    scored = [r for r in g if r["category_gold"] != "AMBIGUOUS"]
    assert len(scored) == 21
    m = json.loads((OUT / "harder_tender_manifest.json").read_text(encoding="utf-8"))
    assert m["scored"] == 21 and "6th October" in m["tender"]


def test_no_production_policy_enabled():
    import app.processing as proc
    assert proc.LLM_MODEL == "qwen2.5:3b" and proc.PIPELINE_VERSION == "1.0"
    import os
    assert "auto" not in str(getattr(proc, "ROUTER_POLICY", "off")).lower()
    from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT, prompt_hash
    assert prompt_hash(LLM_SYSTEM_PROMPT) == "9aa3e11254f672cd"
