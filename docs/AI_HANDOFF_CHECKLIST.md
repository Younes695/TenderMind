# AI Handoff Checklist — TenderMind

## AI Core

- [x] Generic ingestion — `evaluation/generic_extraction.py:12` `ingest_tender(tender_path, tender_id=None)` dynamic `tender_id`, never `SA-2018-HV2` hardcoded
- [x] Generic extraction — `evaluation/generic_extraction.py:97` `extract_requirements_generic()` dynamic `REQ-001` (10 patterns, not 21 fixed), `mandatory=None` when unknown, `applicable_entity=None` when unknown
- [x] Semantic extraction — `evaluation/llm_generic_extraction.py` `qwen2.5:3b` `Variant B` chunk-aware `3000` chars, `candidate_id` → canonical `REQ-001` via `assign_canonical_ids()`, evidence follows canonical map
- [x] Validation — `validate_against_schema()` real `jsonschema` + fallback, checks `required`, `types`, `enums`, `pattern`, `confidence 0-1`, `provenance` (source_document+page_number+chunk_id)
- [x] Provenance — every `requirement`/`evidence` retains `source_document`, `page_number`, `source_chunk_id`, `source_text` exact substring, never fabricated
- [x] Canonicalization — `REQ-001` deterministic `source_document, page_number, summary` sorted, `evidence` references `canonical_map[requirement_candidate_id]`, orphan rejected, `candidate_id` preserved as `_candidate_id`
- [x] Evidence linkage — `requirement_id` must point to existing canonical `REQ-*`, never array position, `unknown candidate` rejected
- [x] Retry/failure recovery — `initial + one retry` for `TIMEOUT/CONNECTION/EMPTY/MALFORMED/HTTP 5xx`, not for `SCHEMA_INVALID`/`HTTP 4xx`, per-chunk isolation (100 chunks 3 failed → 97 successful), `zero predictions` for failed chunk (not `no requirements`), `deterministic` (`220kV`) survives LLM failure
- [x] Partial analysis — `PARTIAL` when some documents `FAILED`/`UNSUPPORTED` but usable analysis exists (e.g., 9 docs 8 complete 1 unsupported `DWG` → `PARTIAL`, not `FAILED`)

## Backend

- [ ] Durable worker required — `app/processing.py` uses `BackgroundTasks` in-process, `QUEUED` jobs lost on restart — **REQUIRED**
- [ ] Production persistence required — `TenderAnalysis` `SQLite` `tendermind.db` `tender_analyses` table exists, but `ProcessingJob` is in-memory `SessionLocal` — needs `Postgres` + `S3` for tender files (currently `C:\Users\EgyTech\Desktop\01- Sarai...` local)
- [ ] API hardening required — `POST /tenders/{id}/process` `409` on active, `GET /processing-jobs/{job_id}` exists, but needs auth, rate limiting, `GET /analysis` currently returns `404` if no job
- [ ] Auth required — `app/api/routes.py` has no `Depends` auth — **REQUIRED**
- [ ] Monitoring required — `ProcessingJob` exposes `current_stage`, `progress`, `last_error`, `documents_failed`, but no `Prometheus`/`Sentry` — **REQUIRED**
- [ ] Deployment configuration required — `uvicorn` `app.main:app` local, no `Docker`/`env` config for `OLLAMA_BASE_URL` — **REQUIRED**

## Frontend

- [ ] Processing state UI — `QUEUED → PROCESSING → COMPLETED/PARTIAL/FAILED` with `progress` polling every 2s — **PROPOSED** (can mock with `sarai_gold_dataset.json`)
- [ ] Partial state UI — `PARTIAL` banner `8/9 complete, 1 unsupported` — **PROPOSED**
- [ ] Requirement list — `GET /tenders/{id}/analysis` `requirements` 21 `REQ-A..U` — **EXISTING** via `GET /requirements` but not yet via `GET /analysis` canonical
- [ ] Evidence/source display — `evidence` with `fact` + `source_document` + `page_number` — **EXISTING** (`GET /evidence` 4)
- [ ] Provenance display — `source_chunk_id` + `source_text` `quote_en` + `bbox` (if available) — **PARTIAL** (`source_spans` in schema but not in API)
- [ ] Deadline display — `deadlines` `unknown` type — **PROPOSED**
- [ ] Risk display — `risks` `severity null` — **PROPOSED**
- [ ] Processing status display — `GET /processing-jobs/{job_id}` `progress` — **PROPOSED**

Do not mark production backend/frontend items complete unless they actually exist in the repository.
