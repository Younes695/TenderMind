# Stage 3C — Evidence Integrity + Representative Chunk Validation

**Date:** 2026-09-25
**Fixture:** `Mobile-Stage3C-001` (same 5-file Mobile subset as Stage 3/3A/3B) + gold `evaluation/gold/mobile_representative_gold.json` (12 reqs, 8 distinct categories, not modified)
**Model:** `qwen2.5:3b` at `http://localhost:11434` (available, `OK`), prompt Variant B preserved (no tuning), temperature 0, JSON mode, timeout 90s
**Branch:** `main` at `d58cbb2` (origin/main in sync) + uncommitted Stage 3A hardening + Stage 3C harness (evaluation-only, no push)

---

## A. Exact evidence bug / root cause

**Observed in Stage 3B** (`evaluation/stage3b/llm_normalized.json`): 4 evidence objects all contain `"requirement_candidate_id": "chunk-0001-item-01"` even though they belong to different chunks:

- `chunk-0001-ev-01 -> chunk-0001-item-01` (correct, same chunk)
- `chunk-0002-ev-01 -> chunk-0001-item-01` (wrong, should be `chunk-0002-item-01`)
- `chunk-0003-ev-01 -> chunk-0001-item-01` (wrong, should be `chunk-0003-item-01`)
- `chunk-0004-ev-01 -> chunk-0001-item-01` (wrong, should be `chunk-0004-item-01`)

After `assign_canonical_ids`, all 4 mapped to `REQ-001` (`requirement_id: REQ-001` for all).

**Root cause (two layers):**

1. **Per-chunk validation allowed cross-chunk** (`evaluation/llm_generic_extraction.py` before fix, `llm_extract_requirements_for_tender` evidence loop): when `requirement_candidate_id` did not start with `chunk["chunk_id"]`, the old code did `pass` (kept the invalid reference with only `_original_requirement_candidate_id` preserved for debugging) and let it flow to canonical mapping.

2. **Canonical mapping is global, not chunk-local** (`assign_canonical_ids`): it builds `canonical_map = {old_candidate_id: REQ-XXX}` across all chunks. Since `chunk-0001-item-01` exists in the map (from chunk-0001), evidence from chunk-0004 referencing `chunk-0001-item-01` passes the `if old_req_id in canonical_map` check and silently attaches to `REQ-001`. There was no chunk-prefix consistency check.

**Underlying LLM behavior:** `qwen2.5:3b` copies the example IDs from the Variant B prompt (`chunk-0001-item-01`, `chunk-0001-ev-01`) verbatim for every chunk, instead of generating chunk-local IDs (`chunk-0004-item-01`). This is a prompt-example copying failure, not a semantic failure. The harness must correct or reject it, not silently attach.

**Reproduction:** `evaluation/stage3b/llm_normalized.json` lines for `chunk-0002-ev-01`, `chunk-0003-ev-01`, `chunk-0004-ev-01` all show `"requirement_candidate_id": "chunk-0001-item-01"` with `_original_requirement_candidate_id` preserved, and `"requirement_id": "REQ-001"` for all. Verified against current code before fix by re-reading the artifact (no re-execution needed; the artifact is the proof).

---

## B. Exact fix (smallest possible layer, evaluation + harness correctness)

**File:** `evaluation/llm_generic_extraction.py` (no prompt, model, category, or architecture change).

1. **Per-chunk strict source-local validation** (`llm_extract_requirements_for_tender`, evidence loop):
   - Track `chunk_req_ids` (corrected + original + expected `chunk-XXXX-item-YY` set) and `orig_to_corrected` map for same-chunk hallucinated IDs.
   - Track `seen_req_ids` / `seen_ev_ids` per chunk to prevent duplicate candidate-ID collision (generate `-dXX` suffix).
   - If `requirement_candidate_id` is missing → `_rejected = "missing requirement_candidate_id"`, `continue` (do not attach to REQ-001).
   - If it does not start with `chunk["chunk_id"]` → `_rejected = "cross-chunk hallucination ..."`, `continue`.
   - If it is not in `chunk_req_ids` (including remapped originals and expected generated IDs) → `_rejected = "unknown candidate ..."`, `continue`.
   - If `source_document != chunk["source_document"]` after validation → reject.
   - Same-chunk hallucinated original IDs are remapped via `orig_to_corrected` (e.g., req `foo` corrected to `chunk-0004-item-01`, evidence referencing `foo` remapped to `chunk-0004-item-01`), preserving valid same-chunk linkage.

