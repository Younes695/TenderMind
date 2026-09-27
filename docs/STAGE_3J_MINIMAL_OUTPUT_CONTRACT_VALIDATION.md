# Stage 3J — Minimal Output-Contract Validation

**Date:** 2026-09-25
**Fixture:** Exact 16 accepted candidates from Stage 3I (`evaluation/stage3i/generated_candidates.json`, same IDs/order/texts; verified `3i-01…3i-16`)
**Model:** `qwen2.5:3b` at `http://localhost:11434` (available, `OK`), temperature 0, timeout 90s — same settings as the existing LLM evaluator
**Variant B:** byte-for-byte unchanged (hash `9aa3e11254f672cd`); minimal-contract prompt hash `40ac1b4f467ae23d` (version `Variant B-minimal-contract`)
**Branch:** `main` at `d58cbb2` (origin/main in sync) + uncommitted Stage 3A/3C/3D/3E/3F/3G/3H/3I work + Stage 3J harness (evaluation-only, no push)

---

## 1. Objective

Test whether Variant B's output contract (candidate IDs, evidence objects, provenance quotes, requirement linkage, multi-field JSON) independently degrades classification: run a minimal-contract variant — same semantic intent, single `{summary, category, mandatory, applicable_entity}` object, no metadata requested — on the exact same 16 pre-segmented candidates and compare category diversity against unchanged Variant B.

## 2. Hypothesis

If output-contract complexity contributes to TECHNICAL collapse, the minimal contract should recover non-technical categories (toward Stage 3H-A/B levels of 7–8/12) on identical inputs. If collapse persists unchanged, the limiter is semantic classification or model capability rather than response shaping.

## 3. Exact controls

- Same 16 candidates, fixed order (`3i-01…3i-16`), same source texts.
- Same model, endpoint, temperature 0, `stream: False`, JSON mode, timeout 90.
- Deterministic baseline frozen (7 reqs, same as 3I).
- Stage 3I Variant B baseline read from the stored artifact (`variant_b_outputs_3i.json`) and verified from disk (9/16 accuracy, 4/16 collapse) rather than hardcoded.
- Gold untouched (obvious-purpose labels from 3I). No full-tender run, no Sarai, no production changes.

## 4. Fixture

The 16 accepted Stage 3I candidates (11 single-signal, 5 dual-signal where the second signal is a substring artifact). Gold: TECHNICAL×1, COMMERCIAL×3, EXPERIENCE×1, SCHEDULE×2, LEGAL×2, FINANCIAL×2, EQUIPMENT×1, HSE×1, QA_QC×1, PERSONNEL×1, SUBCONTRACTOR×1. SUBMISSION uncovered — no deterministic pattern maps to it (documented 3I gap, not re-tested here).

## 5. Contract differences

Variant B response per requirement: `candidate_id`, `summary`, `category`, `mandatory`, `requirement_type`, `applicable_entity`, `evidence_required`, `conditional`, `source_document`, `page_number`, `confidence`, `provenance{quote_en}`, `extraction_method` + separate `evidence[]` objects with `candidate_id`/`requirement_candidate_id`/fact/source/page/confidence/provenance. Minimal contract: `summary`, `category`, `mandatory`, `applicable_entity` only. Semantic content (role, grounding rule, allowed categories, PRIMARY PURPOSE definitions incl. the `Similar 220kV projects is EXPERIENCE` line, UNKNOWN rule) is identical. No category examples, no few-shot, no priorities, no tender terms, no gold. Provenance (`source_document/page/source_text/candidate_id/parent_chunk_id` + `quote_en` = first 200 chars of source) and 1-to-1 evidence (`fact` = summary) are attached deterministically from the fixture afterward; the model is never asked for them.

## 6. Stage 3H baseline

Minimal single-requirement normalization on 12 snippets: A 7/12 = 0.58 (collapse 1: EQUIPMENT→TECHNICAL), B 8/12 = 0.67 (collapse 1, plus 1 malformed multi). Variant B on the same 12 snippets (3H-C): 6/12 = 0.50, collapse 4 (QA_QC/EQUIPMENT/SUBCONTRACTOR/SUBMISSION→TECHNICAL).

## 7. Stage 3I baseline (verified from stored artifact)

Variant B on the 16 candidates: **9/16 = 0.56**, collapse **4/16** (LEGAL-consortium 3i-05, EQUIPMENT 3i-09, QA_QC 3i-11, SUBCONTRACTOR 3i-14 → TECHNICAL). Every candidate produced exactly 1 requirement + 1 evidence (16/16), source-local. Recomputed from `variant_b_outputs_3i.json` at runtime (asserted 9/16 and 4/16 before running 3J).

## 8. Stage 3J results

