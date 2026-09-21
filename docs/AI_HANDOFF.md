# دليل تسليم الذكاء الاصطناعي — TenderMind

> **مصدر الحقيقة هو الكود الحالي في المستودع، وليس هذا المستند وحده.**

## 1. Purpose

TenderMind طبقة ذكاء لفهم المناقصات واستخراج المعلومات المنظمة مع provenance، وتحديد المخاطر، وتوفير مدخلات موحدة لدعم `BID/REVIEW/NO_BID` عبر `app/engines/decision.py` الحتمي.

## 2. AI Pipeline Architecture

```
Tender Upload → File Inventory (64/9/5/11) → Document Extraction (fitz + Tesseract 5.4.0 ara+eng + LibreOffice 26.8.0.3)
→ Document Classification (BOQ, TECHNICAL, LEGAL, etc., generic)
→ Deterministic Extraction (voltage, MVA, dates — regex, authoritative)
→ LLM Semantic Normalization (qwen2.5:3b, Variant B, chunk 3000, constrained JSON)
→ Pydantic + JSON Schema Validation → Provenance (source_document, page_number, chunk_id, source_text) → Deduplication → Canonical IDs (REQ-001) → Evidence Linkage → Validation → Derived Features → Persisted Analysis → Human Review → Decision
```

**الملفات:** `evaluation/generic_extraction.py` (ingestion, classification, deterministic), `evaluation/llm_generic_extraction.py` (chunk, LLM, validation, dedup, canonical), `evaluation/tesseract_local_ocr.py` (Tesseract), `evaluation/run_real_benchmark.py` (orchestration), `app/processing.py` (job lifecycle).

## 3. Input → Processing → Canonical Analysis Flow

1. `POST /tenders/{id}/process` → `ProcessingJob` `QUEUED`
2. `INVENTORY` (5%) → `EXTRACTION` (20%) per-document `COMPLETE/PARTIAL/FAILED/UNSUPPORTED` (failure isolation, one bad file does not crash tender)
3. `CLASSIFICATION` (40%) generic signals, not `G - word` filename
4. `DETERMINISTIC` (60%) `voltage`/`MVA`/`dates` via regex — **authoritative**, LLM must not overwrite
5. `SEMANTIC` (80%) `qwen2.5:3b` `Variant B` per chunk `3000` chars, `temperature 0`, `format json`, `candidate_id` (`chunk-0001-item-01`), retry once on `TIMEOUT/CONNECTION/EMPTY/MALFORMED/HTTP 5xx`
6. `VALIDATION` (90%) `Pydantic` + `jsonschema` + `provenance` + `canonical` + `evidence linkage`
7. `PERSISTENCE` (95%) `TenderAnalysis` `analysis_version 1.0` with `tender, documents, requirements, evidence, deadlines, commercial, risks, derived_features, processing`
8. `COMPLETED` (100%) or `PARTIAL` (some `FAILED`/`UNSUPPORTED` but usable) or `FAILED` (no meaningful result)

## 4. Current Canonical Schema

`schemas/tender_agnostic_schema.json` — `tender_id` dynamic (not `SA-2018-HV2`), `title`, `client`/`location` nullable, `languages` free-form (`AR, EN, FR`), `documents[]` (`filename`, `page_count`, `text_length`, `extraction_method` free-form `tesseract_5.4.0_ara+eng_psm6_dpi300`, `extraction_status` `COMPLETE/PARTIAL/FAILED/UNSUPPORTED`, `document_type` `TECHNICAL/BOQ/LEGAL` etc., `ocr_applied`, `provenance_status`), `requirements[]` (`requirement_id` `^REQ-[A-Z0-9-_]+$` canonical `REQ-001` after dedup, `summary`, `category` 12 enum, `mandatory` `boolean|null` — `null` if unknown, `requirement_type` `HARD_GATE` etc. nullable, `applicable_entity` free-form `string|null` — not `GIZA/HYOSUNG` enum, `source_document`, `page_number`, `source_chunk_id`, `source_text`, `confidence 0-1`, `provenance` `quote_en`, `conditional`), `evidence[]` (`evidence_id`, `requirement_id` canonical, `fact`, `source_document`, `page_number`, `source_chunk_id`, `source_text`, `confidence`, `applicable_entity` free-form, `valid_until`, `reusable`), `deadlines[]` (`type` `submission/opening/validity/completion/unknown/unclassified`, `date` string `raw_text`, not ISO unless source supports), `commercial` `null` if not found, `risks[]` (`severity` nullable `HIGH/MEDIUM/LOW/null`), `provenance_coverage`, `confidence_distribution`, `missing_rate`, `extraction_metadata` (`tender_id`, `timestamp`, `extraction_method`, `model`, `ocr_applied`).