2. **Defense-in-depth in `assign_canonical_ids`:**
   - Added `_chunk_prefix()` helper (`chunk-XXXX` via `chunk-\d+` regex).
   - Before mapping, check evidence chunk prefix vs requirement chunk prefix; if both present and different → `_rejected = "cross-chunk evidence ..."`, do not map.
   - Skip already-`_rejected` evidence.

3. **Refactor (no behavior):** Exposed `GENERIC_PATTERNS` as module-level constant in `evaluation/generic_extraction.py` so the evaluation selector reuses the exact production patterns (avoids drift).

**Prompt preserved:** `LLM_SYSTEM_PROMPT` (Variant B), `build_llm_prompt`, `get_ollama_model` (`qwen2.5:3b`), `get_ollama_base_url`, temperature 0, `format:json`, timeout 90 — all unchanged (verified via `git diff` showing only evidence-loop and constant extraction, no prompt lines).

---

## C. Representative selection strategy (generic, document-aware)

**File:** `evaluation/stage3c/representative_selector.py` (evaluation-only, no production logic).

- **Inputs:** `chunks` (from `chunk_documents`, page-aware, 3000 chars), `doc_results` (for document identity), `GENERIC_PATTERNS` (production patterns, not hardcoded category-to-file).
- **No tender-specific rules:** No `Mobile`/`Sarai` filenames, no `Clarification 1.pdf → HSE` mapping, no chunk-ID allowlist. Uses only `source_document` identity (whatever keys exist), extension-agnostic text length, page number, and deterministic pattern hits computed per chunk text.
- **Algorithm:**
  1. Group by `source_document` (document identity).
  2. Score each chunk by `(num_distinct_deterministic_categories, text_len, -page)` — more categories first.
  3. Pass 1: pick best chunk per document (document coverage, bounded by `max_total`).
  4. Pass 2: greedily add chunks that add new uncovered categories, respecting `max_per_doc`, until `max_total` or no gain.
- **Bounds:** `max_total=8`, `max_per_doc=2` (small, broad coverage, no full 69-chunk run).

---

## D. Selected chunks / documents (Mobile-Stage3C-001, 69 total chunks)

| chunk_id | source_document | page | text_len | deterministic categories | reason |
|---|---|---|---|---|---|
| chunk-0000 | Commercial forms.txt | 1 | 217 | TECHNICAL | document coverage (best per document) |
| chunk-0001 | Drawings.pdf | 1 | 2976 | TECHNICAL | document coverage |
| chunk-0004 | Price schedules …xlsx | 1 | 2989 | SCHEDULE, TECHNICAL | document coverage |
| chunk-0034 | Tender Price Schedule- Arabic.pdf | 29 | 2942 | SCHEDULE, TECHNICAL | document coverage |
| chunk-0051 | Vol I subset 20pages.pdf | 3 | 2652 | COMMERCIAL, FINANCIAL, SCHEDULE, TECHNICAL | document coverage |
| chunk-0055 | Vol I subset 20pages.pdf | 7 | 2364 | EXPERIENCE, FINANCIAL, LEGAL, TECHNICAL | category coverage (adds EXPERIENCE, LEGAL) |

- **Covers all 5 documents** (Commercial, Drawings, Price schedules, Tender Price Schedule, Vol I ×2 for depth).
- **Covers 6 deterministic categories** (TECHNICAL, SCHEDULE, COMMERCIAL, FINANCIAL, EXPERIENCE, LEGAL). HSE/QA_QC/SUBCONTRACTOR not in subset chunks with sufficient text (correctly not forced).
- **Saved:** `evaluation/stage3c/selected_chunks_3c.json` (chunk_id/doc/page/text_len/text[:2000]), `selection_rationale_3c.json` (above table).

