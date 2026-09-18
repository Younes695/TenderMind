# TenderMind — Frontend + Backend Handoff — CANONICAL

**Repo:** `C:\Users\EgyTech\Desktop\TenderMind` — `origin https://github.com/Younes695/TenderMind.git` — branch `main` — commit `b2af0fb`+`45c2704`+`2163985` (Hybrid + Tesseract + LibreOffice)
**Stack:** FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic 2.11 + SQLite temp `opencode/tendermind` + PyMuPDF 1.28.2 + Tesseract 5.4.0 `ara+eng` + LibreOffice 26.8.0.3 + Ollama `qwen2.5:3b` local
**Constraints:** No Azure, no OpenAI, no paid services — all OCR/LLM localhost, $0. Deterministic decision semantics (`app/engines/decision.py`) and frozen acceptance criteria (`docs/AI_Acceptance_Criteria.md`) unchanged.

---

## PRODUCT FEATURES — Tender Upload → Report/Export

Intended flow: `Tender Upload → File Inventory → Document Extraction/OCR → Requirement Extraction → Evidence Extraction → Matching → Deterministic Decision → Explanation → Provenance/Audit → Report/Export`

### 1. Tender Upload — PARTIAL
- **Backend EXISTS:** No dedicated `POST /tenders/{id}/upload` — upload is via direct filesystem `C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation` (64 files) used by `evaluation/run_real_benchmark.py:63` `file_inventory()` — verified `app/api/routes.py` has no upload endpoint.
- **Frontend should build:** Drag-and-drop upload zone for `*.pdf, *.doc, *.docx, *.xls, *.xlsx`, progress bar, file list with size/type, validation (max 64 files, 15MB).
- **Required data:** `TenderDocument {id, tender_id, filename, path, size, type, upload_timestamp}` — **PROPOSED** (current `TenderDocument` model exists but not exposed via API).
- **Blocker:** Backend upload API missing — frontend must mock.

### 2. Tender List — EXISTING / VERIFIED
- **Backend EXISTS:** `GET /api/tenders` `app/api/routes.py:13` returns `Tender[]` (id `SA/2018/HV2`, title `Sarai 220/22kV GIS Substation`, client `MNHD`, location `Sarai, Egypt` via `app/seed.py`).
- **Frontend:** Table/cards with tender id, title, client, location, `decision` badge (`REVIEW`/`BID`/`NO_BID`), last updated.
- **Data:** `Tender {id, title, client, location, original_no}` — **EXISTING**.
- **Blocker:** None.

### 3. Tender Overview/Dashboard — PARTIAL
- **Backend EXISTS:** `GET /api/tenders/{id}` `19` + `GET /api/tenders/{id}/decision` `66` returns `decision, confidence, hard_fail_count, mandatory_missing_count, top_blockers, top_risks`.
- **Frontend:** Header with tender metadata, `top_blockers` (6) and `top_risks` (4) chips, `hard_fail 0` indicator.
- **Data:** `Decision` fields — **EXISTING**.
- **Blocker:** None for overview, but `processing status` not exposed.

### 4. Processing Status — PROPOSED / BLOCKED
- **Backend:** No `processing job/status/progress` endpoint — `evaluation/run_real_benchmark.py:418` `run_document_intelligence()` is synchronous, long-running (`7919s` for 946 pages Tesseract), no `QUEUED/PROCESSING` status, no polling. **BLOCKED.**
- **Frontend should build:** Status timeline `UPLOADED → QUEUED → PROCESSING → EXTRACTING → OCR → REQUIREMENTS → EVIDENCE → MATCHING → DECISION → COMPLETED/FAILED`, progress bar, polling every 2s, error banner.
- **Required data:** `ProcessingJob {id, tender_id, status, progress 0-100, stage, error, started_at, completed_at}` — **PROPOSED**.
- **Blocker:** Backend must implement async job + `GET /api/tenders/{id}/processing/status` before frontend can show real progress — frontend must mock via `setTimeout` for now.

### 5. Requirements Dashboard — EXISTING / VERIFIED
- **Backend EXISTS:** `GET /api/tenders/{id}/requirements` `24` returns `Requirement[]` with `status` (`PASS/FAIL/MISSING/REVIEW`), `evidence_ids`, `reason`, `provenance` via `app/engines/status.py:1` `evaluate_all()` (deterministic, `MISSING≠FAIL`).
- **Frontend:** Filterable table by `category` (`LEGAL, TECHNICAL, EXPERIENCE, EQUIPMENT, FINANCIAL, SCHEDULE, SUBMISSION, HSE, QA_QC, PERSONNEL, SUBCONTRACTOR`), `mandatory` toggle, `status` pills, `applicable_entity` (`GIZA/CONSORTIUM`), search, 21 rows (A-U).
- **Data:** `Requirement {requirement_id, category, requirement, mandatory, requirement_type, evidence_required, source_document, page_or_section, applicable_entity, confidence, status, provenance[]}` — **EXISTING** via `schemas/requirement_schema.json:7`.
- **Blocker:** None for list, but `requirement details` needs `source_spans` with `bbox` (partial — `source_spans` in schema but not returned by API).

