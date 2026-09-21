# Production Processing Pipeline — TenderMind

**Version:** `PIPELINE_VERSION 1.0` — `LLM_MODEL qwen2.5:3b` — `PROMPT_VERSION Variant B` — `2026-09-18`

## Architecture

```
POST /tenders/{id}/process
        |
        v
   ProcessingJob (QUEUED)
        |
        v
 document inventory (file_inventory, 64/9/5/11 files)
        |
        v
 text / OCR extraction (fitz + Tesseract 5.4.0 ara+eng + LibreOffice 26.8.0.3)
        |
        v
 document classification (BOQ, TECHNICAL, LEGAL, etc., generic)
        |
        v
 deterministic extraction (voltage, MVA, dates, via regex, authoritative)
        |
        v
 LLM semantic normalization (qwen2.5:3b, Variant B, constrained JSON, candidate_id)
        |
        v
 schema validation (tender_agnostic_schema.json, jsonschema)
        |
        v
 provenance / canonical IDs (source_document, page_number, chunk_id)
        |
        v
 derived features (requirement_count, evidence_coverage, etc.)
        |
        v
 persisted analysis result (processing_job_id, pipeline_version, model, prompt_version)
        |
        v
 human-review-ready API output (GET /tenders/{id}/analysis)
```

**No BID/NO_BID decision** is made in this pipeline — `app/engines/decision.py` remains separate.

## Job Lifecycle

| Status | Meaning | Who sets? | Frontend shows | Next |
|---|---|---|---|---|
| `QUEUED` | Job created, not yet started | `POST /process` | `Queued — waiting` | `PROCESSING` |
| `PROCESSING` | Running `INVENTORY → EXTRACTION → ... → PERSISTENCE` | `process_tender()` | `Processing — stage: EXTRACTION 20%` | `COMPLETED/PARTIAL/FAILED` |
| `COMPLETED` | All documents `COMPLETE`, analysis persisted | `process_tender()` | `Completed — analysis ready` | `GET /analysis` |
| `PARTIAL` | Some documents `FAILED`/`UNSUPPORTED` but usable analysis exists | `process_tender()` | `Partial — 8/9 complete, 1 failed` | `GET /analysis` with errors |
| `FAILED` | Pipeline cannot produce meaningful result (e.g., no tender files) | `process_tender()` | `Failed — last_error` | Retry `POST /process` |

**Current limitation:** In-process `BackgroundTasks` (no Redis/Celery) — if server restarts, `QUEUED` jobs are lost. Documented.

## Processing Stages

`INVENTORY` → `EXTRACTION` → `CLASSIFICATION` → `DETERMINISTIC` → `SEMANTIC` → `VALIDATION` → `PERSISTENCE` → `COMPLETED`

Each stage updates `ProcessingJob.current_stage` and `progress` (5% → 100%). On failure, `stage` preserved and `last_error` set, `error_count` incremented, `documents_failed` incremented, but **other documents continue** (failure isolation).

## Failure Handling

- **Per-document:** `COMPLETE` (text extracted), `PARTIAL` (some pages failed), `FAILED` (no text), `UNSUPPORTED` (`.dwg`, `.jpg`, `.rar`, `.zip` — not yet supported, marked `UNSUPPORTED` and continued).
- **Tender-level:** `8` complete + `1` unsupported → `PARTIAL` (not `FAILED`). Only `0` documents or no requirements at all → `FAILED`.
- **Document errors:** `filename, stage, safe error message` stored in `ProcessingJob.last_error`, not stack trace.

## LLM Integration

- **Model:** `qwen2.5:3b` `http://localhost:11434` `OLLAMA_MODEL`/`OLLAMA_BASE_URL` configurable, default `qwen2.5:3b`.
- **Prompt:** Variant B (current production prompt + 3 few-shot: `similar 220kV projects`→`EXPERIENCE`, `220kV GIS rated`→`TECHNICAL`, `submit tender security`→`FINANCIAL`), hash `9f71b008`.
- **Chunking:** `3000` chars, `source_document`/`page_number`/`chunk_id` preserved, never sends entire tender (1394 pages) blindly.
- **Output:** `candidate_id` (`chunk-0001-item-01`), `summary`, `category`, etc., `evidence` with `candidate_id` + `requirement_candidate_id` — canonical `REQ-001` assigned **after** `deduplication` via `assign_canonical_ids()`, evidence follows canonical map (never list position).
- **Failure isolation:** One `chunk` fails (timeout, malformed JSON) → `retry` once with same prompt, if still fails → `failed_calls` incremented, other chunks continue, no predictions for that chunk.

## Provenance

Every `requirement`/`evidence` must have `source_document`, `page_number`, `source_chunk_id`, `source_text` (exact substring of chunk `text`), `confidence`, `provenance` (`quote_en`). `source_chunk_id` from actual `chunk["chunk_id"]`, not inferred from `candidate_id`. `Canonical IDs` are `REQ-001` after deduplication, `candidate_id` preserved as `_candidate_id`.

## Decision Separation

- **This pipeline produces analysis inputs** (`requirements`, `evidence`, `risks`, `deadlines`) — **not** `BID/REVIEW/NO_BID`.
- `app/engines/decision.py` remains authoritative, with `MISSING != FAIL`, `Risk → REVIEW`, `HARD_GATE_FAIL → NO_BID` — unchanged.
- No automatic `NO_BID` is generated merely because LLM extracted a requirement.

## API Endpoints

| Method | Endpoint | Request | Response | Status |
|---|---|---|---|---|
| `POST` | `/api/tenders/{id}/process` | — | `{job_id, tender_id, status QUEUED, current_stage INVENTORY}` | **EXISTING** (Phase 3A) |
| `GET` | `/api/processing-jobs/{job_id}` | — | `{job_id, tender_id, status, current_stage, progress, documents_total, documents_processed, documents_failed, error_count, last_error, pipeline_version}` | **EXISTING** |
| `GET` | `/api/tenders/{id}/analysis` | — | `{tender_id, status, progress, documents_total, pipeline_version}` or `404` if not complete | **EXISTING** |
| `GET` | `/api/tenders/{id}/requirements` | — | `Requirement[]` with `status` | **EXISTING** |
| `GET` | `/api/tenders/{id}/decision` | — | `Decision` | **EXISTING** |

## Current Limitations

1. **Local Ollama/qwen2.5:3b** — `50s` avg latency, `67%` valid JSON rate (1/3 chunks failed in Mobile sample), not production-grade for `22-22-22 kV` list-like text.
2. **In-process background execution** — if `uvicorn` restarts, `QUEUED` jobs lost — acceptable for Phase 3A, documented.
3. **CAD/DWG/RAR/JPG** `UNSUPPORTED/PARTIAL` — `Motawreen` `2.9MB DWG` not yet parsed (needs `CAD` parser).
4. **Full Mobile tender not used as production benchmark** — fixture is `16` curated chunks `~5000` chars, not `9` files `70MB+116MB` full `Mobile` OCR — `UNLABELED / EXPLORATORY`.
5. **Human review remains required** — `LLM` is `candidate` extraction, not authoritative `decision`.
6. **Extraction pipeline does not make `BID/NO_BID` decisions** — `decision.py` remains separate.