## 5. Requirement Contract

- `id` `REQ-001` canonical, deterministic, sorted by `source_document, page_number, summary`, unique, `candidate_id` preserved as `_candidate_id`
- `summary` human-readable, `category` 12 enum, `mandatory` `true/false/null` — `null` if source does not explicitly establish `mandatory` (e.g., `shall have` vs `may`), never inferred from `category`
- `applicable_entity` `string|null` — `null` if not explicit, never invented `CONSORTIUM`
- `source_document`, `page_number`, `source_chunk_id`, `source_text` exact substring of chunk `text` — **never fabricated**, `confidence 0-1` (extraction confidence, not business risk)
- `provenance` `quote_en` exact quote, `extraction_method` `deterministic`/`llm`/`hybrid`

## 6. Evidence Contract

- `id` `EV-001` canonical, `requirement_id` must point to existing canonical `REQ-*` via `canonical_map[requirement_candidate_id]`, never array position — orphan evidence (`unknown candidate`) rejected (`_rejected`)
- `summary`/`fact`, `source_document`, `page_number`, `source_chunk_id`, `source_text`, `confidence 0.85`, `applicable_entity` free-form, `valid_until`, `reusable` — all with provenance, never without `source`
- If chunk has requirement but no supporting evidence, `evidence = []` — do not force one evidence per requirement

## 7. Provenance Contract

Every `requirement`/`evidence` must retain `source_document`, `page_number`, `source_chunk_id`, `source_text` (exact substring of `chunk["text"]`), `confidence`. `source_chunk_id` from actual `chunk["chunk_id"]` (`chunk-0000`), not inferred from `candidate_id` (`chunk-0001-item-01` hallucinated → corrected to `chunk-0000-item-01`). Never downgrade valid `source/page` because `confidence` low — `confidence` (extraction) and `provenance` (traceability) are separate.

## 8. Processing States

`QUEUED` (job created, not yet started, `progress 0`), `PROCESSING` (`INVENTORY 5% → EXTRACTION 20% → CLASSIFICATION 40% → DETERMINISTIC 60% → SEMANTIC 80% → VALIDATION 90% → PERSISTENCE 95%`), `COMPLETED` (all documents `COMPLETE`, analysis persisted, `progress 100`), `PARTIAL` (some `FAILED`/`UNSUPPORTED` but usable analysis exists, e.g., `9` docs `8` complete `1` unsupported `DWG` → `PARTIAL`), `FAILED` (pipeline cannot produce meaningful analysis, e.g., no `tender_path`, no `documents`). Use actual implementation, not invented `UPLOADED`.

## 9. Document States

`COMPLETE` (text extracted, `5598` chars `libreoffice` for `.doc` 40KB, `3723` chars `tesseract` for `Drawings 1-SLD.pdf` 1 page), `PARTIAL` (some pages failed, `max-pages` reached, `skip-ocr` with `OCR` needed), `FAILED` (no text, `0` chars, `olefile` fallback empty), `UNSUPPORTED` (`.dwg` 2.9MB, `.bak`, `.jpg` 3KB, `.rar` 325MB, `.zip` 2.3MB — not yet supported, marked `UNSUPPORTED` and continued). One bad file **never** crashes tender.

## 10. LLM Reliability Behavior