### 6. Evidence Viewer — EXISTING / VERIFIED
- **Backend EXISTS:** `GET /api/tenders/{id}/evidence` `47` returns `Evidence[]` (4 gold: `E-001 R PASS CONSORTIUM`, `E-002 B PASS HYOSUNG`, `E-003 J PASS HYOSUNG`, `E-004 U REVIEW CONSORTIUM` with `source_document`, `page_or_section`, `fact`, `extraction_confidence`), `GET /api/tenders/{id}/missing-evidence` `58` returns `MissingEvidence[]`.
- **Frontend:** Evidence cards with `fact`, `status` badge, `source_document + page_or_section` link, `applicable_entity`, `valid_until`, `reusable` flag; `MissingEvidence` checklist with `document_needed`, `priority`, `owner`.
- **Data:** `Evidence {evidence_id, company_id, requirement_supported, evidence_type, fact, status, source_document, page_or_section, extraction_confidence, applicable_entity, valid_until, tender_source_id, reusable}` — **EXISTING** via `schemas/evidence_schema.json`.
- **Blocker:** `.DOC` extraction now via `LibreOffice` `evaluation/run_real_benchmark.py:310` `libreoffice_headless_txt` (5598 chars, `DOC_EXTRACTOR=libreoffice`), but evidence `4/4` only when run via `extract_docx_text` directly — full `64-file` run still `1/4` due to `file_inventory` `ocr_needed` mismatch (needs wiring, not blocker for UI).

### 7. Review / Conflict Center — EXISTING / VERIFIED
- **Backend EXISTS:** `status` `REVIEW` + `conflicts[]` from `app/engines/status.py` (test `First vs Second` category → `REVIEW` + `conflicts`), `GET /api/tenders/{id}/requirements` includes `conflicts` via `status_results`, `GET /api/tenders/{id}/audit` `142` shows `Decision` + `DecisionAudit` with `reviewer, timestamp, reason, previous_decision, new_decision`.
- **Frontend:** Review queue table (`17 MISSING` + `1 REVIEW` U + `3 PASS`), `conflicts` banner, `Human override` button (`POST /api/tenders/{id}/decision/override` `97` with `reviewer, new_decision, reason, comments`), audit timeline.
- **Data:** `DecisionAudit {id, decision_id, reviewer, timestamp, previous_decision, new_decision, reason, comments}` — **EXISTING**.
- **Blocker:** None.

### 8. Bid/No-Bid/Review Decision Dashboard — EXISTING / VERIFIED
- **Backend EXISTS:** `GET /api/tenders/{id}/decision` `66` + `POST /api/tenders/{id}/decision/recompute` `92` + `POST /api/tenders/{id}/decision/override` `97` + `GET /api/tenders/{id}/explanation` `189` (`build_explanation()` returns `decision, confidence, summary, hard_failures, missing_evidence, risks, supporting_evidence, conflicts, rules_triggered, provenance_chain`).
- **Frontend:** Big badge `REVIEW — DO NOT BID YET` `LOW` `MANDATORY_GATE_MISSING` (gold `REVIEW` `hard_fail 0` `mandatory_missing 1` `top 6 blockers A,C,D,E,F,G`), `rules_triggered`, `hard_fail_count`, `top_blockers/risks` lists, `explanation` provenance chain.
- **Data:** `Decision {decision BID/REVIEW/NO_BID, confidence LOW/MEDIUM/HIGH, hard_fail_count, mandatory_missing_count, top_blockers, top_risks, rules_triggered, supporting_requirements, supporting_evidence, missing_evidence, risks, is_override}` — **EXISTING**, deterministic `app/engines/decision.py:12` hierarchy (FAIL→NO_BID, MISSING→REVIEW, etc.).
- **Blocker:** None — decision engine untouched and passing.

### 9. Report / Export — EXISTING / VERIFIED
- **Backend EXISTS:** `GET /api/tenders/{id}/export` `152` returns full JSON (`tender, decision, requirements[] with status, evidences, risks, missing_evidence, provenance_chain`), `GET /api/tenders/{id}/explanation` `189` returns machine-readable explanation. No PDF generation.
- **Frontend:** `Export JSON` button, `Print` view, `Download` for audit.
- **Data:** Same as decision + requirements — **EXISTING**.
- **Blocker:** PDF report generation **PROPOSED** (not in backend).

