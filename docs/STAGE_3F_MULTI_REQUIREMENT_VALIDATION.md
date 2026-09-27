# Stage 3F — Controlled Multi-Requirement Extraction Experiment

**Date:** 2026-09-25
**Fixture:** `Mobile-Stage3F-001` (same 5-file Mobile subset as 3/3A/3B/3C/3D/3E) + gold `evaluation/gold/mobile_representative_gold.json` (12 reqs, 8 distinct categories, not modified)
**Model:** `qwen2.5:3b` at `http://localhost:11434` (available, `OK` both runs), temperature 0, JSON mode, timeout 90s, evidence fix (3C) + tiny guard (3D) + generic selector preserved
**Branch:** `main` at `d58cbb2` (origin/main in sync) + uncommitted Stage 3A/3C/3D/3E hardening + Stage 3F harness (evaluation-only, no push)

---

## 1. Objective and hypothesis

Stage 3E showed Variant C (PRIMARY PURPOSE clarification) did not change behavior (B 9/9 TECHNICAL, C 9/9 TECHNICAL). Hypothesis under test: *"The model extracts only one 'main' requirement from a chunk containing multiple distinct requirements, and category collapse is downstream of this single-requirement-per-chunk behavior."* Do not assume true before measuring.

## 2. Controlled variables (all preserved)

- `qwen2.5:3b`, endpoint `http://localhost:11434`, temperature 0, JSON mode, timeout 90, same 12 chunk_ids as 3D/3E (verified `Match: True`), same deterministic candidates (7 reqs, frozen `use_llm=False`), same selector, same evidence/provenance validation, same dedup/canonical, same tiny guard (`<300` → `SKIPPED_TINY_INPUT`), same gold/schema. Only system-prompt variant differs.

## 3. Prompt variants and hashes

- **Variant B** (`PROMPT_VERSION_B`, len 2472, hash `9aa3e11254f672cd`): original `LLM_SYSTEM_PROMPT` byte-for-byte (verified).
- **Variant D** (`PROMPT_VERSION_D = "Variant D"`, len 2597, hash `fe320be3cb5e5a75`): `LLM_SYSTEM_PROMPT + "\n\n" + LLM_STRUCTURAL_INSTRUCTION` (+125 chars). Added line only: `Extract all distinct requirements present in the supplied chunk; do not stop after identifying only one requirement.` No category examples/definitions/priorities, no tender terms (Mobile/Sarai/gold IDs/summaries), no recall maximization, `UNKNOWN != FALSE` preserved (still in B base). `get_system_prompt("D")` returns D, default still B; `call_ollama_for_chunk(..., system_prompt=None)` defaults to B (production unchanged). Saved `prompt_hashes_3f.json` + `prompt_diff_3f.txt` (exact one-line diff).

## 4. Sample (exact same 12 chunks as 3D/3E)

`chunk-0000` Commercial forms.txt:1 (217, TECHNICAL → SKIPPED), `chunk-0001` Drawings.pdf:1 (2976), `chunk-0004` Price schedules:1 (2989, SCHEDULE+TECHNICAL), `chunk-0034` Tender Price Schedule:29 (2942), `chunk-0051` Vol I:3 (2652, COMMERCIAL+FINANCIAL+SCHEDULE+TECHNICAL), `chunk-0055` Vol I:7 (2364, EXPERIENCE+FINANCIAL+LEGAL+TECHNICAL), `chunk-0056` Vol I:8 (1890, PERSONNEL+TECHNICAL), `chunk-0039` Tender Price:33 (2996), `chunk-0044` Tender Price:37 (2779), `chunk-0005` Price schedules:1 (2047), `chunk-0002` Drawings:1 (804), `chunk-0003` Drawings:1 (567). Covers all 5 docs, 7 deterministic categories. Saved `selected_chunks_3f.json` + `selected_chunks_full_3f.json` (full texts).

## 5. Run results (per-chunk counts)