**11/16 = 0.69**, collapse **1/16** (EQUIPMENT→TECHNICAL only). Correct: TECHNICAL, EXPERIENCE, SCHEDULE×2, COMMERCIAL×2 (3i-06 fixed-price terms, 3i-16 payment terms), FINANCIAL×2, HSE, QA_QC, LEGAL First-Category. Wrong: COMMERCIAL→FINANCIAL (3i-02 tender-security, same stable confusion as every prior stage), LEGAL→UNKNOWN (3i-05 consortium — abstention, not collapse), EQUIPMENT→TECHNICAL (3i-09, stable everywhere), PERSONNEL→EXPERIENCE (3i-13), SUBCONTRACTOR→EXPERIENCE (3i-14). Statuses: 16/16 `ok` (0 malformed/empty/multi/timeout). Mandatory/entity: all null (correct preservation). Provenance attached 16/16, evidence derived 16/16 (deterministic 1-to-1 by construction).

## 9. Confusion matrices

3J non-zero cells: TECHNICAL→TECHNICAL 1; COMMERCIAL→{COMMERCIAL 2, FINANCIAL 1}; EXPERIENCE→EXPERIENCE 1; SCHEDULE→SCHEDULE 2; LEGAL→{LEGAL 1, UNKNOWN 1}; FINANCIAL→FINANCIAL 2; EQUIPMENT→TECHNICAL 1; HSE→HSE 1; QA_QC→QA_QC 1; PERSONNEL→EXPERIENCE 1; SUBCONTRACTOR→EXPERIENCE 1. Per-category rates are 0/1–2/2 and must not be overread. Full matrices in `comparison_3j.json` / `confusion_matrix_3j.json`. 3I-B matrix for reference: same gold set with LEGAL→{TECHNICAL 1, LEGAL 1}, QA_QC→TECHNICAL, SUBCONTRACTOR→TECHNICAL, COMMERCIAL→{COMMERCIAL 1, FINANCIAL 2}.

## 10. Per-candidate comparison

| candidate | gold | 3H-A | 3I-B | 3J | 3H-A err | 3I err | 3J err |
|---|---|---|---|---|---|---|---|
| 3i-01 | TECHNICAL | n/a | TECHNICAL | TECHNICAL | n/a | correct | correct |
| 3i-02 | COMMERCIAL | FINANCIAL | FINANCIAL | FINANCIAL | neighbor | neighbor | neighbor |
| 3i-03 | EXPERIENCE | EXPERIENCE | EXPERIENCE | EXPERIENCE | correct | correct | correct |
| 3i-04 | SCHEDULE | n/a | SCHEDULE | SCHEDULE | n/a | correct | correct |
| 3i-05 | LEGAL | n/a | TECHNICAL | UNKNOWN | n/a | collapse | abstention |
| 3i-06 | COMMERCIAL | n/a | COMMERCIAL | COMMERCIAL | n/a | correct | correct |
| 3i-07 | FINANCIAL | n/a | FINANCIAL | FINANCIAL | n/a | correct | correct |
| 3i-08 | FINANCIAL | FINANCIAL | FINANCIAL | FINANCIAL | correct | correct | correct |
| 3i-09 | EQUIPMENT | n/a | TECHNICAL | TECHNICAL | n/a | collapse | collapse |
| 3i-10 | HSE | HSE | HSE | HSE | correct | correct | correct |
| 3i-11 | QA_QC | QA_QC | TECHNICAL | QA_QC | correct | collapse | correct |
| 3i-12 | LEGAL | SUBMISSION | LEGAL | LEGAL | neighbor | correct | correct |
| 3i-13 | PERSONNEL | n/a | EXPERIENCE | EXPERIENCE | n/a | neighbor | neighbor |
| 3i-14 | SUBCONTRACTOR | SUBCONTRACTOR | TECHNICAL | EXPERIENCE | correct | collapse | neighbor |
| 3i-15 | SCHEDULE | n/a | SCHEDULE | SCHEDULE | n/a | correct | correct |
| 3i-16 | COMMERCIAL | n/a | FINANCIAL | COMMERCIAL | n/a | neighbor | correct |

(3H-A column filled where source_text matches a 3H snippet exactly: 3i-02/03/08/10/11/12/14; else n/a — different snippet sets. 3J summaries in `task_c_3j.json`, e.g., 3i-06 `Fixed price, payment in EGP, …`, 3i-12 First-Category full copy.)

## 11. Error taxonomy