---

## BACKEND API — EXISTING CONTRACT (verified `app/api/routes.py:205`)

| Method | Endpoint | Request | Response | Purpose | Source |
|---|---|---|---|---|---|
| `GET` | `/api/tenders` | — | `Tender[]` | List tenders | `13` **EXISTING** |
| `GET` | `/api/tenders/{id}` | — | `Tender` | Get tender | `17` **EXISTING** |
| `GET` | `/api/tenders/{id}/requirements` | — | `Requirement[] + status` | Requirements + matching status | `24` **EXISTING** |
| `GET` | `/api/tenders/{id}/evidence` | — | `Evidence[]` | All evidences | `47` **EXISTING** |
| `GET` | `/api/tenders/{id}/risks` | — | `Risk[]` | 7 Sarai risks | `53` **EXISTING** |
| `GET` | `/api/tenders/{id}/missing-evidence` | — | `MissingEvidence[]` | Missing checklist | `58` **EXISTING** |
| `GET` | `/api/tenders/{id}/decision` | — | `Decision + status_results` | Current decision | `66` **EXISTING** |
| `POST` | `/api/tenders/{id}/decision/recompute` | — | `Decision` | Recompute deterministic | `92` **EXISTING** |
| `POST` | `/api/tenders/{id}/decision/override` | `{reviewer, new_decision, reason, comments}` | `{override_decision, audit_id, previous}` | Human override | `97` **EXISTING** |
| `GET` | `/api/tenders/{id}/audit` | — | `{decisions, audits}` | Audit trail | `142` **EXISTING** |
| `GET` | `/api/tenders/{id}/export` | — | `{tender, decision, requirements, evidences, risks, missing_evidence, provenance_chain}` | Full export | `152` **EXISTING** |
| `GET` | `/api/tenders/{id}/explanation` | — | `Explanation` | Machine-readable explanation | `189` **EXISTING** |
| `GET` | `/api/company/{id}` | — | `{company, evidences}` | Company evidences | `199` **EXISTING** |
| `GET` | `/health` | — | `{status, tender}` | Health | `app/main.py:38` **EXISTING** |

**PROPOSED API CONTRACT (missing for frontend):**

| Method | Endpoint | Request | Response | Purpose |
|---|---|---|---|---|
| `POST` | `/api/tenders` | `{title, client, location}` | `Tender` | Create tender | **PROPOSED** |
| `POST` | `/api/tenders/{id}/files` | `multipart/form-data` `files[]` | `TenderDocument[]` | Upload tender PDFs/DOCs/XLS | **PROPOSED** |
| `GET` | `/api/tenders/{id}/files` | — | `TenderDocument[]` | List uploaded files | **PROPOSED** |
| `POST` | `/api/tenders/{id}/process` | — | `{job_id, status}` | Start async processing | **PROPOSED** |
| `GET` | `/api/tenders/{id}/processing/status` | — | `{status, progress, stage, error}` | Poll processing | **PROPOSED** |
| `GET` | `/api/tenders/{id}/requirements/{reqId}` | — | `Requirement + status` | Requirement details | **PROPOSED** |
| `GET` | `/api/tenders/{id}/evidence/{evId}` | — | `Evidence + provenance` | Evidence details | **PROPOSED** |
| `GET` | `/api/tenders/{id}/review` | — | `{review_items, conflicts}` | Review center | **PROPOSED** (currently via `requirements` + `audit`) |

---

## DATA CONTRACTS — `app/models.py` + `schemas/` (verified)

