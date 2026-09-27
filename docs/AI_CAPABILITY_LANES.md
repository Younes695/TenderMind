# TenderMind — AI Capability Lanes (Stage 4E)

Lanes are task groupings with stable contracts — NOT models (§6 below).
Code: `app/pipeline/capability_tiers.py` (`LANES`, `lane_manifest()`).
File mirror: `evaluation/stage4e/lane_manifest.json` (exact key match enforced by test).

## LANE A — Requirement Intelligence
In `SourceText[]` → discovery + compression → `normalize_requirement` (Router,
FAST_LOCAL, minimal-1) → deterministic validation/provenance → out
`ValidatedRequirement[] + EvidenceLink[]`. Failures: candidate-level statuses,
PARTIAL, never fabricate. Parallel: per-candidate bounded workers.

## LANE B — Commercial & Schedule
In `StructuredTable[] + SourceText[]` → BOQ normalizer + deadline/currency/
payment patterns → ambiguous clauses to CLAUSE_INTERPRETATION
(NOT_CONFIGURED) → out `CommercialLineItem[] + ScheduleRecord[] + dicts`.
Failures: unparseable rows listed, never guessed. Parallel: per-row/candidate.

## LANE C — Compliance / Gap / Ambiguity
In requirements + inventory → gap counts, UNKNOWN quarantine, failure lists →
AMBIGUITY_ANALYSIS (NOT_CONFIGURED) → out `GapSummary` + flags (4F). Counts
always truthful; interpretive flags only from configured backends. No workers
needed (trivial cost).

## LANE D — Cross-Document Reconciliation
In `ReconciliationInput` → textual dedup (done), addenda as ordinary sources →
RECONCILIATION (NOT_CONFIGURED) → out `ReconciliationResult`. No fake
reconciliation; NOT_CONFIGURED surfaced. Future pairwise workers with O(n²) guard.

## LANE E — Synthesis / Management
In `TenderAnalysisResult` → deterministic slots (mandatory lists, gaps, counts)
→ SYNTHESIS (NOT_CONFIGURED) → out cited summary pack (4F). **NEVER auto
BID/NO-BID** — hard ban preserved in contract text and tests. Single call per
tender; every claim cites artifact IDs.

## §6 — lanes are not models
One model may serve many lanes; one lane may use several tiers over time.
Assignment is by (task capability, observable quality, operational constraints):
`CAPABILITY_TIERS` maps capability → reasoning level → abstract tier →
fallback → volume. Tiers resolve to concrete names via env
(`TENDERMIND_TIER_{FAST,STRONG,API}_MODEL`; FAST defaults to production
default, others UNASSIGNED). No model literal appears in lane logic (tested).
