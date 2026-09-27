# Stage 4H — Release Candidate Hardening

## Bugs fixed (exact)
1. Filename echo: `original_filename` + 400 error echoes now use display-
   sanitized names (basename, no controls/HTML-active chars, 255 cap);
   storage-path logic untouched. Regression tests added.
2. Coverage semantics (additive): `resolve_coverage()` — COMPLETE iff 0 failed
   + 0 unsupported, else PARTIAL + per-state counts. Terminal derivation
   untouched (divergence documented: jobs.py helper answers PARTIAL where the
   legacy processing chain answers COMPLETED for mixed+unsupported — the
   coverage layer is the honest signal). Exposed in GET job + persisted
   processing block; UI coverage line.
3. Persisted AI budget: intelligence telemetry now merges into
   `derived_features.telemetry` (was in-memory only). Verified live:
   169→38 merged→131 calls (128 ok + 3 isolated failures)→127 finals.

## Ambiguity aggregation (live)
4H2: 78 raw → 4 groups (96%+ reduction; template-identical detector texts
merge; raws + IDs + evidence preserved; cross-doc merges refused with
examples). UI: grouped counts + expandable evidence, neutral wording
("requires clarification/review", no severity).

## Live runs
- 4H1/4H2 re-runs (same fixture): 127/127, same 8 categories, provenance
  254/254, no leakage, byte-identical refresh, 409 preserved. 4H2 ambiguity
  groups 4 vs 4H1 3 (3 isolated AI failures shifted finals — expected bounds).
- Motawreen smoke: new tender, 3 files (incl. empty-OCR JPG → UNSUPPORTED),
  COMPLETED + coverage PARTIAL, 5/5 provenance-clean, 87.9s, no leakage.

## Matrix / audits
Release matrix A–H all PASS (C at unit level). Demo scan: only explicit
no-fake labels. Security recheck: PASS (echo fixed; traversal/cap/rename/
isolation/ORM confirmed; no content in logs).

## Tests
12 backend + 5 frontend new (coverage line, grouped ambiguities, neutral
wording). Suites: backend 357+flake-doc, frontend 46, build green.