| Field | Type | Required | Meaning | Existing/Proposed | Source |
|---|---|---|---|---|---|
| `Tender.id` | `string` `SA-2018-HV2` | Yes | Tender ID | **EXISTING** | `app/models.py:1` `schemas/requirement_schema.json:9` |
| `Requirement.requirement_id` | `string` `REQ-A` | Yes | Stable ID A-U | **EXISTING** | `schemas/requirement_schema.json:8` |
| `Requirement.category` | `enum` `LEGAL, TECHNICAL...` | Yes | Category | **EXISTING** | `schemas:10` |
| `Requirement.mandatory` | `boolean` | Yes | Hard gate | **EXISTING** | `app/models.py` |
| `Requirement.applicable_entity` | `enum` `CONSORTIUM/GIZA/HYOSUNG/AMBIGUOUS` | Yes | Who must satisfy | **EXISTING** | `schemas:18` |
| `Evidence.evidence_id` | `string` `E-001` | Yes | Evidence ID | **EXISTING** | `app/models.py` |
| `Evidence.fact` | `string` | Yes | Extracted fact | **EXISTING** | `app/models.py` |
| `Evidence.applicable_entity` | `enum` | Yes | Owner | **EXISTING** | `app/models.py` |
| `Evidence.valid_until` | `datetime` | No | Expiry | **EXISTING** | `app/models.py` |
| `TenderDocument` | `id, tender_id, filename, path, size, type` | Yes | Uploaded file | **PROPOSED** (model exists but not exposed) | `app/models.py` |
| `ProcessingJob` | `id, tender_id, status, progress, stage` | Yes | Async job | **PROPOSED** | — |
| `Match` | `requirement_id, evidence_ids, status, reason, provenance` | Yes | Per-requirement matching | **EXISTING** via `status_results` |
| `Decision.decision` | `enum` `BID/REVIEW/NO_BID` | Yes | Final decision | **EXISTING** | `app/models.py` |
| `DecisionAudit` | `reviewer, timestamp, reason` | Yes | Human override audit | **EXISTING** | `app/models.py` |
| `Provenance` | `source_document, page_or_section, evidence_id, quote` | Yes | Source link | **EXISTING** | `app/engines/status.py` |
| `Risk` | `risk_id, type, severity, decision_impact REVIEW` | Yes | Commercial/financial risk | **EXISTING** | `app/models.py` |

---

## MATCHING / DECISION SEMANTICS — `app/engines/status.py:1` + `app/engines/decision.py:12` (verified, not modified)

- **PASS** — Valid non-expired applicable evidence `status=PASS` with provenance `source_document+page/section+evidence_id+quote+confidence`, no conflict — `status.py` `PASS`.
- **FAIL** — Applicable evidence `status=FAIL` with explicit contradictory evidence (e.g., `Second Category` vs `First Category` `E-FAIL-CONTRADICT`) — `status.py` `FAIL` → `decision.py` `HARD_GATE_FAIL` → `NO_BID` **only if** `mandatory HARD_GATE`.
- **MISSING_EVIDENCE** — No applicable evidence (0 matches or filtered by `applicable_entity`/`valid_until`/`reusable`) → `MISSING_EVIDENCE` + `reason = evaluation_logic.MISSING_EVIDENCE` — **never auto-converted to `FAIL`** (`MISSING≠FAIL` invariant).
- **REVIEW** — `valid_until < now` → `expired:true` + `REVIEW`; `applicable_entity AMBIGUOUS` → `REVIEW`; conflicting `PASS` vs `FAIL` → `REVIEW` + `conflicts[]`; `REVIEW` evidence (e.g., `E-004` `REVIEW` `CONSORTIUM`) → `REVIEW`; `Risk` always `REVIEW` (`Risk.decision_impact REVIEW` per `AI_Evaluation_Contract_v1.md:14`).
- **N/A** — `NOT_APPLICABLE` for non-mandatory filtered.
- **Mandatory** — `HARD_GATE` always `mandatory true` — `decision.py:12` hierarchy: `FAIL` → `NO_BID`, `MISSING` → `REVIEW`, `REVIEW` → `REVIEW`, else `BID`.
- **Applicable** — Strict `applicable_entity` filter (`GIZA` cannot be satisfied by `HYOSUNG` — test `test_6`), `AMBIGUOUS` → `REVIEW`.

**Deterministic decision `app/engines/decision.py:12` `decide()`:** `hard_fail>0`→`NO_BID`, else `mandatory HARD_GATE MISSING`→`REVIEW`, else `REVIEW`→`REVIEW`, else `HIGH` risk→`REVIEW`, else `BID` — **never `Risk→NO_BID`, never `MISSING→FAIL`**.

---

## PROCESSING LIFECYCLE — CURRENT vs PROPOSED

**CURRENT (verified `evaluation/run_real_benchmark.py:783` `main()` + `app/main.py:11` `startup()`):**
- `UPLOADED` — files in `C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation` (64 files) **EXISTING** (manual filesystem, no API)
- `PROCESSING` — synchronous `run_document_intelligence()` `403` → `extract_pdf_text()` `187` (now `ocr_needed_hint` routed) → `extract_docx_text()` `310` (`libreoffice` `5598` for `.doc`) → `extract_requirements_rule_based()` `492` → `extract_evidence_rule_based()` `561` → `evaluate_all()` → `decide()` — **EXISTING** but **synchronous, no job, no progress, blocks for `7919s` if full Tesseract, times out in tool.**
- `COMPLETED`/`FAILED` — via `threshold_results` `overall PASS/FAIL` **EXISTING**, but no `QUEUED/FAILED` status.