- **Failure types:** `TIMEOUT` (90s), `CONNECTION_ERROR` (`ConnectionRefused`), `EMPTY_RESPONSE` (`null`/whitespace), `MALFORMED_JSON` (`json.loads` fail), `SCHEMA_INVALID` ( `validate_requirement` fail), `HTTP_ERROR` (`status !=200`), `UNKNOWN_ERROR` — recorded as `chunk_id, source_document, page_number, failure_type, attempts, safe_error_message, elapsed_seconds` (no stack trace, no secrets, no full prompt).
- **Retry:** `initial + one retry` (2 total), **only** for `TIMEOUT, CONNECTION_ERROR, EMPTY_RESPONSE, MALFORMED_JSON, HTTP 5xx` — **not** for `SCHEMA_INVALID` (deterministic) or `HTTP 4xx` (unless documented). Retry uses **same** `chunk`, `Variant B` prompt, `model` `qwen2.5:3b`, same params — no reuse of malformed JSON, no fabricated fields.
- **Per-chunk isolation:** `100` chunks `3` failed `97` successful → `semantic_chunks_successful 97`, `semantic_chunks_failed 3` — failed chunk → `requirements []`, `evidence []` (**zero predictions**, not `no requirements`), does not delete successful `97` or `deterministic` `voltage` values.
- **Zero-prediction semantics:** Failed chunk means **no semantic prediction was produced**, **not** `this chunk contains no requirements` — recorded in `run report` as `failed` vs `skipped empty`.
- **Deterministic survives LLM failure:** `220kV`, `175MVA` from deterministic remain, even if `3` chunks failed.

## 11. Retry Behavior

- First call timeout `90s` → `TIMEOUT`, second call fresh `qwen2.5:3b` same chunk → if success, `retry_successes++`, else `retry_failures++`, `failed_calls` increments, `http_calls` = `initial_attempts` (3) + `retry_attempts` (1) = `4` for `3` chunks with `1` retry.

## 12. Failure Semantics

- **Permanently failed chunk** (2 attempts): `requirements []`, `evidence []`, `failure_type` final (e.g., `EMPTY_RESPONSE` after `TIMEOUT` on first attempt — **attempt history preserved**: `[{attempt:1, failure_type:TIMEOUT, elapsed:90.1}, {attempt:2, failure_type:EMPTY_RESPONSE, elapsed:2.0}]`, final `failure_type EMPTY_RESPONSE`, `attempts 2`, `elapsed_seconds 92.1`), `provenance` remains valid for successful neighbors, `deterministic` remains.

## 13. Deterministic Extraction Boundary

- `extract_voltage_levels()` `220kV` regex, `extract_mva_values()` `MVA`, `extract_deadlines_deterministic()` `16 of August, 2018` (type `unknown`) — **authoritative**, LLM may normalize but **must not silently overwrite**. Conflict recorded as `{"type":"deterministic_llm_conflict","fact":"voltage","deterministic_value":["220kV"],"llm_value":"110kV"}`.

## 14. Decision Boundary

- **AI analysis is NOT final `BID/NO_BID`**. AI provides `requirements`, `evidence`, `deadlines`, `commercial`, `risks`, `derived_features` (`requirement_count`, `evidence_coverage`, `overall_pages`, `ocr_ratio`).
- **Decision layer** `app/engines/decision.py` `decide()` remains separate, deterministic, `MISSING != FAIL`, `Risk → REVIEW`, `HARD_GATE_FAIL → NO_BID` — **not modified**.
- **Human/committee** gives final `Go/No-Go`.

## 15. API Integration Points

- `POST /tenders/{id}/process` → `{job_id, tender_id, status QUEUED, current_stage INVENTORY}` (async `BackgroundTasks`, in-process, `PIPELINE_VERSION 1.0`)
- `GET /processing-jobs/{job_id}` → `{job_id, tender_id, status, current_stage, progress, documents_total/processed/failed/unsupported, error_count, last_error, pipeline_version, model, prompt_version}`
- `GET /tenders/{id}/analysis` → **canonical analysis** (`tender, documents, requirements, evidence, deadlines, commercial, risks, derived_features, processing`) — `404` if no job, `QUEUED/PROCESSING` if not complete, `FAILED` with `last_error`, `COMPLETED/PARTIAL` with full analysis + `documents_failed` warnings. **Prototype contract — backend production hardening required** (durable worker, persistence, auth).

## 16. Current Limitations

- **Local `qwen2.5:3b` Ollama dependency** — `50s` avg, `67%` valid JSON, `1/3` chunks failed on `Commercial forms.txt` equipment list (`valid JSON 67%` in Mobile sample, not production-ready).
- **Long OCR cost** — `Sarai` `946` OCR pages `7919s` `2h12m`, full `Sarai` OCR remains expensive, `in-process BackgroundTasks` lost on restart.
- **In-process execution** — `que` jobs lost on `uvicorn` restart (documented).
- **Controlled LLM reliability** — `1` known failure on list-like `Commercial forms` input.
- **CAD/DWG/RAR/JPG** `UNSUPPORTED` (Motawreen `2.9MB DWG`).