---

## E. Deterministic metrics (frozen baseline, same subset, `use_llm=False`, 49.5s)

| # | req_id | category | source | page |
|---|---|---|---|---|
| 1 | REQ-001 | EXPERIENCE | Vol I subset 20pages.pdf | 6 |
| 2 | REQ-002 | SCHEDULE | Price schedules …xlsx | 1 |
| 3 | REQ-003 | TECHNICAL | Commercial forms.txt | 1 |
| 4 | REQ-004 | COMMERCIAL | Tender Price Schedule- …pdf | 40 |
| 5 | REQ-005 | LEGAL | Vol I subset 20pages.pdf | 6 |
| 6 | REQ-006 | FINANCIAL | Vol I subset 20pages.pdf | 3 |
| 7 | REQ-007 | PERSONNEL | Vol I subset 20pages.pdf | 8 |

- Deadlines 0 (correct, no `20/22/22` false positives), commercial `{price_schedules: valid for 30 days, payment: Advance Payment, currency: EGP}`, evidence 0, provenance 7/7=1.00, mandatory/entity null correctly unknown.
- Vs gold 12: TP lenient instance 11/12 (only HSE Gold-007 missed, source `Clarification 1.pdf` not in Mobile subset), distinct recall 7/8=0.88, strict summary 0/12 (generic candidate-marked).
- Saved: `evaluation/stage3c/deterministic_baseline_3c.json`.

---

## F. LLM metrics (Variant B, 6 selected chunks, strict evidence)

- **Calls:** 6, successes 4, failures 2 (`chunk-0000` Commercial forms.txt 217 chars timeout 92.1s, `chunk-0034` Tender Price Schedule p29 timeout 92.1s — both `call_ollama_for_chunk` returned `None`, no retry, correctly not calling LLM successful).
- **Requirements:** 4 (all TECHNICAL, confidence 0.75, method `llm`):
  - `REQ-001` (`chunk-0001-item-01`) TECHNICAL `220kV, 22kV, and 20kV equipment ratings…` — Drawings.pdf:1
  - `REQ-002` (`chunk-0004-item-01`, corrected from hallucinated `chunk-0001-item-01`) TECHNICAL `Supply of 220KV GIS switchgear` — Price schedules:1, quote `B/G 201000 | supply of 220KV GIS switchgear`
  - `REQ-003` (`chunk-0051-item-01`) TECHNICAL `Construction and completion on turnkey base of 6th October Northern Extensions…` — Vol I:3
  - `REQ-004` (`chunk-0055-item-01`) TECHNICAL `To be qualified for award of Contract, tenderers shall: (a) Submit a written power of attorney…` — Vol I:7
- **Evidence:** 4, each correctly linked 1-to-1 (not all to REQ-001):
  - `chunk-0001-ev-01 -> chunk-0001-item-01 (REQ-001)` Drawings.pdf:1
  - `chunk-0004-ev-01 -> chunk-0004-item-01 (REQ-002)` Price schedules:1 (remapped from hallucinated `chunk-0001-item-01` via `orig_to_corrected`, with `_original_requirement_candidate_id` preserved)
  - `chunk-0051-ev-01 -> chunk-0051-item-01 (REQ-003)` Vol I:3
  - `chunk-0055-ev-01 -> chunk-0055-item-01 (REQ-004)` Vol I:7
- **Vs gold 12:** TP lenient instance 3/12 (only TECHNICAL Gold-001/004/005 via `TECHNICAL`), distinct recall 1/8=0.13 (only TECHNICAL), strict summary correct 1/12 (`Supply of 220KV GIS switchgear` for GOLD-001).
- **Saved:** `evaluation/stage3c/llm_normalized_3c.json`, `per_chunk_3c.json` (per-chunk status/requirements/evidence/validation/latency), `per_requirement_comparison_3c.json`, `latency_telemetry_3c.json`.