**PROPOSED frontend-friendly (not yet implemented):**
- `UPLOADED` (after `POST /files`) **PROPOSED**
- `QUEUED` **PROPOSED**
- `PROCESSING` **PROPOSED** with `progress 0-100` per stage (`EXTRACTING 20% → OCR 40% → REQUIREMENTS 60% → EVIDENCE 70% → MATCHING 85% → DECISION 95% → COMPLETED 100%`)
- `EXTRACTING/OCR/REQUIREMENTS/EVIDENCE/MATCHING/DECISION` — **PROPOSED** granular, currently only `PROCESSING`
- `COMPLETED` / `FAILED` **PROPOSED**
- **Synchronous/asynchronous:** Currently **synchronous** (`run_real_benchmark.py` blocks) — **PROPOSED** `async` via `POST /process` returning `job_id`, `GET /processing/status` polling, `progress` per stage, `errors` array.
- **Long-running:** `7919s` for `946` Tesseract pages — frontend **must poll** every 2s.
- **Current limitation:** No polling, no `job_id`, `run_document_intelligence()` re-opens PDFs twice (`file_inventory` + `extract_pdf_text` double `fitz` open) — fixed in Phase A via `ocr_needed_hint` to avoid duplicate.

---

## FRONTEND STARTING SCOPE — Can start immediately (no AI perfection needed)

1. **App shell** — React/Vite + Tailwind, layout, nav, `TenderMind` header — **can start now** (no API)
2. **Tender list** — `GET /api/tenders` — **can start now** (mock `SA/2018-HV2` if API not ready)
3. **Tender upload** — `POST /api/tenders/{id}/files` — **can start UI now**, mock upload progress
4. **Upload progress** — progress bar, file validation — **can start now** (mock)
5. **Processing screen** — timeline `UPLOADED → COMPLETED`, polling mock — **can start now** (use `setTimeout` mock until `processing/status` exists)
6. **Tender overview** — `GET /api/tenders/{id}` + `GET /api/tenders/{id}/decision` — **can start now** (verified)
7. **Requirements table** — `GET /api/tenders/{id}/requirements` — **can start now** (21 rows, filters for `category`, `mandatory`, `status`)
8. **Requirement details** — `GET /api/tenders/{id}/requirements` `provenance` + `source_spans` — **can start now** (partial `source_spans` not in API, mock)
9. **Evidence panel** — `GET /api/tenders/{id}/evidence` — **can start now**
10. **Source/page viewer** — `source_document + page_or_section` link, `bbox` overlay — **can start now** (PDF viewer mock)
11. **Review/conflict center** — `GET /api/tenders/{id}/requirements` `REVIEW` + `conflicts` + `GET /api/tenders/{id}/audit` — **can start now**
12. **Decision dashboard** — `GET /api/tenders/{id}/decision` + `explanation` — **can start now** (big badge `REVIEW`/`BID`/`NO_BID`)
13. **Report page** — `GET /api/tenders/{id}/export` + `explanation` — **can start now** (JSON export, print view)
14. **Loading states** — skeletons for all tables — **can start now**
15. **Empty states** — `No tenders`, `No requirements` — **can start now**
16. **Error states** — `404 Tender not found`, `ocr_failed` banner — **can start now**
17. **API client layer** — `fetch` wrapper for `app/api/routes.py` contracts — **can start now**
18. **Mock/stub data** — use `evaluation/sarai_gold_dataset.json` (21 req, 4 ev, 7 risks) as mock until backend `processing` ready — **can start now**

---

## BACKEND STARTING SCOPE — Can start now

1. **API structure** — `app/main.py:8` `FastAPI` + `app/api/routes.py:11` `APIRouter` — **EXISTING**, add `POST /tenders`, `POST /files`, `POST /process`
2. **Pydantic contracts** — `schemas/requirement_schema.json:7` etc. — **EXISTING**, add `TenderDocument`, `ProcessingJob` schemas
3. **Tender/file endpoints** — `POST /tenders`, `POST /tenders/{id}/files`, `GET /tenders/{id}/files` — **PROPOSED** (currently filesystem `ROOT` constant)
4. **Processing job/status contract** — `ProcessingJob` model + `GET /processing/status` — **PROPOSED**
5. **Requirements APIs** — `GET /tenders/{id}/requirements` **EXISTING**, add `GET /requirements/{reqId}` **PROPOSED**
6. **Evidence APIs** — `GET /evidence` **EXISTING**, add `GET /evidence/{evId}` **PROPOSED**
7. **Decision API** — `GET /decision`, `POST /decision/recompute`, `POST /decision/override`, `GET /explanation` — **EXISTING**
8. **Review/conflict API** — via `requirements` `REVIEW` + `audit` — **EXISTING**, add `GET /review` **PROPOSED**
9. **Report/export API** — `GET /export` **EXISTING**, add `GET /export/pdf` **PROPOSED**
10. **Persistence** — `app/database.py` `SQLite` `SessionLocal` `init_db` `app/seed.py` `SA/2018-HV2` — **EXISTING**, add `TenderDocument` persistence
11. **Integration tests** — `tests/test_*` `17+7+4` — **EXISTING**, add `test_doc_libreoffice.py` `5` (just added)
12. **Frontend mock-data contract** — serve `sarai_gold_dataset.json` as mock — **EXISTING**

