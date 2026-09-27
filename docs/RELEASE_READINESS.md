# Release Readiness (post-4H: RELEASE CANDIDATE)

## Status: RELEASE CANDIDATE (flag-gated pilot)
4H closed the 4G observations: filename echo sanitized; coverage semantics
explicit and persisted; AI budget persisted per job; ambiguity 78→4 grouped
with provenance; Motawreen cross-tender smoke passed. Two consecutive
identical-fixture runs reproduce within expected bounds.
The flag-on path processes a fresh tender end-to-end with truthful states,
valid provenance, observable budgets, and persisted recoverable results.
The flag-off default path is byte-identical to before. Production default
model qwen2.5:3b; no auto-escalation; no new models; engine/UI semantics kept.

## Verified (acceptance 1–26 + 4H matrix A–H)
Fresh create/upload/process/persist/refresh ✓ (two consecutive runs); 127
reqs + 127 evidence, 254/254 provenance ✓; structured BOQ path ✓; commercial/
schedule facts ✓; gaps + grouped ambiguities ✓; clarification lifecycle ✓;
risks non-scored ✓; synthesis grounded ✓; no fake stats (audit) ✓;
PARTIAL/UNSUPPORTED + coverage truthful ✓; budget persisted (169→38→131→127)
✓; workers=2 configurable ✓; APIs compatible ✓; security recheck ✓; suites
green (backend 370, frontend 46) ✓; E2E + Motawreen smoke ✓; zero
leakage ✓.

## Classified items
READY: creation/upload/processing/persistence/refresh, provenance/evidence,
structured generic path, commercial/schedule deterministic, gaps, grouped
ambiguities, reconciliation MVP, non-scored risks, grounded synthesis, budget
observability, security basics, API stability.
READY-WITH-LIMITATIONS: ambiguity volume on fragments (grouped, honest);
mixed COMPLETED+unsupported (coverage PARTIAL is the signal; status-rule
refinement deferred, not a bug); single-session concurrency evidence; no
durable queue; no escalation/calibration/advanced reasoning/synthesis; no
RBAC; no full-load SLA; CAD/archive unsupported (explicit).
BLOCKED: none for flag-gated pilot scope.

## Post-pilot (explicitly NOT built)
Redis/Celery, K8s, multi-node inference, auth/RBAC, calibration, advanced
routing/reconciliation/risk/synthesis, Gemini, model enablement decision,
status-rule refinement, echo sanitization, concurrency soak, full-tender SLA.