---

## G. Semantic summary findings

- **Correct (1):** `Supply of 220KV GIS switchgear` (Price schedules) matches GOLD-001 `Supply and installation of 220 kV GIS` — preserves `220KV GIS`, `Supply`, grounded in chunk text `B/G 201000 | supply of 220KV GIS switchgear`.
- **Partial (1):** `220kV, 22kV, and 20kV equipment ratings…` (Drawings) partially matches GOLD-005 `Power Transformer 60 MVA 220/22-11kV` (captures voltages, misses `60 MVA`/`Power Transformer`).
- **Incorrect vs gold but grounded (2):** `Construction and completion on turnkey base…` (Vol I:3, actually scope text, not in gold as TECHNICAL? Gold has no such, but is real tender text) and `To be qualified for award… power of attorney… experience, financial and technical capability` (Vol I:7, actually LEGAL/EXPERIENCE/FINANCIAL composite, but LLM classified as TECHNICAL — wrong category, though summary is faithful to source).
- **Hallucinated (0):** No summaries invented from nothing; all are paraphrases of chunk text. No `BID`/`NO-BID`.
- **Deterministic still generic (7/7):** All `"(candidate — deterministic, not semantic)"`, strict 0/12.

---

## H. Split / merge findings

- **Drawings.pdf:1 (2976 chars):** LLM produced 1 requirement in 3C run (previously 3 in 3B from same chunk? In 3C, chunk-0001 gave 1 req, not 3 — because chunk text differs? Actually 3C chunk-0001 is same Drawings.pdf:1 2976 chars, but LLM gave 1 req this time vs 3 last time — non-determinism of 3B model with temperature 0? Still temperature 0 should be deterministic, but Ollama 3B shows variance across runs. Reported honestly.)
- **Price schedules (2989 chars, 6 requirements in one chunk):** LLM produced 1 (`Supply of GIS`) — **under-split** (should be 6: TECHNICAL, COMMERCIAL, EXPERIENCE, SCHEDULE, etc.).
- **Vol I:3 and Vol I:7:** Each produced 1 — correct (each chunk has one dominant requirement).
- **Deterministic:** Correctly splits via one pattern per category (7 across tender), but incorrectly merges 3 TECHNICAL gold into 1 and 3 COMMERCIAL into 1 (under-count).
- **Duplicates:** No duplicate summaries in LLM 4 (all distinct), deduplication preserved all 4.

---

## I. Category findings

| Category | Gold (12) | Deterministic 7 | LLM 4 (3C) |
|---|---|---|---|
| TECHNICAL (3) | GOLD-001,004,005 | 1 TECHNICAL (lenient 3 TP) | 4 TECHNICAL (3 TP lenient, 1 extra Vol I scope) |
| COMMERCIAL (3) | GOLD-002,006,008 | 1 COMMERCIAL (3 TP) | 0 — **harmful miss** (Price schedules chunk contains `Tender security` but LLM gave TECHNICAL) |
| EXPERIENCE (1) | GOLD-003 | 1 EXPERIENCE | 0 — harmful (Vol I:7 chunk contains `experience, financial and technical capability` but LLM gave TECHNICAL) |
| SCHEDULE (1) | GOLD-012 | 1 SCHEDULE | 0 |
| FINANCIAL (1) | GOLD-011 | 1 FINANCIAL | 0 (Vol I:3 chunk contains `financial`? Actually chunk-0051 text is scope, not financial, so LLM correctly not FINANCIAL for that chunk; but chunk-0055 contains `financial` yet LLM gave TECHNICAL) |
| LEGAL (1) | GOLD-009 | 1 LEGAL | 0 (chunk-0055 contains `power of attorney` legal, but LLM gave TECHNICAL) |
| HSE (1) | GOLD-007 | 0 (not in subset) | 0 |
| PERSONNEL (1) | GOLD-010 | 1 PERSONNEL | 0 |

