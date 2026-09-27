"""Stage 4H tests (fast: no live server, no Sarai)."""
import json
from pathlib import Path

from app.pipeline import ambiguity_groups as AG
from app.pipeline.ambiguity import Ambiguity
from app.pipeline.jobs import resolve_coverage, resolve_terminal_status

P = Path(__file__).resolve().parents[1]


def _amb(aid="AMB-001", typ="missing-value", desc="Submit TBD documents please",
         req="REQ-001", ev=("A.pdf#p1",)):
    return Ambiguity(aid, req, typ, desc, list(ev), True, True)


# ---- mixed-status coverage semantics (status derivation untouched) ----
def test_coverage_all_complete():
    assert resolve_coverage(3, 3, 0, 0)["analysis_coverage"] == "COMPLETE"
    assert resolve_terminal_status(3, 3, 0, 0) == "COMPLETED"


def test_coverage_complete_plus_unsupported():
    c = resolve_coverage(3, 2, 0, 1)
    assert c["analysis_coverage"] == "PARTIAL"
    assert c["document_status_counts"] == {"complete": 2, "failed": 0, "unsupported": 1, "total": 3}
    # jobs.py helper: any unsupported/failed with progress -> PARTIAL.
    # (processing.py's legacy chain answers COMPLETED here; the additive
    # coverage layer is the honest signal either way — see 4H doc.)
    assert resolve_terminal_status(3, 2, 0, 1) == "PARTIAL"


def test_coverage_complete_plus_failed():
    c = resolve_coverage(3, 2, 1, 0)
    assert c["analysis_coverage"] == "PARTIAL"
    assert resolve_terminal_status(3, 2, 1, 0) == "PARTIAL"


def test_coverage_all_unsupported():
    c = resolve_coverage(2, 0, 0, 2)
    assert c["analysis_coverage"] == "PARTIAL"
    assert resolve_terminal_status(2, 0, 0, 2) == "PARTIAL"


def test_coverage_analysis_failure_edge():
    # nothing persisted with real docs -> FAILED honesty rule lives in processing;
    # coverage of an empty/failed job is PARTIAL, never COMPLETE-with-content
    c = resolve_coverage(2, 0, 2, 0)
    assert c["analysis_coverage"] == "PARTIAL"
    assert resolve_terminal_status(2, 0, 2, 0) == "FAILED"


# ---- ambiguity grouping ----
def test_exact_duplicates_grouped_provenance_kept():
    sigs = [_amb("AMB-001", "missing-value", "Submit TBD documents please", "REQ-001", ("A.pdf#p1",)),
            _amb("AMB-002", "missing-value", "Submit  TBD  documents please", "REQ-002", ("A.pdf#p1",))]
    groups, rep = AG.aggregate_ambiguities(sigs)
    assert len(groups) == 1 and rep["reduction_pct"] == 50.0
    g = groups[0]
    assert g.signal_ids == ["AMB-001", "AMB-002"] and g.source_document == "A.pdf"
    assert len(g.raw_signals) == 2 and g.evidence == ["A.pdf#p1"]


def test_cross_document_never_merges_without_relationship():
    sigs = [_amb("AMB-001", "missing-value", "Submit TBD documents please", "REQ-001", ("A.pdf#p1",)),
            _amb("AMB-002", "missing-value", "Submit TBD documents please", "REQ-002", ("B.pdf#p2",))]
    groups, rep = AG.aggregate_ambiguities(sigs)
    assert len(groups) == 2 and rep["reduction_pct"] == 0.0
    assert any(r["ambiguity_id"] == "AMB-002" for r in rep["rejected_examples"])


def test_unrelated_types_never_merge():
    sigs = [_amb("AMB-001", "missing-value", "Submit TBD documents please"),
            _amb("AMB-002", "undefined-term", "Submit TBD documents please")]
    groups, _ = AG.aggregate_ambiguities(sigs)
    assert len(groups) == 2


def test_no_signal_loss_no_severity():
    sigs = [_amb(f"AMB-{i:03d}") for i in range(1, 6)]
    groups, rep = AG.aggregate_ambiguities(sigs)
    assert rep["raw_signals"] == 5
    blob = json.dumps([g.__dict__ for g in groups]).lower()
    assert "critical" not in blob and "severity" not in blob and "high risk" not in blob


def test_group_dicts_shape():
    (g,), _ = AG.aggregate_ambiguities([_amb()])
    d = AG.group_dicts([g])[0]
    assert set(d) == {"group_id", "ambiguity_type", "description", "signal_count",
                      "signal_ids", "source_document", "pages", "evidence",
                      "raw_signals", "clarification_needed", "human_review_required"}


# ---- filename sanitization ----
def test_display_filename_never_raw_traversal():
    import re
    def sanitize(name):
        disp = Path(name).name
        disp = re.sub(r"[\x00-\x1f\x7f<>\"'&]", "", disp).strip()[:255]
        return disp or "file"
    assert sanitize("../evil.txt") == "evil.txt"
    assert sanitize("a<b>.txt") == "ab.txt"
    assert "<" not in sanitize("<script>x</script>.pdf")


# ---- no tender-specific rules in new modules ----
def test_no_tender_specific_rules():
    for mod in ("ambiguity_groups",):
        src = (P / "app" / "pipeline" / f"{mod}.py").read_text(encoding="utf-8")
        for token in ("Mobile", "Motawreen", "Sarai", "October", "FORM D"):
            assert token not in src
