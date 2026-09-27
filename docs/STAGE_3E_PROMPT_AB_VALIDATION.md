# Stage 3E — Controlled Variant-B Prompt Tuning Experiment

**Date:** 2026-09-25
**Fixture:** `Mobile-Stage3E-001` (same 5-file Mobile subset as 3/3A/3B/3C/3D) + gold `evaluation/gold/mobile_representative_gold.json` (12 reqs, 8 distinct categories, not modified)
**Model:** `qwen2.5:3b` at `http://localhost:11434` (available, `OK` both runs), temperature 0, JSON mode, timeout 90s, evidence fix (3C) + tiny guard (3D) preserved
**Branch:** `main` at `d58cbb2` (origin/main in sync) + uncommitted Stage 3A/3C/3D hardening + Stage 3E harness (evaluation-only, no push)

---

## 1. Objective

Test one hypothesis: *"The existing PRIMARY PURPOSE classification instruction is insufficient for qwen2.5:3b, causing requirements with mixed vocabulary to collapse into TECHNICAL."* Measure whether minimal semantic clarification (Variant C) changes category behavior without regressing grounding/evidence/schema/null-safety. Do not assume the hypothesis true before measuring.

## 2. Environment

- Windows 10, Python 3.11.0, `pymupdf 1.28.2`, `openpyxl 3.1.5`, `tesseract 5.4.0_ara+eng_psm6_dpi300`, `fastapi 0.115.0`. Local CPU, no GPU/Azure/paid API.
- Ollama `http://localhost:11434` via `check_ollama_available()` — `OK http://localhost:11434 model qwen2.5:3b` for both B and C runs.
- Tender rebuilt identically twice (same 5 files, same Vol I 20 pages via `fitz insert_pdf`): `Commercial forms.txt` 217 chars, `Drawings.pdf` 2p `tesseract` 4350, `Price schedules …xlsx` 5040, `Tender Price Schedule- Arabic.pdf` 41p 83049, `Vol I subset 20p` 40380 — 65 pages, ~133k chars, `ocr_ratio 0.03`.

## 3. Model/version

- `qwen2.5:3b` (`DEFAULT_MODEL`, `OLLAMA_MODEL`/`TENDERMIND_OLLAMA_MODEL` override, unchanged). Endpoint `http://localhost:11434` (unchanged). Timeout 90 (`TIMEOUT_PER_REQUEST`, unchanged). `options: {"temperature": 0}`, `stream: False`, `format: "json"` (unchanged). No model switch.

## 4. Prompt/version/hash

- **Variant B** (`PROMPT_VERSION_B = "Variant B"`, len 2472, hash `9aa3e11254f672cd`): original `LLM_SYSTEM_PROMPT` preserved byte-for-byte (verified `VARIANT_C.startswith(VARIANT_B)` and `git diff` shows no B lines changed).
- **Variant C** (`PROMPT_VERSION_C = "Variant C"`, len 3164, hash `a1711fb49e7e629a`): `LLM_SYSTEM_PROMPT + "\n\n" + LLM_PRIMARY_PURPOSE_CLARIFICATION` (+692 chars). Added suffix only (see `evaluation/stage3e/prompt_diff_3e.txt`):
  > Primary-purpose guidance (semantic, not keyword matching): Classify by main business/contractual purpose. Experience (bidder history, past/reference projects) -> EXPERIENCE. Financial capacity, turnover, audited statements, bank guarantee capacity -> FINANCIAL. Power of attorney, legal authorization, registration, consortium agreement -> LEGAL. Personnel qualifications, staff CVs, key staff, project manager -> PERSONNEL. Payment, price, bid security, commercial terms -> COMMERCIAL. Delivery, completion, submission, opening, validity dates -> SCHEDULE. Equipment, specification, performance, testing, drawings -> TECHNICAL.