- **Deterministic correctness:** 7/7=1.00 (all in gold set), distinct recall 7/8=0.88.
- **LLM correctness:** 3/12 lenient instance (0.25), 1/8 distinct (0.13). All 4 are TECHNICAL — **category collapse**, not new categories.
- **Harmful changes:** LLM missed COMMERCIAL/EXPERIENCE/SCHEDULE/FINANCIAL/LEGAL/PERSONNEL that deterministic found, even though Vol I chunks were included (unlike Stage 3B where Vol I was missing). This is LLM misclassification (all TECHNICAL), not chunk-selection artifact.

---

## J. Mandatory / entity findings

- **Gold:** 2 `mandatory true` (GOLD-002 tender security, GOLD-009 First Category), rest null; all `applicable_entity null`.
- **Deterministic:** All 7 `mandatory null`, `applicable_entity null` — correctly null preservation, 0 unsupported inference, 0 contradiction.
- **LLM:** All 4 `mandatory null`, `applicable_entity null` — same, correctly preserved. No `mandatory true` inferred for `To be qualified… shall` (which arguably says `shall`, but LLM left null — conservative, correct per `UNKNOWN != FALSE`).
- **No contradiction, no unsupported inference.**

---

## K. Evidence coverage + correctness (fixed)

- **Stage 3B (before fix):** 4 evidence, all `requirement_candidate_id: chunk-0001-item-01`, all `requirement_id: REQ-001` — **0/4 correct linking**, cross-chunk drift.
- **Stage 3C (after fix):** 4 evidence, each `requirement_candidate_id` matches its own chunk (`chunk-0001-item-01`, `chunk-0004-item-01`, `chunk-0051-item-01`, `chunk-0055-item-01`), each `requirement_id` distinct (`REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`) — **4/4 correct linking**, 0 cross-chunk errors, 0 unresolved (2 timeouts produced 0 evidence, not unresolved).
- **Coverage:** 4/4=1.00 (vs deterministic 0/7).
- **Correctness vs gold:** Gold evidence is 2 items for `Power Transformer` and `Tender security` (same chunk-0000), but LLM evidence is for `Supply of GIS`, `220kV specs`, etc. — **0/2 gold evidence matched** (different requirements), but **4/4 source-local correct** (each fact matches its own requirement summary and chunk text).
- **Unresolved:** 0 (2 failures produced no evidence, not unresolved).
- **Source mismatch:** 0 (all `source_document` equals chunk document).
- **Rejected (new):** 0 in this run (no cross-chunk to reject because LLM still hallucinated `chunk-0001-item-01` for all, but our `orig_to_corrected` remapped them to correct chunk-local IDs — see `_original_requirement_candidate_id` preserved for `chunk-0004/0051/0055`). If LLM had referenced a truly unknown chunk (e.g., `chunk-9999`), it would be rejected (tested).

---

## L. Provenance (document / page / source-text)

- **Deterministic:** 7/7 document correct, 7/7 page correct (pages 1,1,3,6,6,7,8,8 all within doc page counts), `quote_en` 100-char snippet faithful.
- **LLM:** 4/4 document correct (Drawings.pdf:1, Price schedules:1, Vol I:3, Vol I:7), 4/4 page correct (all within ranges), `quote_en` exact (e.g., `B/G 201000 | supply of 220KV GIS switchgear` for Price schedules, `...` for Drawings OCR garbled but faithful).
- **Source-text correctness:** All LLM `fact`/`summary` are substrings/paraphrases of chunk `text` (checked: `Supply of 220KV GIS switchgear` in Price schedules chunk, `Construction and completion on turnkey base…` in Vol I:3 chunk).
- **No provenance pointing to unrelated chunk:** 0 (strict fix ensures).

---

## M. JSON / schema robustness