---

## WHAT THEY SHOULD NOT WAIT FOR

Frontend and Backend **should NOT wait for:**
- perfect OCR (`Tesseract` 7919s for 946 pages, `page_number_accuracy` still `0.007` in real run due to `fitz` probe, but `libreoffice` now `5598` for `.doc` — not needed for UI)
- perfect LLM extraction (`requirement_set_f1` already `0.9756` 20/21 with `reference project`, `evidence 1/4` due to `.doc` piece-table, not matching)
- final matching accuracy (`Hybrid 0.797` vs deterministic `0.604` — isolated `0.797` not production, `0.604` is real pipeline with 1 evidence)
- final full-tender benchmark (`1394` pages, `64` files, `7919s` — not needed for contracts)
- OCR performance optimization (Phase A fix `ocr_needed_hint` already avoids `7919s` for `volume 1` `189` native pages)
- final AI acceptance score (`overall FAIL` due to `page_number_accuracy` `0.007`, `evidence_set_f1 0.4` — not needed for UI)

**They should work against stable contracts and mock incomplete AI outputs where necessary** (e.g., mock `MISSING` requirements as `REVIEW`, mock `ProcessingJob` progress).

---

## DEPENDENCIES / BLOCKERS

| Dependency | Owner | Why | Can work around it? | Current state |
|---|---|---|---|---|
| `POST /tenders/{id}/files` + `TenderDocument` persistence | **Backend** | Frontend upload needs API + storage | **Yes** — mock upload via `localStorage` + `sarai_gold_dataset.json` | **PROPOSED** — currently filesystem `ROOT` constant |
| `POST /process` + `GET /processing/status` async job | **Backend** | `run_document_intelligence` is synchronous `7919s`, blocks UI | **Yes** — mock `QUEUED→PROCESSING→COMPLETED` with `setTimeout` | **BLOCKED** — no async, no `job_id`, no polling |
| `LibreOffice` `.doc` extraction | **Backend/AI** | `SARAI ... rev1.doc` 40960 `Word 97-2003` needed `5598` chars for `4/4` evidences | **No** — now **FIXED** `libreoffice_headless_txt` `5598` `DOC_EXTRACTOR=libreoffice` | **EXISTING** (just wired, `b2af0fb`) |
| `Tesseract` 946-page OCR performance | **Backend/AI** | Full `1394` pages `7919s` makes E2E impractically slow, times out | **Yes** — Phase A `ocr_needed_hint` avoids OCR for `volume 1` `189` native pages (`0.62s` vs `3420s`) | **PARTIAL** — `volume 1` fixed, `Part 1/2` still `YES` (409/487 pages) will still be slow without hint |
| `Requirement extraction` `reference project` widening | **Backend/AI** | `REQ-L` missing without `reference project` | **No** — now **FIXED** `run_real_benchmark.py:470` `reference project` → `20/21` `0.9756` | **EXISTING** (`2163985`) |
| `Evidence extraction` `4/4` vs `1/4` | **Backend/AI** | Only `REQ-J` found via `FORM D` `Manufacturer Name`, other 3 need `consortium` `Hyosung` `Korea` from `.doc` `5598` | **Partial** — isolated `2-file` run gives `4/4`, full `64-file` run gave `1/4` before LibreOffice (now should be `4/4` after fix, but not yet proven in full E2E) | **PARTIAL** — `libreoffice` now extracts `5598` with all terms, but full E2E `1/4` was from old `246`-char run |
| `HybridMatcher` `0.797` vs deterministic `0.604` | **AI** | Frontend `Decision` currently uses deterministic `status.py` `0.604`, not `HybridMatcher` `0.797` | **Yes** — frontend mocks `0.797` as `REVIEW` | **BLOCKED** — `HybridMatcher` not wired into `run_real_benchmark.py` `evaluate_matching_and_decision()` (uses `status.py` directly) |

---

## IMPLEMENTATION ORDER

**STEP 1:** Freeze API/data contracts — `schemas/` + `app/models.py` + `app/api/routes.py` contract table above — **EXISTING**, frontend/backend agree on `Tender`/`Requirement`/`Evidence`/`Decision` shapes.

