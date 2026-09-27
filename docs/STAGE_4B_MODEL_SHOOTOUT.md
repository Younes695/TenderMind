# Stage 4B — Controlled Model Shootout

## 1. Objective
Benchmark qwen2.5:3b (baseline), qwen3:4b, gemma3:12b, phi4-mini (and Gemini 3.8
Flash if reachable) through the SAME hardened two-stage normalization task from
Stage 4A, without changing production, prompts, contracts, or pipeline semantics.

## 2. Environment
Intel i7-6820HQ (4C/8T), 16GB RAM, Quadro M2200 4GB VRAM (WDDM), 15GB disk free
at start, Windows, Ollama local (gguf Q4_K_M). 4GB VRAM means gemma3:12b runs
mostly CPU-offloaded. Gemini: no credentials (`GOOGLE_API_KEY`/`GEMINI_API_KEY`/
`GOOGLE_GENAI_API_KEY` all absent) and no client library installed → NOT_RUN;
no secrets requested, nothing hardcoded (per protocol).

## 3. Models tested
| Model | Tag | Digest | Size | Status |
|---|---|---|---|---|
| qwen2.5:3b | qwen25 | 357c53fb659c | 1.9GB | RUN 57/57 |
| qwen3:4b | qwen3 | 359d7dd4bcda | 2.5GB | RUN 57/57 |
| gemma3:12b | gemma | f4031aab637d | 8.1GB | RUN 57/57 |
| phi4-mini | phi | 78fad5d182a7 | 2.5GB | RUN 57/57 |
| gemini-3.8-flash | gemini | — | — | NOT_RUN (no credentials) |

## 4. Exact benchmark controls
Same candidates (byte-identical, fixture sha asserted per model run), fixed
order, same source_text, same 13-category space, same MINIMAL_CONTRACT_SYSTEM
string, same user builder, same parser (`parse_single_requirement`),
temperature 0, format json, timeout 90s. One documented control: qwen3's Ollama
default enables thinking (breaks single-JSON comparability) → `think:false`.
Diagnostic: thinking-on timed out >120s on a failed case, so the control did
not cause qwen3's failures (§12). No tuning, examples, hints, or gold per model.

## 5. Dataset
Primary: exact 16 Stage 3I candidates (balanced: 11 distinct gold categories).
Secondary: exact 41 Stage 3K-A candidates (TECHNICAL-heavy, 2 MULTI excluded
from accuracy; 6 Arabic-source rows scored ONLY in §18). The 150-candidate B
sample was NOT rerun (per-candidate source_text not persisted; re-derivation
cannot re-link run-local IDs — documented, not faked). No Sarai OCR.

## 6. Qwen 2.5 results (baseline)
Primary 11/16 (0.688), secondary-en 20/33 (0.606). Collapse 1+1, UNKNOWN 1+1,
0 malformed, 0 timeouts, 0 provider errors. Avg 6.4s / 5.7s. Grounded 1.0,
mandatory/entity null-compliance 1.0. Diversity 9 cats. Errors: neighbor
confusions (COMMERCIAL→FINANCIAL, PERSONNEL/SUBCONTRACTOR→EXPERIENCE,
EQUIPMENT→TECHNICAL, LEGAL→UNKNOWN on JV fragment). Replicates 3J (11/16).

## 7. Qwen3 results
Primary 12/16 (0.75), secondary-en 12/33 (0.364 — includes 17 contract
violations + 1 http_500 as incorrect). Collapse 1+1, UNKNOWN 1+2. Avg 16.4s /
10.2s. **Systematic failure mode**: 17/41 secondary outputs echo the literal
schema template (`"summary": "..."`) → bad_category. Correlate: ALL 6 Arabic
rows + 11 English rows failed; input length indistinguishable from passes
(74 vs 62 chars). Primary (clean hand-picked English) was 16/16 ok — the
failure bites on real-world fragments, exactly what production would send.

## 8. Gemma results
Primary **14/16 (0.875)**, secondary-en 23/33 (0.697). Collapse 1+2, UNKNOWN
0+1, 0 violations, 0 timeouts. Avg ~32–33s (≈5× baseline). Diversity 11 cats —
only model to get PERSONNEL and SUBCONTRACTOR right on primary; Arabic 5/6.
Bias note: over-predicts SUBMISSION (5 secondary neighbor errors incl. LEGAL/
FINANCIAL/SCHEDULE→SUBMISSION). Grounded 1.0, null-compliance 1.0.

## 9. Gemini results
NOT_RUN — §2. Adapter implemented (`GeminiProvider` reports
provider_not_configured without secrets); registry records the exact reason.