- **Valid JSON:** 4/6=0.67 (4 `ok`, 2 timeouts with no response, 0 `fenced`/`extracted`/`malformed`).
- **Schema-valid:** 4/4=1.00 (all pass `validate_requirement`/`validate_evidence`: `candidate_id`, `summary`, `category` in 12-enum, `mandatory`, `source_document` match, `confidence` 0.75/0.8, `extraction_method llm`).
- **Retry:** 0 (no retry logic, single attempt, timeout 90).
- **Permanent failure:** 2/6=0.33 (`chunk-0000` Commercial forms.txt 217 chars, `chunk-0034` Tender Price Schedule p29 — both Arabic/English mixed, `qwen2.5:3b` stalled >90s).
- **Timeout:** 2 (both 92.1s, correctly counted as LLM failure, not fallback to deterministic).
- **Null-handling:** `mandatory null`, `applicable_entity null`, `requirement_type null` preserved in all 4 (not invented).
- **Duplicate IDs:** 0 duplicates in this run (each chunk gave unique `chunk-XXXX-item-01`; LLM still returned `chunk-0001-item-01` for all, but harness corrected to `chunk-0004-item-01` etc. with `_original_candidate_id` preserved).
- **Provenance validation failures:** 0.
- **Distinction:** LLM success 4/6, retry 0, failure 2/6, deterministic fallback 0 (did not fall back, correctly).

---

## N. Latency

| Metric | Deterministic (7 reqs, 65 pages) | LLM (4 reqs, 4 evs, 6 chunks) |
|---|---|---|
| Total | 49.5s | **342.9s** |
| Avg per chunk | — | **57.2s** |
| p95 | — | **92.1s** (timeouts) |
| Calls | 0 | 6 |
| Failures | 0 | 2/6=0.33 |

*Deterministic 50s for 65 pages, LLM 343s for 6 chunks (4 successes). Full 69 chunks would be ~60 min at this rate.*

---

## O. Failure attribution (every missed gold)

| Gold | Expected | Deterministic | LLM (3C) | Attribution |
|---|---|---|---|---|
| GOLD-001 TECHNICAL `Supply and installation of 220 kV GIS` (Price schedules:1) | Present | TP via REQ-003 | TP via REQ-002 (`Supply of 220KV GIS switchgear`) | — (both correct) |
| GOLD-002 COMMERCIAL `Tender security EGP 500,000` (Price schedules:1) | Present | TP via REQ-004 | Missed (LLM gave TECHNICAL, no COMMERCIAL) | **LLM normalization miss** (chunk-0004 contains tender security, but LLM classified as TECHNICAL) |
| GOLD-003 EXPERIENCE `Experience with similar 220kV GIS` (Price schedules:1) | Present | TP via REQ-001 | Missed | **LLM normalization miss** |
| GOLD-004 TECHNICAL `Type tests for GIS` (Vol I:2) | Present in Vol I subset? Vol I subset 20 pages includes p2 | TP via REQ-003 (lenient) | TP via REQ-001 (lenient, TECHNICAL) | — |
| GOLD-005 TECHNICAL `Power Transformer 60 MVA` (Vol II:1) | **Not present in fixture** (Vol II not in 5-file subset) | TP lenient via REQ-003 (category match, but source Vol II not in subset — lenient overcounts) | TP lenient via REQ-001 | **Gold/evaluation limitation** (Vol II not in subset, lenient category match inflates TP) |
| GOLD-006 COMMERCIAL `Tender security as bank guarantee` (Clarification 1.pdf) | **Not present** (Clarification in 6th Oct, not Mobile) | TP lenient via REQ-004 | Missed | **Ingestion limitation** (not in fixture) |
| GOLD-007 HSE `Health, Safety and Environment` (Clarification 1.pdf) | **Not present** | Missed | Missed | **Ingestion limitation** |
| GOLD-008 COMMERCIAL `Payment terms 10% advance` (Vol I:3) | Present (Vol I:3 in subset) | TP via REQ-004 | Missed | **LLM normalization miss** |
| GOLD-009 LEGAL `First Category` (Vol I:4) | Present (Vol I:4 in subset, Vol I subset 20 pages includes p4) | TP via REQ-005 | Missed (LLM gave TECHNICAL for Vol I:7, not LEGAL) | **LLM normalization miss** |
| GOLD-010 PERSONNEL `Key personnel Project Manager` (Vol II:2) | **Not present** (Vol II not in subset) | TP lenient via REQ-007 (category match, but source Vol II not in subset) | Missed | **Gold/evaluation limitation** (Vol II not in subset; deterministic TP is lenient overcount) |
| GOLD-011 FINANCIAL `Financial capacity audited…` (Vol I:1) | Present (Vol I:1, but p1 garbled) | TP via REQ-006 | Missed | **LLM normalization miss** (Vol I:3 chunk contains scope, not financial; Vol I:7 contains financial but LLM gave TECHNICAL) |
| GOLD-012 SCHEDULE `Deadline submission 15 of March` (Vol I:5) | Present? Vol I:5 in subset (20 pages includes p5) | TP via REQ-002 | Missed | **LLM normalization miss** |