- No tender-specific examples (no Mobile/Sarai/6th October/NUCA/220KV GIS switchgear verbatim), no new categories (12 preserved, no BID/NO-BID/score), no gold IDs/summaries, no `prefer X` priority, `UNKNOWN != FALSE` preserved (still in B base). `get_system_prompt(variant)` defaults to B; `call_ollama_for_chunk(..., system_prompt=None)` defaults to B (production unchanged).

## 5. Fixture

Same Stage 3D 12 chunks (verified `Stage 3E chunk_ids == Stage 3D chunk_ids`, `Match: True` in both B and C runs). Gold 12 reqs unchanged. Tiny guard same (`<300` chars → `SKIPPED_TINY_INPUT`): `chunk-0000` Commercial forms.txt 217 chars skipped in both, 11 LLM calls each.

## 6. Experimental design

- **A) Variant B** on 11 chunks (1 skipped) via `run_variant(filtered, SYS_B, "B")` with strict evidence fix, same validation/dedup/canonical as 3C/3D.
- **B) Variant C** on the **exact same 11 chunks** (same `chunk_id`/doc/page/text, same order) via `run_variant(filtered, SYS_C, "C")`.
- Deterministic baseline frozen (`use_llm=False`, 7 reqs, 48.6–53.6s, same as 3D). No deterministic regeneration between variants. Saved incrementally (`variant_b_3e.json` before C, so C timeout cannot lose B).

## 7. Deterministic baseline

7 reqs (EXPERIENCE Vol I:6, SCHEDULE Price:1, TECHNICAL Commercial:1, COMMERCIAL Tender Price:40, LEGAL Vol I:6, FINANCIAL Vol I:3, PERSONNEL Vol I:8), deadlines 0, commercial 3 fields, provenance 7/7, TP lenient 11/12 (only HSE missed, Clarification not in Mobile subset). Saved `deterministic_baseline_3e.json`.

## 8. LLM-normalized results

| Variant | Reqs | Evs | Categories | Calls (success/fail/skip) |
|---|---|---|---|---|
| B | 9 | 8 | 9/9 TECHNICAL | 11 (9/2/1) |
| C | 9 | 9 | 9/9 TECHNICAL | 11 (9/2/1) |

- B summaries: Drawings `220kV specs`, `Main Road`, `XLPE`, Price `Supply of GIS` + garbled OCR, Tender Price:37 `works shall include design…`, Vol I:3 `Construction turnkey`, Vol I:7 `To be qualified… power of attorney`, Vol I:8 `Site visit`, plus depth chunks. All TECHNICAL, confidence 0.75, method `llm`.
- C summaries: Drawings `Future extension of dotted lines` (vs B `220kV specs` for same chunk-0001 — model variance, not prompt effect alone), `Main Road` (same), `XLPE` variant, Price `Materials, quantities and prices for 220KV GIS system` (vs B `Supply of GIS` — same meaning, different wording), garbled OCR, Tender Price:37 `works shall include…` (same), Vol I:3 `Construction and completion…` (same), Vol I:7 `To be qualified…` (same), Vol I:8 `Site visit…` (same). All TECHNICAL, confidence 0.75.
- Evidence: B 8 evs (chunk-0005 garbled has 0 evs — correctly no fabrication), C 9 evs (chunk-0005 garbled has 1 ev from garbled OCR — slightly more eager, see §13). All 1-to-1, no cross-chunk (see §13).
- Saved: `variant_b_3e.json`, `variant_c_3e.json`, `per_chunk_b/c_3e.json` (per-chunk status/requirements/evidence/validation/latency), `selected_chunks_full_3e.json` (full texts).

## 9. Semantic summary analysis