- Correct: 11 (grounded summaries, all copy/paraphrase source).
- Semantic neighbor error: 3 (3i-02 COMMERCIAL→FINANCIAL, 3i-13 PERSONNEL→EXPERIENCE, 3i-14 SUBCONTRACTOR→EXPERIENCE — same stable confusions as every prior stage; 3i-14 moved from collapse to neighbor vs 3I-B).
- TECHNICAL collapse: 1 (3i-09 EQUIPMENT→TECHNICAL, stable across all five interfaces 3G-A/B + 3H-A/B/C + 3J — likely schema-boundary overlap, not prompt-specific).
- UNKNOWN: 1 (3i-05 consortium→UNKNOWN — honest abstention on a permission statement, counted incorrect per gold LEGAL but not a collapse).
- Hallucination 0, malformed 0, timeout 0, source/candidate ambiguity 0.

## 12. Latency

| Test | Total (16 calls) | Avg | p95 | Timeouts |
|---|---|---|---|---|
| 3J | ~98.5s | ~6.2s | ~20.4s (first-call warmup) | 0 |
| 3I-B (same 16) | ~426s | ~26.6s | ~30.5s | 0 |
| 3H-A (12 snippets) | ~79s | ~6.6s | ~20.7s | 0 |

Minimal contract restores minimal-prompt latency (no 4–5× Variant B penalty). Full 69-chunk estimate at 3J rate ≈ 7 min vs ≈30 min for Variant B (estimates, not measured).

## 13. Architectural interpretation

The data support this pipeline assignment (evaluation conclusion only — production unchanged):

- Candidate discovery / segmentation: deterministic (splitter + quality gate work: 16 accepted single-purpose + 21 correctly rejected mixed/tiny/signal-less).
- Semantic normalization: LLM with a minimal single-object contract (3J recovers QA_QC/SUBCONTRACTOR-as-neighbor/LEGAL-First-Category/COMMERCIAL-payment lost under Variant B).
- Provenance: deterministic (fixture-attached, exact spans).
- Evidence linkage: deterministic (1-to-1 derivation; model-generated linkage was the 3B drift source).
- Canonical IDs: deterministic (unchanged assign step).

## 14. Limitations

- 16 candidates, 1–3 per category: rates are binary, no significance claimed; single run per variant (wording variance observed in 3E/3F, categories were the signal).
- SUBMISSION has no candidate (deterministic gap) so its 3H-C collapse could not be retested.
- 3i-05 consortium→UNKNOWN is counted wrong per gold LEGAL; whether abstention is preferable to a wrong label is a policy question, not measured here.
- EQUIPMENT→TECHNICAL persists in all six interfaces tested (3G-A/B, 3H-A/B/C, 3J) — untouched by contract simplification.
- Garbled-OCR and timeout behavior were not re-tested (no OCR-noise candidates in this set; 0 timeouts observed).

## 15. Decision: A) STRONGLY SUPPORTS OUTPUT-CONTRACT HYPOTHESIS

TECHNICAL collapse drops substantially (3I-B 4/16 → 3J 1/16), category diversity approaches minimal A/B (3J correct categories: TECHNICAL, EXPERIENCE, SCHEDULE×2, COMMERCIAL×2, FINANCIAL×2, HSE, QA_QC, LEGAL = 8 distinct vs 3I-B's 7 with 4 collapses; non-technical recovered: QA_QC, LEGAL-First-Category, COMMERCIAL-payment, SUBCONTRACTOR-as-neighbor), and output reliability improves (16/16 ok, 0 malformed vs 3H-B's 1 multi; latency back to ~6s). The one remaining collapse (EQUIPMENT) is stable across all six interfaces and looks like a schema-boundary/model-level confusion, not contract complexity. Classification is about the prompt experiment only, not the overall product.

## 16. Next experiment

Implement the evaluated architecture behind a flag on the real pipeline path (deterministic pre-segmentation → minimal-contract LLM normalization → deterministic provenance/evidence/IDs) and rerun the Stage 3D 12-chunk + full-tender comparison against current production, keeping Variant B as the control. If category diversity holds on real chunks with no evidence drift and no latency blowup, propose it as the production change. Do not add few-shot examples, new categories, BID logic, or model changes in that experiment.

---

**Files changed (Stage 3J, evaluation-only):**
- **Added:** `evaluation/stage3j/minimal_contract_prompt.py`, `run_3j.py`, `task_c_3j.json`, `comparison_3j.json`, `confusion_matrix_3j.json`, `latency_3j.json`, `README.md`, `tests/test_stage3j_contract.py` (8 tests), `docs/STAGE_3J_MINIMAL_OUTPUT_CONTRACT_VALIDATION.md` (this file)
- **Not changed:** Variant B/C/D prompts, model, schema, evidence/provenance implementation, chunking globally, deterministic semantics, gold, frontend/backend, timeouts/decoding beyond reuse

*Not committed/pushed.*