## 10. Phi results
Primary 10/16 (0.625), secondary-en 14/33 (0.424). Collapse 1+1, UNKNOWN 1+0,
0 violations, avg ~7.5s (near-baseline speed). **Systematic EXPERIENCE bias**:
11 TECHNICAL-gold secondary rows → EXPERIENCE. Phi is also the only model to
assert `mandatory:true` (3×, all textually explicit — "must provide/have/be
registered" — contract-compliant, notable for future mandatory-label work).

## 11. Confusion matrices
`confusion_matrices.json` (gold × pred per model/dataset). Universal hard cell:
EQUIPMENT→TECHNICAL (all 4 models, both datasets). Shared neighbor pairs:
LEGAL→EXPERIENCE/UNKNOWN (JV sentences), PERSONNEL/SUBCONTRACTOR→EXPERIENCE,
SCHEDULE↔COMMERCIAL/SUBMISSION, FINANCIAL→COMMERCIAL/SUBMISSION.

## 12. TECHNICAL collapse
Count (rate over non-technical golds): primary all models 1 (qwen25, qwen3, gemma,
phi each exactly one — the EQUIPMENT row). Secondary: qwen25 1, qwen3 1 (+17
violations), gemma 2, phi 1. No model eliminates collapse; gemma trades one extra
collapse for the best overall accuracy. Phi shows the mirror bias (EXPERIENCE×11).

## 13. Reliability
qwen25: 114/114 valid. Gemma: 114/114 valid. Phi: 114/114 valid. Qwen3:
primary 16/16 ok; secondary 23 ok / 17 bad_category / 1 http_500 (single
transient-class server error, candidate 3k-A-26). Zero
timeouts for all (90s policy never tripped; slowest single call 51.3s gemma).

## 14. Latency
Avg (primary/secondary): qwen25 6.4/5.7s, phi 7.4/7.6s, qwen3 16.4/10.2s, gemma
32.4/33.4s. p95 ≈ 1.1–1.3× avg for all. Per-100 projection: qwen25 ~10min, phi
~13min, qwen3 ~17–27min, gemma ~55min. Full-tender 2545-candidate projection:
qwen25 ~4h, gemma ~23h (single-worker; architecture allows future workers).

## 15. Resource usage
Disk: 1.9 / 2.5 / 8.1 / 2.5 GB. All local Ollama gguf; gemma largely
CPU-offloaded on the 4GB card (hence §14). VRAM point-snapshot 2792/4096 MiB
post-run (resident phi; not a peak profile — labeled as such). API cost: n/a,
no cost fabricated. (`resource_comparison.json`.)

## 16. Model agreement
Primary (16): unanimous 10, single-differ 4, split-2/2 2, agree-TECHNICAL-gold-not 1.
Secondary (41): unanimous 14, single-differ 17, split-2/2 5, agree-TECHNICAL-gold-not 2.
High single-differ count (21/57) = models err differently → observable-signal
escalation has headroom; low agree-TECHNICAL-gold-not (3/57) = no collective
collapse. (`model_agreement*.json`.)

## 17. Router simulation (evaluation-only, observable signals only)
Policy: qwen25 first; escalate on UNKNOWN/contract-violation/malformed/
provider-error/timeout. Escalation rate: primary 1/16 (6.25%), secondary-en
1/33 (3.0%) — qwen25's reliability leaves almost nothing to escalate.
Simulated accuracy: primary 11/16 (unchanged — no challenger fixes 3i-05),
secondary-en 21/33 (0.636 vs 0.606 baseline — all three challengers fix 3k-A-28
LEGAL). Verdict from data: with THIS baseline, a fallback buys +1 row per
dataset; the architecture is justified for worse-behaved primaries (e.g. qwen3
would escalate 18/41), not yet economical for qwen25.

## 18. Language robustness (supplementary, existing Arabic rows only, n=6)
Gemma 5/6 correct + 1 UNKNOWN, 0 collapse. qwen25 2/6, phi 2/6 (neighbor
errors, 0 collapse). qwen3 0/6 (all placeholder-echo). Main accuracy untouched
by these rows. Signal: gemma uniquely robust on Arabic-source fragments;
qwen3 non-thinking unusable on them.

## 19. Limitations
Small n (16+33 scored); single-signal deterministic golds punish defensible
dual-aspect answers (§11 pairs); one machine/GPU; Ollama serving variance;
qwen3's think:false is a control with a documented diagnostic, not proof of
optimal qwen3 usage; gemini untested; no concurrency measurement; mandatory/
entity "correctness" is null-compliance + review list, not gold judgment.

## 20. Production implications
Default stays qwen2.5:3b (fastest, 114/114 valid, replicates 3J). Gemma is the
quality challenger (+19pp primary, +9pp secondary, Arabic-robust) at 5× latency
and 8.1GB — viable as an escalation backend, not a wholesale replacement on
this hardware. Phi's speed is attractive but its EXPERIENCE bias is
disqualifying without mitigation. qwen3 non-thinking is disqualified by
contract reliability (44% violation on secondary). No router policy enabled.

## 21. Deferred decisions
Production model selection (needs 4C criteria sign-off); escalation policy;
thinking-vs-reliability study for qwen3-family; mandatory-field supervision
(phi's explicit-mandatory behavior as seed signal); concurrent-worker
measurement; Gemini/API challenger when credentials exist.