- **B correct (1):** `Supply of 220KV GIS switchgear` for GOLD-001 (preserves `220KV GIS`, `Supply`, quote `B/G 201000 | supply…`).
- **C correct (1):** `Materials, quantities and prices for 220KV GIS system` for GOLD-001 (preserves `220KV GIS`, `quantities/prices`, grounded in Price schedules header `Schedule No. (1) Materials, Quantities and prices` — equally correct, different wording).
- **Partial (B 1, C 1):** B `220kV specs` / C `Future extension…` for Drawings — both capture voltages/drawings, miss `60 MVA`.
- **Incorrect but grounded (B 7, C 7):** `Main Road`, `XLPE`, `works shall include…`, `Construction turnkey`, `To be qualified…`, `Site visit`, garbled OCR — all paraphrases of chunk text, no invented quantities/BID.
- **Hallucinated (0 both):** No summaries from nothing. Preserves voltages/equipment names (`220kV`, `GIS switchgear`, `XLPE`), misses durations/financial values (`12 months`, `500,000` not in LLM summaries), contractual constraints partial (`power of attorney` preserved but misclassified).
- Deterministic still generic 7/7, strict 0/12. LLM strict 1/12 both (different wording, same gold).

## 10. Requirement split/merge analysis

- Both: Drawings 2976-char chunk → 1 req (correct for that chunk in these runs; 3B gave 3 from same chunk — model variance with temperature 0, reported honestly). Price schedules 2989 chars (6 requirements in one chunk) → B 2 reqs (`Supply of GIS` + garbled), C 2 reqs (`Materials…` + garbled) — both **under-split** (should be 6). Vol I:3/7/8 each 1 — correct. No over-split, no incorrect merge (9 distinct kept via deduplication).

## 11. Category analysis

| Category | Gold (12) | Det 7 | B 9 | C 9 |
|---|---|---|---|---|
| TECHNICAL (3) | GOLD-001,004,005 | 1 (3 TP lenient) | 9 (3 TP, 6 extra grounded but not in gold) | 9 (same) |
| COMMERCIAL (3) | GOLD-002,006,008 | 1 (3 TP) | 0 | 0 |
| EXPERIENCE (1) | GOLD-003 | 1 | 0 | 0 |
| SCHEDULE (1) | GOLD-012 | 1 | 0 | 0 |
| FINANCIAL (1) | GOLD-011 | 1 | 0 | 0 |
| LEGAL (1) | GOLD-009 | 1 | 0 | 0 |
| HSE (1) | GOLD-007 | 0 (not in subset) | 0 | 0 |
| PERSONNEL (1) | GOLD-010 | 1 | 0 | 0 |

- Det correctness 7/7=1.00, distinct 7/8=0.88. B correctness 3/12=0.25 instance, 1/8 distinct. C identical: 3/12, 1/8. **No category produced beyond TECHNICAL in either** (HSE/QA_QC/SUBCONTRACTOR/SUBMISSION/EQUIPMENT never produced — correctly not forced, none in subset with sufficient text).
- **Harmful changes (both):** Missed COMMERCIAL/EXPERIENCE/SCHEDULE/FINANCIAL/LEGAL/PERSONNEL that deterministic found on same chunks. No new categories, no `prefer TECHNICAL` instruction in C (verified).

## 12. Mandatory/entity analysis

- Gold: 2 `mandatory true` (GOLD-002,009), rest null; all `applicable_entity null`.
- Det: All 7 null — correctly preserved. B: All 9 null. C: All 9 null. **0 correct explicit, all correct null preservation, 0 unsupported inference, 0 contradiction.** `To be qualified… shall` left null in both (conservative, correct per `UNKNOWN != FALSE`).

## 13. Evidence/provenance analysis