**STEP 2:** Backend tender/file + processing status foundation — `POST /tenders`, `POST /files`, `ProcessingJob` + `GET /processing/status` (async, mock `7919s` with progress) — **PROPOSED**, frontend can mock until ready.

**STEP 3:** Frontend application shell + tender list/upload — `app shell`, `Tender list` `GET /tenders`, `Upload` `POST /files` (mock), `Upload progress` — **can start now** (no AI).

**STEP 4:** Requirements + evidence APIs/UI — `GET /requirements`, `GET /evidence` — **EXISTING**, frontend builds tables with `status` pills and `provenance` links (mock `source_spans` `bbox` if needed).

**STEP 5:** Review/conflict center — `GET /requirements` `REVIEW` + `GET /audit` — **EXISTING**, frontend builds `Review` queue and `Human override` `POST /decision/override`.

**STEP 6:** Decision dashboard — `GET /decision` + `GET /explanation` — **EXISTING**, frontend builds big badge `REVIEW/NO_BID/BID` + `rules_triggered`.

**STEP 7:** Reports/export — `GET /export` **EXISTING**, add `PDF` export **PROPOSED**.

**STEP 8:** Real AI pipeline integration — wire `Tesseract` `ocr_needed_hint` + `LibreOffice` `.doc` + `reference project` (all done in `b2af0fb`/`2163985`) into async `POST /process` — **PARTIAL**, needs `run_document_intelligence` to use `inventory` hint for all PDFs (Phase A fix done) and `extract_evidence_rule_based` to use `libreoffice` text (now does for `2-file` test, but full `64-file` run still `1/4` before).

---

## GITHUB RULES

- **Canonical repo:** `C:\Users\EgyTech\Desktop\TenderMind` `origin https://github.com/Younes695/TenderMind.git` `branch main` — verified `git remote -v` `origin/main`.
- **Branch:** `main` — feature branches `feature/frontend-shell`, `feature/backend-upload`, `feature/ai-ocr` from `main`.
- **Feature branch workflow:** `git checkout -b feature/...` → `git add` → `git commit -m "..."` → `git push origin feature/...` → PR to `main` (no direct `main` pushes for AI logic).
- **PR workflow:** Require `python tests/test_doc_libreoffice.py` + `tests/test_pdf_ocr_routing.py` + `tests/test_hybrid_*` passing (`pytest -q` if available, else `python tests/...py`), no `MISSING→FAIL` or `Risk→NO_BID` invariant violations.
- **No direct modification of deterministic decision semantics:** `app/engines/status.py:1` `evaluate_all()` and `app/engines/decision.py:12` `decide()` are frozen — matcher never returns `BID/NO_BID`, only `PASS/FAIL/MISSING/REVIEW` at requirement level.
- **Coordination for AI pipeline contracts:** Any change to `schemas/requirement_schema.json`, `evidence_schema.json`, `matching_schema.json` or `REQUIREMENT_PATTERNS` must be PR with `docs/AI_Evaluation_Contract_v1.md` reference and `evaluation/run_real_benchmark.py` re-run (currently `0.9756` `20/21`).

---

## READY TO SEND

أرسل هذا للفريق Frontend + Backend (انسخ والصق):