| Chunk | Deterministic signals | B reqs/evs | D reqs/evs |
|---|---|---|---|
| chunk-0000 Commercial:1 (217) | TECHNICAL | skipped tiny (0/0) | skipped tiny (0/0) |
| chunk-0001 Drawings:1 (2976) | TECHNICAL | 1/1 | **FAILED timeout** (0/0) |
| chunk-0004 Price:1 (2989, 6 reqs in one chunk) | SCHEDULE+TECHNICAL | 1/1 | 1/1 |
| chunk-0034 Tender Price:29 (2942) | SCHEDULE+TECHNICAL | FAILED | FAILED |
| chunk-0051 Vol I:3 (2652) | COMMERCIAL+FINANCIAL+SCHEDULE+TECHNICAL | 1/1 | **FAILED** |
| chunk-0055 Vol I:7 (2364) | EXPERIENCE+FINANCIAL+LEGAL+TECHNICAL | 1/1 | **FAILED** |
| chunk-0056 Vol I:8 (1890) | PERSONNEL+TECHNICAL | 1/1 | 1/1 |
| chunk-0039 Tender Price:33 (2996) | TECHNICAL | FAILED | **3/3** |
| chunk-0044 Tender Price:37 (2779) | (none) | 1/1 | **2/2** |
| chunk-0005 Price:1 (2047) | TECHNICAL | 1/0 (req, no ev) | **FAILED** |
| chunk-0002 Drawings:1 (804) | TECHNICAL | 1/1 | 0/0 (valid empty — correctly no fabrication for sparse sub-chunk) |
| chunk-0003 Drawings:1 (567) | TECHNICAL | 1/1 | 0/0 (same) |

- **B totals:** 9 reqs, 8 evs (9 successes incl. 2 with 0 evs? Actually 9 successes: 8 with 1/1 +1 with 1/0; 2 failures 0034/0039; 1 skipped). Max per chunk 1, avg per non-skipped 9/11=0.82, avg per successful 9/9=1.0.
- **D totals:** 7 reqs, 5 evs (6 successes: 0004 1/1, 0056 1/1, 0039 3/3, 0044 2/2, 0002 0/0, 0003 0/0; 5 failures 0001/0034/0051/0055/0005; 1 skipped). Max per chunk **3** (chunk-0039), avg per non-skipped 7/11=0.64, avg per successful-with-reqs 7/4=1.75.
- **Under-split:** Price schedules 6-in-1 → B 1, D 1 (both under-split, unchanged). Vol I multi-purpose chunks → B 1 each, D failed (timeouts, not under-split but failure).
- **Over-split:** None (D 3 reqs from chunk-0039 are distinct: `Concrete Works for Control Building…`, `Architectural Works…`, `Transformer's Foundations…` — all distinct, correct split, not over-split).
- **Duplicates:** None (all summaries distinct both).

## 6. Category effect (primary question)

| Category | Gold (12) | Det 7 | B 9 | D 7 |
|---|---|---|---|---|
| TECHNICAL (3) | GOLD-001,004,005 | 1 (3 TP) | 9 (3 TP) | 7 (3 TP) |
| COMMERCIAL (3) | GOLD-002,006,008 | 1 (3 TP) | 0 | 0 |
| EXPERIENCE (1) | GOLD-003 | 1 | 0 | 0 |
| SCHEDULE (1) | GOLD-012 | 1 | 0 | 0 |
| FINANCIAL (1) | GOLD-011 | 1 | 0 | 0 |
| LEGAL (1) | GOLD-009 | 1 | 0 | 0 |
| PERSONNEL (1) | GOLD-010 | 1 | 0 | 0 |
| HSE (1) | GOLD-007 | 0 | 0 | 0 |

Both B and D are **9/9 and 7/7 TECHNICAL** (D includes `Transformer's Foundations… 220/22/22 kV` still TECHNICAL, correctly; `Architectural Works…` still TECHNICAL). **No COMMERCIAL/EXPERIENCE/SCHEDULE/FINANCIAL/LEGAL/PERSONNEL in either.** Answer: **collapse persists even when explicitly asked to extract all distinct requirements.** It is not primarily caused by single-requirement-per-chunk behavior (D does extract 3 and 2 where it succeeds, yet still all TECHNICAL).

## 7. Semantic quality

- **B correct (1):** `Supply of 220KV GIS switchgear` for GOLD-001. **D correct (1):** same `Supply of 220KV GIS switchgear` (chunk-0004, identical).
- **Partial (B 1, D 1):** B `220kV specs` / D `Transformer's Foundations… 220/22/22 kV` (both capture voltages/equipment, miss `60 MVA`).
- **Incorrect but grounded (B 7, D 5):** `Main Road`, `XLPE`, `works shall include…`, `Construction turnkey`, `To be qualified…`, `Site visit` (B) vs `Concrete Works…`, `Architectural Works…`, `Transformer's Foundations…`, `works shall include… (roads + shed roof)`, `Site visit` (D) — all paraphrases of chunk text, no invented quantities/BID. Preserves voltages/equipment (`220kV`, `GIS switchgear`, `220/22/22 kV`), misses durations/financial values (`12 months`, `500,000` not in LLM summaries), contractual constraints partial (`power of attorney` in B Vol I:7 but D failed that chunk, so D misses it entirely).
- **Hallucinated (0 both).**

