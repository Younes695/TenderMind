# TenderMind — Current Architecture State (Stage 4A audit, pre-change)

Date: Stage 4A entry. Based on direct inspection of `app/`, `evaluation/`, `frontend/src`,
`schemas/`, tests and docs. No code changed to produce this document.

## 1. Production path (what serves the UI today)

```
UI (React, vite proxy /api → :8000)
 → app/api/routes.py (single file, mounted /api)
 → POST /tenders/{id}/process → BackgroundTasks process_tender() (in-process, no queue)
 → app/processing.py: INVENTORY → EXTRACTION → PERSISTENCE
 → build_generic_extraction(use_llm=False)  [evaluation/generic_extraction.py]
 → TenderAnalysis JSON blob (validated vs schemas/tender_agnostic_schema.json)
 → GET /tenders/{id}/analysis (ad-hoc dict, no Pydantic)
 → TenderWorkspace evidence-first UI
```

- Async = in-process `BackgroundTasks` only. Restart loses QUEUED jobs. Concurrent re-POST → 409.
- Stages exist (`STAGES`, 8 names) but CLASSIFICATION / DETERMINISTIC / SEMANTIC / VALIDATION
  are **no-ops** (progress number + commit only). Progress percentages are **hardcoded**
  (5/10/20/40/60/80/90/95/100), not measured. Only real numbers: documents_total/processed/
  failed/unsupported.
- LLM is effectively **disabled** in prod: SEMANTIC only pings `check_ollama_available()`
  (never blocks); persistence calls `build_generic_extraction(use_llm=False)`.
- `PIPELINE_VERSION="1.0"`, `LLM_MODEL="qwen2.5:3b"`, `PROMPT_VERSION="Variant B"` hardcoded in
  `processing.py:18-20` (note: `ollama_matcher.DEFAULT_MODEL` says `qwen3:4b` — mismatch, dead code).
- Failure isolation is GOOD: per-document try/except; all-ok→COMPLETED, some-failed→PARTIAL,
  all-failed→FAILED, unsupported-only→PARTIAL. One bad document never destroys the analysis.

## 2. Evaluation-only path (must stay intact, never auto-run in prod)

- `evaluation/run_real_benchmark*.py`, `evaluation/stage3*/` runners, `evaluation/stage3k/run_3k.py`
  (Experiments A/B), gold fixtures, prompt-hash assertions. Heavy Sarai/Azure OCR is offline-only
  (`azure_doc_intel.py` never imported by prod path). Normal path uses local Tesseract **only**
  for scanned PDFs; text PDFs use fitz directly. `app/processing.py` job inventory omits
  `ocr_needed`, so its PDF hint defaults to `None` (try-Tesseract-first) — minor inefficiency.
- Frozen: Variant B `LLM_SYSTEM_PROMPT` bytes, hash `9aa3e11254f672cd`
  (`evaluation/llm_generic_extraction.py:82-129,167-170`), asserted in `stage3j/run_3j.py:77`.
  C/D append-only via `+ "\n\n" +`. `two_stage_pipeline.py` (218L) is the validated reference:
  flag `TENDERMIND_TWO_STAGE_LLM`, `discover_candidates`, `normalize_candidate` (minimal contract),
  `post_process` (deterministic binding, 1:1 evidence, canonical IDs).

## 3. Map of findings (spec letters)

A) **Production path**: §1 above. UI → routes → BackgroundTasks → processing → analysis blob.
B) **Evaluation-only path**: §2 above + `evaluation/generic_extraction_v2.py` (dead clone),
   `chunk_documents_inner` (test-only duplicate), `stage3*/` one-off runners.
C) **Duplicated logic**: ingestion ×2 (app/processing vs evaluation ingest; double I/O —
   processing re-ingests via `build_generic_extraction` after its own extraction loop);
   chunkers ×2; Ollama prompt-senders ×4 with identical transport settings;
   `Requirement`/`Evidence` ORM tables (legacy seed universe) vs `TenderAnalysis` JSON blob
   (pipeline universe) — **two disconnected data universes**; `app/matchers/*` unreachable
   from any route (dead code in prod).