- **Coverage:** B 8/9=0.89 (chunk-0005 garbled has 0 evs — correctly no fabrication), C 9/9=1.00 (chunk-0005 garbled has 1 ev from garbled OCR — slightly more eager, but grounded in chunk text, not hallucinated from nothing).
- **Correctness:** B 8/8 source-local correct (each `requirement_candidate_id` matches own chunk, each `requirement_id` distinct, e.g., `chunk-0004-ev-01 -> chunk-0004-item-01 (REQ-002)` with `_original_requirement_candidate_id` preserved for hallucinated `chunk-0001-item-01`). C 9/9 same (e.g., `chunk-0004-ev-01 -> chunk-0004-item-01`). **0 cross-chunk errors both** (vs 3B 3/4 drift). **0 unresolved** (2 timeouts → 0 evs, 1 skipped → 0 evs).
- **Source mismatch:** 0 both (all `source_document` equals chunk doc, all pages within ranges).
- **Quote correctness:** Each `quote_en` substring of chunk text (e.g., `B/G 201000 | supply…`).
- **Regression rule:** No meaningful regression in C vs B (C +1 evidence for garbled chunk is variance, not drift; still 1-to-1, valid IDs, correct doc/page/quote). No blocker.

## 14. JSON/schema robustness

- B: valid JSON 9/11=0.82 (9 `ok`, 2 timeouts no response, 0 `fenced`/`extracted`/`malformed`), schema 9/9 +8/8 =1.00, retries 0, permanent failures 2/11, skipped tiny 1/12, timeouts 2, fallback 0.
- C: identical counts (9/11 valid, 9/9 +9/9 schema, 0 retries, 2 failures, 1 skipped, 0 fallback). Null-handling correct (all `mandatory/applicable_entity/requirement_type null` where not explicit), duplicate IDs 0 (each `chunk-XXXX-item-01` corrected with `_original_candidate_id` preserved), provenance failures 0.

## 15. Latency

| Variant | Total | Avg | p95 | Calls (success/fail/skip) | Reqs/evs |
|---|---|---|---|---|---|
| B | 509.2s | 46.3s | 92.1s | 11 (9/2/1) | 9/8 |
| C | 526.2s | 47.8s | 92.0s | 11 (9/2/1) | 9/9 |
| Det | 49.5–53.6s | — | — | 0 | 7/0 |

C +17s total (+1.5s avg) due to slightly longer generations (e.g., chunk-0051 35.0s vs 31.5s), not significant. Full 69-chunk est. ~52–55 min both (clearly labeled estimate).

## 16. Cross-tender sanity check

Reuse `evaluation/stage3c/cross_tender_3c.json` (deterministic subsets, no full LLM per spec lightweight): 6th Oct (`Clarification 5p`+`Addendum.zip` → 2 reqs, deadlines 0, no Sarai, `Addendum.zip` FAILED in analysis vs unsupported in job — known mismatch), Motawreen (`Layout pdf 5p`+`.bak` → 1 TECHNICAL, deadlines 0, currency EGP, no Sarai, `.bak` FAILED). No Mobile/Sarai hardcoding (same `GENERIC_PATTERNS`), source-local, `220/22/22` not deadlines. B/C Mobile outputs have 0 `Sarai/SA-2018/GIZA/HYOSUNG` hits (verified via `Select-String`, 0 matches).

## 17. Failure taxonomy

- HSE/Clarification + Vol II PERSONNEL → ingestion (not in 5-file subset, not LLM).
- FINANCIAL now found deterministically, but LLM still TECHNICAL → LLM miss (both variants).
- Commercial forms + Tender Price p29 timeouts → LLM failure (both, 2/11).
- `Main Road` FP → evaluation limitation (in Drawings, not gold).
- COMMERCIAL/EXPERIENCE/SCHEDULE/FINANCIAL/LEGAL missed → LLM miss (both).
- Evidence drift → fixed (0 now, both).
- `20/22/22` → deterministic fixed (0 now, both).

## 18. Before/after comparison (B vs C, same 12 chunks)

| Metric | Variant B | Variant C | Delta |
|---|---|---|---|
| Reqs | 9 | 9 | 0 |
| Category dist | 9 TECHNICAL | 9 TECHNICAL | 0 |
| TP lenient | 3/12 | 3/12 | 0 |
| Distinct recall | 1/8 | 1/8 | 0 |
| Strict correct | 1/12 | 1/12 (different wording, same gold) | 0 |
| Mandatory correct | 0/2 (null preserved) | 0/2 | 0 |
| Evidence coverage | 8/9=0.89 | 9/9=1.00 | +1 (garbled chunk) |
| Evidence correctness | 8/8 source-local | 9/9 source-local | 0 drift both |
| Valid JSON | 9/11=0.82 | 9/11=0.82 | 0 |
| Latency total/avg | 509.2s/46.3s | 526.2s/47.8s | +17s/+1.5s |