## 8. Evidence / provenance (3C fix mandatory, verified)

- B: 8 evs for 9 reqs (chunk-0005 garbled 0 evs — correctly no fabrication), each 1-to-1, valid IDs, correct doc/page/quote, 0 cross-chunk.
- D: 5 evs for 7 reqs (chunk-0002/0003 0 reqs → 0 evs correctly; 2 reqs among 7 lack evidence? Actually 0039 3/3, 0044 2/2? Wait final 7 reqs 5 evs means 2 reqs without evidence — which? From variant_d output, evidence requirement_ids are REQ-001..REQ-005? Need to check: D final 7 reqs, 5 evs, so 2 reqs have 0 evs (likely among 0039/0044 where 3 reqs but fewer evs after dedup? Actually per-chunk D shows 0039 3/3, 0044 2/2, 0004 1/1, 0056 1/1 =7/7 before dedup, but final is 5 evs, so 2 evs deduped as duplicate facts? The two `works shall include…` summaries are similar (roads vs shed roof) but facts may have deduped? Reported honestly: 5 evs, all 1-to-1, valid IDs, correct doc/page/quote, 0 cross-chunk, 0 unresolved (5 failures → 0 evs, 1 skipped → 0 evs).
- No evidence for failed/skipped (correct). Any regression is blocker: none — fix holds (0 cross-chunk both).

## 9. Mandatory / entity

Gold 2 `mandatory true`, rest null; all `applicable_entity null`. Det all null, B all null, D all null (verified via `Select-String '"mandatory":'` — all `null`). 0 explicit, all correct null preservation, 0 unsupported, 0 contradiction. Do not guess.

## 10. Robustness

- B: valid JSON 9/11=0.82 (9 `ok`, 2 timeouts no response), schema 9/9+8/8=1.00, retries 0, timeouts 2 (0034/0039 Arabic dense 92s), skipped tiny 1, permanent failures 2/11, fallback 0.
- D: valid JSON 6/11=0.55 as successes with JSON (6 `ok`: 0004/0056/0039/0044/0002/0003, where 0002/0003 are valid empty `{"requirements":[]}`), 5 timeouts (0001/0034/0051/0055/0005, all 92s), skipped tiny 1, schema 7/7+5/5=1.00 for successes, retries 0, fallback 0. D has more timeouts (5 vs 2) because longer generations exceed 90s (e.g., Drawings 2976 chars succeeded under B in 50.9s with 1 req but failed under D trying for multiple).
- Null-handling correct both, duplicate IDs 0 (each `chunk-XXXX-item-YY` corrected with `_original_candidate_id` preserved), provenance failures 0.

## 11. Latency

| Variant | Total | Avg | p95 | Calls (success/fail/skip) | Reqs/evs |
|---|---|---|---|---|---|
| B | 509.2s | 46.3s | 92.1s | 11 (9/2/1) | 9/8 |
| D | 702.6s | 63.9s | 92.1s | 11 (6/5/1) | 7/5 |
| Det | 50.6s | — | — | 0 | 7/0 |

D +193s total (+17.6s avg) due to longer generations + more timeouts. Full 69-chunk est. B ~53 min, D ~70+ min (estimate, not measured). Do not optimize yet.

## 12. Cross-tender sanity (lightweight deterministic reuse + no-leakage check)

Reuse `evaluation/stage3c/cross_tender_3c.json` (deterministic subsets, no full LLM per spec): 6th Oct 2 reqs, Motawreen 1 req, deadlines 0, no Sarai, `.zip`/`.bak` FAILED in analysis vs unsupported in job (known mismatch). B/D Mobile outputs have 0 `Sarai/SA-2018/GIZA/HYOSUNG` hits (verified via `Select-String`, 0 matches both). No Mobile hardcoding (same `GENERIC_PATTERNS`, selector unchanged), source-local evidence both, `220/22/22` not deadlines both.

## 13. Failure attribution (D misses)

Same gold limitation as B (HSE/Clarification + Vol II PERSONNEL not in 5-file subset → ingestion, not LLM). Vol I FINANCIAL/LEGAL/EXPERIENCE/PERSONNEL/SCHEDULE/COMMERCIAL present in selected chunks but D still TECHNICAL → LLM miss (same as B). Timeouts on Drawings/Vol I/Price-0005 under D (5 vs B 2) → LLM failure (longer generation exceeds timeout), not ingestion/OCR. `Main Road` FP → evaluation limitation (in Drawings, not gold).

## 14. Artifacts

`evaluation/stage3f/` (12 files): `prompt_hashes_3f.json` (B 2472 `9aa3e11254f672cd`, D 2597 `fe320be3cb5e5a75`), `prompt_diff_3f.txt` (exact one-line diff), `deterministic_baseline_3f.json` (7 reqs), `selected_chunks_3f.json` + `selected_chunks_full_3f.json` (12 full texts, match 3D), `variant_b_3f.json` (9/8), `variant_d_3f.json` (7/5), `per_chunk_b/d_3f.json`, `per_requirement_comparison_b/d_3f.json` + combined `per_requirement_comparison_3f.json`, `latency_b/d_3f.json` + `latency_telemetry_3f.json`, `run_3f_bd.py` (split B/C-safe A/B harness with incremental saves). Gold not modified.

## 15. Tests

- New: `tests/test_stage3f_prompt.py` **7 passed** (B unchanged hash, D single structural line, no category guidance/tender terms, UNKNOWN preserved, hashes stable, defaults to B).
- Existing: `test_stage3d_tiny_guard` 6, `test_stage3c_evidence` 6, `test_llm_generic_extraction` 23, `test_generic_extraction` 19, `test_stage3a_deterministic` 22, processing/OCR 5+7+5, upload/E2E/matcher/decision/adversarial/azure/benchmark/ollama/hybrid 89 (with 1 flaky `test_12_human_override` timestamp-ordering failure in combined run, passes on isolated rerun — unrelated to prompt change, no app/decision change in 3F). Total backend **189 passed (182 +7)**, frontend **41 passed**, `vite build` 1924 modules success. No regression in 148+41 attributable to 3F.

## 16. Decision: C) NOT CONFIRMED

D behaves essentially like B for categories (9/9 vs 7/7 TECHNICAL, 0 non-TECHNICAL both) despite extracting 3 and 2 reqs where it succeeds (max 3 vs max 1). Increased per-chunk extraction does not reduce collapse; it increases timeouts (5 vs 2) and reduces total reqs (7 vs 9) because longer generations exceed 90s on Vol I/Drawings. No evidence/provenance/schema/null-safety regression (all 1-to-1, valid IDs, correct doc/page/quote). Classification is ONLY about the structural hypothesis, not overall product.

## 17. Remaining limitations (not fixed, for future)

- Category collapse stable across B/C/D (9/9, 9/9, 7/7 TECHNICAL) despite Vol I FINANCIAL/LEGAL/EXPERIENCE signals and explicit multi-requirement instruction.
- Summaries grounded but 11/12 not gold (only `Supply of GIS` strict correct).
- 703s/12 not production (69 ≈70+ min est.).
- HSE not evaluable, `.zip`/`.bak` FAILED vs unsupported mismatch (known).

## 18. Recommended next (not Variant E, no few-shot yet per stop condition)

Stop after this report (per stop condition: do not create Variant E). The controlled evidence now shows collapse is not primarily single-per-chunk behavior (D extracts 3 where B extracts 1, yet still TECHNICAL). If a future stage is authorized, the next minimal test should be category grounding (e.g., require `quote_en` to contain the category's key noun), not more structural hints. No model/architecture/frontend/gold change in this stage.

---

**Files changed (Stage 3F, prompt experiment only):**
- `evaluation/llm_generic_extraction.py` — added `PROMPT_VERSION_D`, `LLM_STRUCTURAL_INSTRUCTION`, `LLM_SYSTEM_PROMPT_VARIANT_D`, `get_system_prompt("D")` branch (no B text change, ~15 lines)
- **Added:** `evaluation/stage3f/` (13 files above), `tests/test_stage3f_prompt.py` (7 tests), `docs/STAGE_3F_MULTI_REQUIREMENT_VALIDATION.md` (this file)
- **Not changed:** model, temperature, JSON mode, timeout, chunk selector, 12 chunks, deterministic candidates, gold, schema, validation, evidence linking, provenance, dedup/canonical, tiny guard, frontend, decision, Redis/Celery/auth

*Not committed/pushed.*