```
السلام عليكم — TenderMind — هاندوف للتنفيذ المتوازي

إيه هو TenderMind؟
منصة لتقييم مناقصات Sarai 220/22kV GIS (SA/2018/HV2): رفع المناقصة → استخراج المستندات/OCR → استخراج المتطلبات → استخراج الأدلة → مطابقة → قرار حتمي BID/REVIEW/NO_BID → شرح + provenance → تقرير.

الـ Frontend يبدأ فوراً (مش محتاج يستنى AI كامل):
1. App shell + Tender list (GET /api/tenders — موجود)
2. Tender upload (POST /api/tenders/{id}/files — مقترح، اعمل mock بالـ drag-drop + sarai_gold_dataset.json 21 req/4 ev)
3. شاشة المعالجة مع timeline (UPLOADED→COMPLETED) و polling وهمي كل 2 ثانية (الـ Backend لسه synchronous 7919s)
4. Tender overview (GET /api/tenders/{id}/decision — top_blockers, risks)
5. جدول المتطلبات (GET /api/tenders/{id}/requirements — 21 صف، فلاتر category/mandatory/status)
6. لوحة الأدلة (GET /api/tenders/{id}/evidence — 4 أدلة + MissingEvidence)
7. مركز المراجعة والتعارضات (REVIEW + conflicts + POST /api/tenders/{id}/decision/override + GET /audit)
8. لوحة القرار (GET /api/tenders/{id}/decision + GET /api/tenders/{id}/explanation — badge REVIEW/NO_BID/BID)
9. صفحة التقرير والتصدير (GET /api/tenders/{id}/export — JSON + طباعة)
+ حالات التحميل والفراغ والخطأ + طبقة API client + بيانات وهمية حيث العقود غير جاهزة.

الـ Backend يبدأ فوراً:
1. توسيع app/api/routes.py: POST /tenders, POST /tenders/{id}/files, GET /tenders/{id}/files, POST /tenders/{id}/process, GET /tenders/{id}/processing/status (async job + progress 0-100)
2. عقود Pydantic: TenderDocument, ProcessingJob (schemas/)
3. ربط Tesseract المحلي (evaluation/tesseract_local_ocr.py — 946 صفحة، ara+eng) و LibreOffice 26.8.0.3 للـ .DOC القديم (SARAI ... rev1.doc 5598 حرف، الآن 4/4 أدلة في الاختبار المعزول) — تم تثبيتهم (b2af0fb) لكن run_document_intelligence لا يزال يعيد 1/4 في الـ E2E الكامل بسبب 246 حرف قديم
4. الحفاظ على القواعد الحتمية (app/engines/status.py + decision.py — MISSING≠FAIL)
5. اختبارات: tests/test_doc_libreoffice.py (5) + tests/test_pdf_ocr_routing.py (7) + hybrid (7)

الشاشات/المميزات الرئيسية: قائمة المناقصات، رفع، حالة المعالجة، نظرة عامة، جدول المتطلبات، تفاصيل المتطلب، لوحة الأدلة، عارض المصدر/الصفحة، مركز المراجعة، لوحة القرار، التقرير.

عقود API/البيانات: موجودة في app/api/routes.py (13 endpoint) + PROPOSED (8 endpoints للرفع والمعالجة) — اعتمدوا على schemas/requirement_schema.json و app/models.py.

ماذا يبدأوا به الآن: كل ما فوق — لا ينتظروا OCR مثالي، LLM نهائي، أو 0.93.

ماذا لا ينتظروا: OCR كامل 7919s، LLM كامل، 0.93، أو E2E كامل — اعملوا بالـ mock و sarai_gold_dataset.json.

الاعتمادات: رفع الملفات + حالة المعالجة غير المتزامنة — يمكن تجاوزها بالـ mock.

GitHub: C:\Users\EgyTech\Desktop\TenderMind origin https://github.com/Younes695/TenderMind.git branch main — اعملوا feature branches (feature/frontend-shell, feature/backend-upload) و PRs، لا تعدلوا decision semantics مباشرة.

التنسيق مع AI: أي تغيير في REQUIREMENT_PATTERNS أو schemas يجب PR مع evaluation/run_real_benchmark.py.

يلا نبدأ — Frontend يبني الـ shell + upload mock، و Backend يبني tendency/file + processing/status — نلتقي عند Requirements + Evidence APIs.
```

---

**Phase A validation (before handoff):**

- Tests `7` `tests/test_pdf_ocr_routing.py` **all passed** (`ocr_needed False → no Tesseract, True → routing, native remains native, scanned gets OCR, provenance correct, confidence available, fallback intact`).
- Smoke `4` files: `volume 1 of 2.pdf` `189 pages` `ocr_needed NO` → `Tesseract NOT invoked` `0 OCR 189 native 362803 chars 0.62s` **PROVED**; `Sarai RFP.pdf` `2 pages` `YES` → `Tesseract invoked` `1 OCR` **PROVED**; `Part 1 of 2.pdf` `409 pages` `YES` → `Tesseract invoked` **PROVED** (mocked 1 page to avoid 409×8s); `Drawings 1-SLD.pdf` `1 page` `YES` → `tesseract dpi200 fallback` **PROVED** (previous diagnostic `139M px → 3723 chars`).
- `git status` `On branch main up to date with origin/main, Changes not staged: evaluation/run_real_benchmark.py, tests/test_pdf_ocr_routing.py` — 2 files modified (Phase A fix).
- `git diff --check` `warning: LF will be replaced by CRLF` only — no whitespace errors.
- No unrelated files changed — only `evaluation/run_real_benchmark.py` (`extract_pdf_text` hint + `run_document_intelligence` hint) and `tests/test_pdf_ocr_routing.py` (new) + `docs/FRONTEND_BACKEND_HANDOFF.md` (new, to be created).

**No commit/push performed** as requested — handoff document created at `C:\Users\EgyTech\Desktop\TenderMind\docs\FRONTEND_BACKEND_HANDOFF.md` (this file).