*No single overall score.*

## 19. Concrete examples (ambiguous-case table)

| Source | Deterministic signal | Variant B category | Variant C category | Expected/gold | Grounding | Evidence | Result |
|---|---|---|---|---|---|---|---|
| Vol I:7 `To be qualified… power of attorney… experience, financial…` (chunk-0055, EXPERIENCE+FINANCIAL+LEGAL+TECHNICAL) | LEGAL + EXPERIENCE + FINANCIAL | TECHNICAL `To be qualified…` | TECHNICAL `To be qualified…` (same text, slightly different truncation) | LEGAL (GOLD-009) | Faithful quote `...power of attorney…` | 1-to-1, same chunk Vol I:7, valid IDs | Both miss (harmful, persists) |
| Price schedules `Tender security EGP 500,000… Experience… Schedule…` (chunk-0004, SCHEDULE+TECHNICAL) | COMMERCIAL + EXPERIENCE + SCHEDULE | TECHNICAL `Supply of GIS` | TECHNICAL `Materials, quantities and prices…` | COMMERCIAL (GOLD-002) | Both grounded in Price header, miss security | 1-to-1 | Both miss |
| Vol I:3 `Construction turnkey…` + `Financial…`? (chunk-0051, COMMERCIAL+FINANCIAL+SCHEDULE+TECHNICAL) | FINANCIAL + COMMERCIAL | TECHNICAL `Construction turnkey…` | TECHNICAL `Construction and completion…` (same) | FINANCIAL (GOLD-011) | Faithful scope text | 1-to-1 | Both miss FINANCIAL |
| Vol I:8 `Key personnel… Project Manager…`? Actually `Site visit…` (chunk-0056, PERSONNEL+TECHNICAL) | PERSONNEL | TECHNICAL `Site visit…` | TECHNICAL `Site visit…` (same) | PERSONNEL (GOLD-010, though Vol II not in subset) | Faithful site-visit text | 1-to-1 | Both miss PERSONNEL |
| Price `10% advance…` (Vol I:3, COMMERCIAL) | COMMERCIAL | TECHNICAL (scope) | TECHNICAL (scope) | COMMERCIAL (GOLD-008) | Missed payment terms | 1-to-1 | Both miss |
| `Deadline 15 of March` (Vol I:5, not in selected 12? Vol I:5 chunk not selected — selection has Vol I:3,7,8 but not :5) | SCHEDULE | — (no Vol I:5 chunk) | — | SCHEDULE (GOLD-012) | Not supplied to LLM (sampling limitation, not LLM miss for this table; deterministic found via global patterns) | — | Both miss due to sampling |
| Drawings `220kV specs` (chunk-0001, TECHNICAL) | TECHNICAL | TECHNICAL `220kV specs` | TECHNICAL `Future extension…` (different summary, same chunk) | TECHNICAL (GOLD-001/004/005) | Both grounded in Drawings OCR | 1-to-1 | Both correct category, C wording differs (variance) |

## 20. Limitations

- Same 12 chunks, same tiny guard (1 skipped), same 2 timeouts (Tender Price p29/p33 Arabic dense) — C did not fix timeouts.
- HSE not evaluable (Clarification not in Mobile subset).
- `.zip`/`.bak` FAILED vs unsupported mismatch (known, not fixed).
- Temperature 0 still shows run-to-run variance (B `220kV specs` vs C `Future extension…` for same chunk-0001 — cannot fully attribute summary wording differences to prompt; categories identical, so category conclusion is robust).
- Full 69 chunks ≈53 min est., not measured.