D) **Hardcoded assumptions**: fake progress %; `PIPELINE_VERSION/LLM_MODEL/PROMPT_VERSION`;
   `B_MAX_CALLS`-style ceilings only in eval runners; `TENDER_SARAI_PATH` env fallback;
   `C:\Users\EgyTech\...` literals live only in eval runners/docs (NOT in `app/`).
E) **Hidden coupling**: prod `processing.py` imports `evaluation.run_real_benchmark`
   (extract_pdf/docx/xls), `evaluation.llm_generic_extraction.check_ollama_available`,
   `evaluation.generic_extraction` (build + schema validate). Any eval refactor can break prod.
   API bugs (out of 4A scope, recorded): `GET evidence` / `missing-evidence` ignore tender_id;
   `POST decision/recompute` non-idempotent; `ProcessingJob` counters typed Float.
F) **Scalability bottlenecks**: sequential per-document extraction in one background thread;
   sequential per-candidate LLM calls (~5.5s each; 2545 candidates ≈ 3.9h); full-table scans on
   evidence/audit endpoints (no pagination); SQLite single-writer; per-stage commits.
G) **Second-model invasiveness**: direct `requests.post(.../api/chat)` inside
   `ollama_matcher.py:174` and 4 eval senders; `HybridMatcher` hard-defaults `OllamaMatcher()`;
   model/version constants scattered across `processing.py`, both matchers, eval helpers, DB
   columns. **No provider registry, no factory, no router.**

## 4. Other load-bearing facts

- Storage: `get_storage_root()` (`TENDERMIND_STORAGE_ROOT` else `<root>/uploads`), layout
  `<root>/<tender_id>/<filename>`; DB keeps absolute `source_path` + size + original name.
- Config surface: `DATABASE_URL`, `TENDERMIND_STORAGE_ROOT`, `TENDER_SARAI_PATH`,
  `TENDERMIND_OLLAMA_MODEL/ENDPOINT/TIMEOUT` (+matcher variants), `OPENAI_*` (gated, unwired),
  `TENDERMIND_MATCHER_PROVIDER/TENDERMIND_ENABLE_LLM`. `TENDERMIND_TWO_STAGE_LLM` exists only
  in eval + its test.
- Decision engine (`app/engines/decision.py`) DOES auto-map to BID/REVIEW/NO_BID, but it is
  **orphaned**: reachable only via legacy `/decision*` routes; frontend never calls them (0 hits);
  pipeline never calls `decide()`; UI stays neutral ("Not available"). Semantics must not change.
- Frontend contract: `frontend/src/api/client.js` sole surface; analysis shape consumed =
  `{tender,documents,requirements,evidence,deadlines,commercial,risks,derived_features,
  processing,status,...version fields}`; handles COMPLETED/PARTIAL/FAILED/QUEUED/PROCESSING +
  COMPLETE/PARTIAL/FAILED/UNSUPPORTED docs; gaps derived client-side; GoNoGo shows counts only.
  Frontend tests: 3 files, 41 tests, mocked fetch. No `localhost` in components (proxy + env).
- Format support (via `run_real_benchmark.py` + `processing.py`): PDF (fitz+Tesseract routing),
  DOCX (python-docx), DOC (LibreOffice→olefile fallback), XLS (xlrd, 50 rows/sheet), XLSX
  (openpyxl `data_only`, `|`-joined, 5000-char cap/sheet, no table-structure parsing), TXT/LOG/CSV
  (utf-8 ignore). Images/archives/CAD → UNSUPPORTED (explicit, truthful).
- Provenance today: deterministic first-match (generic), Stage 3C per-chunk ID-correction +
  cross-chunk rejection for LLM path, `assign_canonical_ids` with chunk-prefix drift guard,
  3K `post_process` same-candidate binding + 1:1 evidence (`fact=summary`).
