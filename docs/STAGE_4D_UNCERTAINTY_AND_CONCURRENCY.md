# Stage 4D — Uncertainty Signals, Warmed Concurrency, Harder-Tender Validation

## 1. Objective
Three separate experiments: (A) find gold-free uncertainty signals for
valid-but-wrong outputs; (B) measure warmed concurrency properly (n=32);
(C) validate routing on a harder, non-Mobile tender (6th October).

## 2. Exact controls
Same minimal-1 contract, temp 0, timeout 90, shared parser, only qwen2.5:3b +
gemma3:12b in routing. Signals defined on (text, deterministic signals, model
output, status, latency) only; gold used post-hoc for evaluation. Fresh calls
for self-consistency, concurrency, and all harder-tender runs; stored-row
reuse only where labeled diagnostic (Mobile R3).

## 3. Environment
Unchanged machine (i7-6820HQ, 16GB, 4GB VRAM, Ollama local). Repo baseline
d58cbb2/c193c78, fetched, preserved, no commits.

## 4. Candidate signals
S_UNKNOWN, S_INVALID, S_DEGENERATE, S_SIGNAL_MISMATCH (pred ∉ deterministic
signals), S_KEYWORD_MISMATCH (summary keyword-dominant category vs pred, sets
from contract PRIMARY PURPOSE text — not gold), S_LENGTH_ANOMALY,
S_VERBATIM_COPY, S_SLOW, plus S_SELF_CONSISTENCY and S_LOGPROBS (unavailable:
Ollama /api/chat exposes no logprobs; no config change permitted).

## 5. Signal evaluation (n=49 scored Mobile rows: 18 wrong / 31 right)
| Signal | Flagged | Prec | Rec | FPR | Valid-but-wrong caught |
|---|---|---|---|---|---|
| S_UNKNOWN / S_INVALID | 2 | 1.00 | 0.11 | 0.00 | 0 |
| S_DEGENERATE / LENGTH / VERBATIM | 0 | — | 0 | 0 | 0 |
| S_SLOW | 1 | 0.00 | 0 | 0.03 | 0 |
| S_SIGNAL_MISMATCH | 15 | 0.87 | 0.72 | 0.06 | 13 |
| S_KEYWORD_MISMATCH | 22 | 0.73 | 0.89 | 0.19 | 14 |
| UNKNOWN_OR_MISMATCH | 17 | 0.88 | 0.83 | 0.06 | — |
| UNKNOWN_OR_KEYWORD | 22 | 0.73 | 0.89 | 0.19 | — |
Caveats: MISMATCH is partly circular (fixture gold IS signals[0] on
single-signal rows) — yet it caught 2 cases where the model CORRECTLY
overrode the patterns (informative FPs: 3i-12, 3i-16). KEYWORD is independent
but crude (6 FPs from mixed-vocabulary summaries). Combos add nothing beyond
their parts.

## 6. Self-consistency
qwen2.5:3b ×2 on 16 primary: 16/16 category agreement (summaries equivalent).
At temperature 0 the model is deterministic here → doubling cost buys zero
information. NOT USEFUL as a signal in this setup. (`self_consistency.json`.)

## 7. Concurrency benchmark (warmed, 32 fixed requests)
| c | wall | thr/s | avg | p95 | max | errors |
|---|---|---|---|---|---|---|
| 1 | 165.6s | 0.193 | 5.2s | 6.3s | 6.4s | 0 |
| 2 | 101.0s | 0.317 | 6.2s | 7.5s | 9.5s | 0 |
| 4 | 106.2s | 0.301 | 12.6s | 14.7s | 15.5s | 0 |
| 8 | 108.2s | 0.296 | 24.2s | 28.4s | 28.7s | 0 |
c=2 is the sweet spot (1.64×); c≥4 serializes in contention (avg scales with
c, wall flat). Zero errors at all levels — c=2 evidenced SAFE for batch use;
do NOT label any level "production safe" (single session, n=32, no soak).

## 8. Harder-tender dataset
6th October: Clarification (3pp) + Transformer Specs (19pp) + VOL1 pp1–30,
native text, fitz-direct, no OCR → 52 pages → 282 accepted / 2523 rejected.
Explicit 22-row round-robin subset across all 13 signal groups; 21 scored +
1 AMBIGUOUS golds (manual dominant-purpose, provenance + confidence per row in
`harder_gold.json`; ambiguous row kept for abstention analysis only).

## 9. R0 (harder)
7/21 (0.333), collapse 4/20, UNKNOWN 3. Fragment density crushes qwen:
TECHNICAL collapse ×4, EXPERIENCE neighbors, 3 abstentions. (Mobile R0: 31/49.)

## 10. R1 (harder)
3 UNKNOWN escalations → 8/21 (0.381), +135s. +1 (PERSONNEL fix); collapse
unchanged. Mirrors Mobile R1 (+1 each) at a higher trigger rate (14% vs 4%).

## 11. R3 (harder)
Keyword gate: 11 escalations (3 R1 + 8 new) → 8/21. Fixed 2 more (PERSONNEL,
SUBMISSION) but BROKE 2 correct COMMERCIAL answers (gemma SUBMISSION bias) —
net zero at 387s gemma cost. Mobile R3-diagnostic (stored rows): 22 flags,
9 fixed, 2 broken, 31→38/49. The gate's value is tender-dependent; its FPR
cost is general. R3 stays evaluation-only.

## 12. Cross-tender comparison
GENERAL: observable escalation rare (+1 each); collapse never triggers signals;
keyword FPR breaks correct answers on both; fragments drive difficulty.
TENDER-SPECIFIC: Mobile neighbor errors are gemma-fixable (+9 diag); 6thOct
fragments trigger gemma's SUBMISSION bias (net zero); qwen3 placeholder-echo
(Mobile Arabic) untested here by scope. Do not generalize from one tender —
but the FAILURE MODES (invisible neighbors, collapse, FPR cost) reproduced.

## 13. Latency/resources
Walls in `latency.json`. Residency rule: cold gemma escalation ≈ 90s ≈ policy
limit — keep models resident or budget reloads. Snapshots only for VRAM/RAM.

## 14. Limitations
n=49+21; manual golds (1 ambiguous excluded); single session/machine;
stored-row Mobile R3 is diagnostic; concurrency n=32 one session; logprobs
unmeasurable without config change; self-consistency only temp-0 qwen.

## 15. Production implications
Nothing changes: qwen2.5:3b default, no auto-routing, no contract/schema/UI
changes (all verified). c=2 batching evidenced for offline throughput only.

## 16. Decision
Uncertainty: WEAK overall — KEYWORD_MISMATCH PROMISING-WITH-COST (rec 0.89,
FPR 0.19, tender-dependent payoff); all structural signals near-zero recall;
self-consistency dead; logprobs unavailable. Concurrency: factual 1.64× at c2,
zero errors — adoptable for batch tooling, not production SLA. Routing:
PARTIAL — R1 robust but tiny; R3 not promotable (FPR). Keep Router abstraction
only.

## 17. Stage 4E recommendation
(a) calibration research on larger n (the binding constraint stands);
(b) capability lanes over blanket escalation (mandatory/Arabic showed model
separation); (c) concurrency soak + warmed c1-vs-c2 at n≥128; (d) Gemini/API
challenger when credentialed; (e) gold-set growth on 6th October fragments
(collapse/UNKNOWN behavior is the richest signal source found).