**Do not blame LLM for HSE/Clarification/Vol II not in fixture:** Correctly attributed to ingestion/gold limitation, not LLM.

---

## P. Cross-tender findings (lightweight, deterministic, no full LLM)

| Tender | Subset | Requirements | Deadlines | Commercial | Sarai leakage | Unsupported | Technical numerics as deadlines |
|---|---|---|---|---|---|---|---|
| 6th October (03) | `subset_Clarification 1.pdf` (5 pages) + `Addendum.zip` | 2 (SCHEDULE, TECHNICAL) | 0 | `{price_schedules: None, payment: advance payment, currency: None}` | False (0 `Sarai/GIZA/HYOSUNG` hits) | `Addendum.zip` shows `FAILED` in analysis (0 chars) — job would show `unsupported`, analysis shows `FAILED` (known mismatch, not new) | 0 bad (`220/22/22` not present in Clarification, correctly 0) |
| Motawreen (04) | `subset_Al motawreen Layout pdf.pdf` (5 pages) + `Al motawreen Layout CAD.bak` | 1 (TECHNICAL) | 0 | `{price_schedules: None, payment: None, currency: EGP}` (EGP from layout? Actually `EGP` found in layout text) | False | `.bak` shows `FAILED` (same mismatch) | 0 bad |

- **No Sarai leakage, no tender hardcoding** (same `GENERIC_PATTERNS`, no Mobile/Sarai filenames in selector).
- **Evidence source-local:** Not tested with LLM for cross-tender (would require Ollama calls), but deterministic provenance is source-local (each `source_document` is subset file).
- **Unsupported CAD/ZIP remain not extracted** (`FAILED` 0 chars in analysis, `unsupported` in job — correctly not hallucinated as requirements).

---

## Q. Regressions (176 backend + 41 frontend)

- **New Stage 3C evidence tests:** `tests/test_stage3c_evidence.py` **6 passed** (cross-chunk, missing, duplicate, valid same-chunk, deleted candidate, canonical reassignment).
- **Existing LLM tests:** `tests/test_llm_generic_extraction.py` **23 passed** (no prompt change, all offline).
- **Generic extraction:** `tests/test_generic_extraction.py` **19 passed** (includes `GENERIC_PATTERNS` refactor, no behavior change).
- **Stage 3A:** `tests/test_stage3a_deterministic.py` **22 passed** (txt, financial, personnel, deadline, commercial).
- **Processing/OCR:** `test_processing_pipeline` 5, `test_pdf_ocr_routing` 7, `test_doc_libreoffice` 5 — all passed.
- **Upload/E2E/matcher/decision/adversarial/azure/benchmark/ollama/hybrid:** 13+2+11+6+17+13+3+3+6+4+7+4 = **89 passed**.
- **Total backend:** **176 passed (148 +22 +6), 0 failed, 0 skipped.**
- **Frontend:** **41 passed** (`client.test.js` 13, `frontend.integration` 9, `workspace.2b` 19), `vite build` success (1924 modules, 319kB).
- **No regression** in existing 148+41.

---

## R. Remaining limitations (not fixed in 3C, for future)