## 17. Backend Integration Requirements

**AI currently owns:** ingestion, classification, deterministic extraction, LLM semantic extraction, validation, provenance, canonicalization, evidence linkage, AI processing metadata, `analysis_version`.

**Backend must own before production:** durable `ProcessingJob` execution (queue/worker, not in-process), `TenderAnalysis` persistence architecture (currently `SQLite` `tendermind.db` `tender_analyses` table, in-memory for demo), `TenderDocument` persistence, authentication/authorization, production database lifecycle (`Postgres`), API security, production retries/monitoring (` Prometheus`), deployment/runtime configuration (`Docker`), `S3` for tender files (currently `C:\Users\EgyTech\Desktop\01- Sarai...` local).

**Explicitly mark:** `Backend implementation required before production deployment.`

## 18. Frontend Integration Requirements

**Frontend can consume:** `GET /tenders/{id}/analysis` canonical analysis (no `Ollama`/`chunks`/`candidate IDs` needed) — render `no analysis yet` (`404`), `queued` (`QUEUED`), `processing` (`PROCESSING` `progress`), `completed` (`COMPLETED` with `tender, documents, requirements, evidence, deadlines, commercial, risks, derived_features`), `partial` (`PARTIAL` with warnings), `failed` (`FAILED` with `last_error`). For each requirement: `summary`, `category`, `mandatory` (if known), `applicable_entity`, `confidence`, `source_document`, `page`, `source_chunk`, `source_text`; for evidence: `fact`, `linked requirement`, `source location`.

## 19. What AI Owns / Does NOT Own

**AI owns:** `ingestion orchestration`, `document classification`, `generic/deterministic/semantic extraction`, `validation`, `provenance`, `canonicalization`, `evidence linkage`, `AI processing metadata` (`pipeline_version`, `model`, `prompt_version`).

**AI explicitly does NOT own:** `BID/NO_BID` decision (`decision.py`), `ProcessingJob` durability, `TenderDocument` persistence, `auth`, `production DB`, `queue/worker`, `frontend UI`.

## 20. Known Test Status

- `tests/test_generic_extraction.py` `18/18` **passed** (arbitrary tender IDs, variable counts, `EN-only`, `unknown` deadline, `nullable` risk)
- `tests/test_llm_generic_extraction.py` `23/23` **passed** (chunk provenance, `fenced` JSON, `missing provenance` rejected, `retry`, `canonical` linkage, `duplicate` handling)
- `tests/test_doc_libreoffice.py` `5/5` **passed** (`libreoffice` `5598`)
- `tests/test_pdf_ocr_routing.py` `7/7` **passed** (`ocr_needed_hint` `False` no `Tesseract`)
- `tests/test_processing_pipeline.py` `5/5` **passed** (`POST /process` `200`, `404`, `409` duplicate, `GET /processing-jobs`, `GET /analysis`)
- Existing offline `46` still pass — **no `decision.py` change**

## 21. Known Benchmark Limitations

- `Mobile` `3` chunks `16` curated `~5000` chars, not `9` files `70MB+116MB` full `Mobile` OCR — `UNLABELED / EXPLORATORY`, not `GOLD-VALIDATED` like Sarai `21` `F1 ≥0.90`
- `1` failed chunk (`Commercial forms.txt` equipment list) — `qwen2.5:3b` local unstable for list-like text
- `Full Sarai` `1394` pages `946` OCR `7919s` not rerun after `ocr_needed_hint` fix — `~60s` smoke test only (3 drawings + `volume 1` `189` native)

## 22. Quick Start

```bash
git clone https://github.com/Younes695/TenderMind.git
cd TenderMind
pip install -r requirements.txt
# LibreOffice already installed 26.8.0.3
# Ollama
ollama pull qwen2.5:3b
uvicorn app.main:app --reload
# Test
python tests/test_llm_generic_extraction.py # 23/23
# Benchmark (small fixture, no full OCR)
OLLAMA_MODEL=qwen2.5:3b OLLAMA_BASE_URL=http://localhost:11434 python evaluation/run_llm_gold_benchmark.py # fixture 3 chunks
```

---

**Backend handoff required before production deployment.**
**Frontend handoff ready — can start with `GET /analysis` mock (`evaluation/gold/mobile_representative_gold.json`).**
