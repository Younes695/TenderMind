# Stage 4G — Production-Capable Pilot + Fresh-Tender Validation

Live-server E2E on a fresh 6th October tender (Clarification 1.pdf + Power
Transformer Specs.pdf + Addendum.zip), isolated DB/storage, flag ON, real qwen.

## Flow
`run_e2e.py`: create → upload ×3 → process → duplicate-POST probe (409) →
poll → analysis → re-get (persistence) → validate sections/provenance/leakage/
budget. Server: `uvicorn app.main:app` (env: DATABASE_URL, STORAGE_ROOT, FLAG).

## Files
`fresh_tender_manifest.json` (sources+hashes), `fresh_tender_e2e.json` (full
record), `ai_call_budget.json`, `stage_timings.json`, `provenance_validation.json`,
`structured_validation.json` (honest XLSX absence), `security_audit.json`,
`release_check.json`, `comparison_4g.json`.

## Headline (4G3 run)
127 reqs / 127 evidence, provenance 254/254 valid, 8 categories, gaps 4,
ambiguities 78, risks 3, synthesis true, terminal COMPLETED (2 docs +
1 unsupported-zip, all listed), duplicate POST → 409, re-GET byte-identical,
zero fixture leakage. Two live bugs found + fixed during the pilot:
schema-enum rejection of `two-stage` method; COMPLETED-without-analysis
honesty rule (now FAILED). See `docs/STAGE_4G_PRODUCTION_PILOT_VALIDATION.md`.