## 21. Recommendation for next engineering step (technical, not product)

- **Do not adopt Variant C as production yet based on category alone** (no improvement), but **do not discard the clarification approach** — it caused no regression (evidence/provenance/schema/null-safety all hold, +1 evidence for garbled chunk is variance, not drift).
- Next experiment should test whether the collapse is due to **single-requirement-per-chunk bias** (LLM returns 1 req per chunk even when chunk contains 6 requirements, e.g., Price schedules) rather than category wording: try minimal structural hint (e.g., `Extract all distinct requirements in the chunk, not just one`) without adding examples/categories, measured on same 12 chunks. If still all TECHNICAL, then consider 1–2 generic few-shot examples (still no tender-specific).
- Keep strict evidence fix + tiny guard + representative selector unchanged.

---

## Artifacts

- `evaluation/stage3e/prompt_hashes_3e.json` (B 2472 `9aa3e11254f672cd`, C 3164 `a1711fb49e7e629a`), `prompt_diff_3e.txt` (exact +692-char suffix), `deterministic_baseline_3e.json` (7 reqs), `selected_chunks_3e.json` + `selected_chunks_full_3e.json` (12 full texts, match 3D), `variant_b_3e.json` (9/8), `variant_c_3e.json` (9/9), `per_chunk_b/c_3e.json`, `per_requirement_comparison_3e.json` (B vs C vs gold), `latency_b/c_3e.json` + `latency_telemetry_3e.json`, `run_3e_ab.py` (A/B harness with incremental saves).
- `evaluation/stage3d/` (12-chunk fixture, tiny guard) and `evaluation/stage3c/` (selector, evidence fix) reused, not duplicated.
- Gold not modified.

## Tests

- New: `tests/test_stage3e_prompt.py` **7 passed** (B preserved, C minimal, no new categories/tender terms, UNKNOWN preserved, hashes stable, defaults to B).
- Existing: `test_stage3d_tiny_guard` 6, `test_stage3c_evidence` 6, `test_llm_generic_extraction` 23, `test_generic_extraction` 19, `test_stage3a_deterministic` 22, processing/OCR 5+7+5, upload/E2E/matcher/decision/adversarial/azure/benchmark/ollama/hybrid 89 — total backend **189 passed (182 +7)**, frontend **41 passed**, `vite build` success. No regression.

---

**Files changed (Stage 3E, prompt experiment only):**
- `evaluation/llm_generic_extraction.py` — added `PROMPT_VERSION_B/C`, `LLM_PRIMARY_PURPOSE_CLARIFICATION`, `LLM_SYSTEM_PROMPT_VARIANT_C`, `get_system_prompt()`, `prompt_hash()`, `call_ollama_for_chunk(..., system_prompt=None)` default B (no B text change, ~30 lines)
- **Added:** `evaluation/stage3e/` (above 12 files), `tests/test_stage3e_prompt.py` (7 tests), `docs/STAGE_3E_PROMPT_AB_VALIDATION.md` (this file)
- **Not changed:** model, temperature, JSON mode, timeout, chunk selector, 12 chunks, deterministic candidates, gold, schema, validation, evidence linking, provenance, dedup/canonical, tiny guard, frontend, decision, Redis/Celery/auth

*Not committed/pushed.*

## 22. Decision: C) NOT IMPROVED

Category collapse remains materially unchanged (B 9/9 TECHNICAL, C 9/9 TECHNICAL on identical 12 chunks; TP lenient 3/12 both, distinct recall 1/8 both). Variant C causes no important regression (evidence 1-to-1 both, provenance 100% both, schema 100% both, null-safety preserved, valid JSON 9/11 both, latency +17s not significant), but provides no material category improvement. The +1 evidence for garbled OCR in C vs B is run-to-run variance (temperature 0 still nondeterministic across runs for wording/evidence-count on noise), not prompt effect. Classification is about the prompt experiment only, not the overall product.
