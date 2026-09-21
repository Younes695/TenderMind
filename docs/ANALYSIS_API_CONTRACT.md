# Analysis API Contract — TenderMind — Canonical

**Version:** `analysis_version 1.0` — `pipeline_version 1.0` — `model qwen2.5:3b` — `prompt Variant B`

## Endpoint

`GET /api/tenders/{id}/analysis`

**Behavior:**

- `404` if no processing job exists
- `200` with `status QUEUED/PROCESSING` and `progress` if job is running — **not** fake completed
- `200` with `status FAILED` and `last_error` if pipeline failed
- `200` with full canonical analysis if `COMPLETED` or `PARTIAL` (partial returns usable analysis + `documents_failed` warnings)

**Example completed `200`:**
```json
{
  "tender": {"id": "SA-2018-HV2", "title": "Sarai 220/22kV GIS Substation"},
  "documents": [{"filename": "Sarai RFP.pdf", "page_count": 2, "extraction_method": "tesseract", "extraction_status": "COMPLETE", "document_type": "TECHNICAL", "ocr_applied": true, "provenance_status": "COMPLETE"}],
  "requirements": [{"id": "REQ-001", "summary": "Supply and installation of 220 kV GIS", "category": "TECHNICAL", "mandatory": null, "applicable_entity": null, "source_document": "Price schedules ...", "page_number": 1, "source_chunk_id": "chunk-0000", "source_text": "Supply and installation of 220 kV GIS", "confidence": 0.75}],
  "evidence": [{"id": "EV-001", "requirement_id": "REQ-001", "summary": "Power Transformer 60 MVA", "source_document": "Price schedules ...", "page_number": 1, "source_chunk_id": "chunk-0000", "source_text": "Power Transformer 60 MVA", "confidence": 0.8}],
  "deadlines": [{"type": "unknown", "date": "16 of August, 2018", "source_document": "Vol I", "page_number": 1, "raw_text": "16 of August, 2018"}],
  "commercial": null,
  "risks": [],
  "derived_features": {"requirement_count": 12, "evidence_coverage": 0.17, "overall_pages": 1394, "provenance_coverage": 1.0},
  "processing": {"job_id": "JOB-ABCD1234", "status": "COMPLETED", "progress": 100, "documents_total": 9, "documents_processed": 9, "pipeline_version": "1.0", "model": "qwen2.5:3b", "prompt_version": "Variant B"},
  "analysis_version": "1.0",
  "pipeline_version": "1.0",
  "model": "qwen2.5:3b",
  "prompt_version": "Variant B",
  "status": "COMPLETED",
  "created_at": "2026-09-18T10:00:00Z"
}
```

**Processing states:** `QUEUED → PROCESSING (INVENTORY 5% → EXTRACTION 20% → CLASSIFICATION 40% → DETERMINISTIC 60% → SEMANTIC 80% → VALIDATION 90% → PERSISTENCE 95% → COMPLETED 100%)` — `PARTIAL` if some documents `FAILED`/`UNSUPPORTED` but usable analysis exists, `FAILED` only if no meaningful result.

**Document states:** `COMPLETE` (text extracted), `PARTIAL` (some pages failed), `FAILED` (no text), `UNSUPPORTED` (`.dwg`, `.jpg`, `.rar`, `.zip` not yet supported) — each document has `filename`, `document_type` (`TECHNICAL`, `BOQ`, `LEGAL`, `CLARIFICATION`, `ADDENDUM`, `DRAWING`, `OTHER`), `processing_status`, `extraction_status`, `error`.

**Requirement fields:** `id` (`REQ-001` canonical, deterministic `REQ-001,002` sorted by `source_document, page_number, summary`), `summary`, `category` (`LEGAL`... 12 enum), `mandatory` (`true/false/null` — `null` if unknown, never guessed), `applicable_entity` (`string or null`), `source_document`, `page_number`, `source_chunk_id`, `source_text`, `confidence` `0-1` (extraction confidence, not business risk), `provenance` (`quote_en`), `conditional` — **never without `source_document/page_number/source_chunk_id`**.

**Evidence linkage:** `id` `EV-001`, `requirement_id` must point to existing canonical `REQ-*` (`canonical_map[requirement_candidate_id]`), never array position. Orphan evidence rejected.

**Deadlines:** `type` `submission/opening/validity/completion/unknown/unclassified` — `unknown` if not explicitly supported, `date` as `raw_text` (`16 of August, 2018`), not converted to ISO unless source supports, `source_document`/`page_number`/`source_chunk_id` preserved.

**Commercial:** `price_schedules`, `payment`, `currency` — `null` if not found, not invented.

**Risks:** Only if explicitly present or deterministic rule provides `HIGH/MEDIUM/LOW` — otherwise `null` (Phase 1 has `0` risks, not `0` as analyzed).

**Derived features:** `requirement_count`, `evidence_coverage`, `overall_pages`, `ocr_ratio`, `provenance_coverage`, `confidence_distribution` — **no `BID/NO_BID` decision** (remains separate `GET /tenders/{id}/decision`).

**Validation:** Before persistence, `validate_against_schema()` (`tender_agnostic_schema.json` via `jsonschema` or fallback) checks `required`, `types`, `enums`, `nullability`, `requirement_id` pattern `^REQ-[A-Z0-9-_]+$`, `confidence 0-1`, `deadline` `unknown` allowed. Invalid canonical output is rejected, not silently repaired.

**Versioning:** `analysis_version 1.0`, `pipeline_version 1.0`, `prompt_version Variant B` — separate, not conflated.

**Frontend-safe:** No `candidate_id`, no `chunk-local` temp, no `raw LLM output`, no `retry` internals — only canonical `REQ-*` + `source_chunk_id` + `provenance`.

**Decision separation:** `GET /tenders/{id}/analysis` **never** returns `BID/REVIEW/NO_BID` — that remains `GET /tenders/{id}/decision` (`app/engines/decision.py`).

**Partial:** `9` docs `8` complete `1` unsupported → `PARTIAL` with usable analysis + `documents_failed: 1` warning, not `FAILED`.

**Limitations:** `CAD/DWG/RAR/JPG` `UNSUPPORTED`, full Mobile `70MB+116MB` not benchmarked as production, `LLM` `qwen2.5:3b` `67%` valid JSON, human review required.