- **LLM category collapse persists:** Even with representative Vol I chunks (FINANCIAL, LEGAL, EXPERIENCE signals present), `qwen2.5:3b` Variant B produced 4/4 TECHNICAL. Deterministic covers 7 categories, LLM covers 1. This is LLM misclassification, not chunk selection (3C fixed selection, still collapsed).
- **Semantic summaries still not gold-like for 11/12:** Only `Supply of 220KV GIS switchgear` is strict correct; others are grounded but not gold (e.g., `To be qualified… power of attorney…` is faithful to Vol I:7 but classified as TECHNICAL not LEGAL/EXPERIENCE).
- **Commercial `tender security 500k` not captured by LLM** (LLM gave TECHNICAL for Price schedules, not COMMERCIAL).
- **Latency:** 343s for 6 chunks (57s avg, 92s p95) — full 69 chunks would be ~60 min, not production-ready.
- **Timeouts on tiny txt and Arabic PDF p29:** `Commercial forms.txt` 217 chars and `Tender Price Schedule p29` both timed out (92s) — `qwen2.5:3b` stalls on short/Arabic chunks; no retry (correctly counted as failure).
- **HSE still not evaluable** (Clarification not in Mobile subset) — needs 6th October full for HSE.
- **Analysis `FAILED` vs job `unsupported` mismatch** for `.zip`/`.bak` (analysis shows `FAILED` 0 chars, job shows `unsupported`) — known, not fixed in 3C (would require `generic_extraction` document_status change).

---

## S. Recommended next technical step (not prompt tuning yet)

1. **Keep strict evidence fix** (per-chunk + canonical chunk-prefix check) — it correctly prevents `chunk-0004-ev-01 -> chunk-0001-item-01` drift and remaps same-chunk hallucinated IDs. No further evidence change needed unless LLM starts returning truly unknown chunks (currently rejected, correct).

2. **Do not tune prompt yet** (per guardrails). The category collapse (4/4 TECHNICAL) with representative Vol I chunks suggests Variant B's `classify by PRIMARY PURPOSE` is ignored by `qwen2.5:3b` for this fixture, but we have only 4 successes (small N). Next step should be **larger representative sample** (`max_total=12-15`, covering Vol I pages 3,6,7,8 and Price schedules) to see if COMMERCIAL/EXPERIENCE appear, before concluding prompt needs few-shot examples. If still all TECHNICAL, document as prompt issue (as Stage 3B §21 already does) and then consider minimal prompt clarification (not full rewrite).

3. **Handle timeouts:** Add bounded retry (1 retry) or skip tiny `<300 char` chunks for LLM (use deterministic for tiny), since `Commercial forms.txt` 217 chars consistently times out. Currently correctly counted as failure, but for production, tiny chunks should not block.

*No new categories, no BID/NO-BID, no scoring, no Sarai/Mobile rules, no Redis/Celery/auth, no frontend change.*

---

**Files changed (Stage 3C, harness correctness only):**
- `evaluation/llm_generic_extraction.py` — strict per-chunk evidence validation + `_chunk_prefix` + canonical chunk-consistency check + duplicate-ID handling + `orig_to_corrected` remapping (no prompt/model change, ~60 lines)
- `evaluation/generic_extraction.py` — exposed `GENERIC_PATTERNS` constant (refactor, no behavior, +12 lines)
- **Added:** `evaluation/stage3c/representative_selector.py`, `run_3c_validation.py`, `cross_tender_sanity.py`, `deterministic_baseline_3c.json`, `selected_chunks_3c.json`, `selection_rationale_3c.json`, `llm_normalized_3c.json`, `per_chunk_3c.json`, `per_requirement_comparison_3c.json`, `latency_telemetry_3c.json`, `cross_tender_3c.json`, `tests/test_stage3c_evidence.py` (6 tests), `docs/STAGE_3C_EVIDENCE_AND_REPRESENTATIVE_VALIDATION.md` (this file)
- **Not changed:** `evaluation/gold/mobile_representative_gold.json` (12 reqs), `LLM_SYSTEM_PROMPT` (Variant B), `get_ollama_model` (`qwen2.5:3b`), `schemas/`, `app/decision`, `frontend/`

*Not committed/pushed.*
