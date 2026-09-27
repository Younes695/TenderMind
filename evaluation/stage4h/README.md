# Stage 4H — Release Candidate Hardening (evaluation/production-flagged)

## Changes (minimal, additive)
- `resolve_coverage()` (jobs.py): COMPLETE iff 0 failed + 0 unsupported; else
  PARTIAL + per-state counts. Terminal-status derivation untouched. Exposed in
  GET job + persisted processing block. UI: coverage line (Processing +
  Coverage + counts).
- Ambiguity aggregation (`ambiguity_groups.py`): same-type + same-doc +
  (exact desc OR near-dup ≥0.9 same-page) merge; cross-doc never merges without
  explicit relationship; every raw signal in exactly one group (asserted);
  no severity, no suppression. Runner stores grouped `ambiguities` + raw +
  report. UI: grouped counts + expandable evidence (neutral wording).
- Filename echo sanitization (routes.py): display name = basename stripped of
  control/HTML-active chars; storage path logic untouched; error echoes use
  safe names. Regression tests added.

## Live evidence
- 4H1 re-run (same fixture): 127/127, same 8 categories, provenance clean,
  no leakage, byte-identical refresh. Ambiguities 78 raw → 3 groups (template-
  identical descriptions merge; raws preserved + expandable).
- Motawreen smoke: 5/5, 0 violations, coverage PARTIAL (JPG unsupported),
  87.9s, no leakage.
- `run_e2e.py` (stage4g, retargeted), `smoke_motawreen.py` here.

## Files
`fresh_tender_release_run.json`, `cross_tender_smoke.json`,
`release_matrix.json` (A–H), `ambiguity_aggregation.json` (in-run reports),
`demo_data_audit.json` (below), `security_recheck.json` (below),
`performance_4h.json` (below).
