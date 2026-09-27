# Stage 4C — Routing Validation + Performance Benchmark

## 1. Objective
Test whether qwen2.5:3b + observable-failure escalation + gemma3:12b gives a
useful quality/latency tradeoff: escalation counts, quality recovered,
wall-clock cost, signal usefulness, and whether the Router abstraction earns
its keep. Routing only — production default untouched.

## 2. Environment
Same machine as 4B (i7-6820HQ, 16GB RAM, 4GB VRAM, Ollama local). Repo baseline:
local HEAD d58cbb2 vs origin/main c193c78 (pre-existing frontend-only delta);
`git fetch` clean, no resets, all prior work preserved, no commit/push.

## 3. Candidate fixtures
Exact stored sets: 16 Stage 3I (primary) + 41 Stage 3K-A (secondary; 33 English
scored, 6 Arabic supplement-only, 2 MULTI excluded). Fixture sha asserted per
4B run; escalation inputs hash-verified byte-identical (`input_hash_match` true
for every escalation). No Sarai, no new candidates.

## 4. Routing policies
R0 = qwen for all. R1 = escalate on provider_error|timeout|malformed|
wrong_shape|multi|bad_category|empty|empty_summary|UNKNOWN. R2 = R1 +
degenerate_placeholder|degenerate_repetitive|degenerate_blank (deterministic
string heuristics, no confidence). Gold NEVER routed on (signature-enforced,
test-guarded); scoring post-hoc only. Escalations ran as FRESH gemma calls;
fresh predictions matched stored 4B rows 2/2 (deterministic replication).

## 5. R0 baseline
11/16 (0.688) + 20/33 (0.606). Collapse 1+1. Diversity 9 cats. Wall 103.0s +
233.0s (stored same-machine latencies). 0 malformed, 0 timeouts.

## 6. R1 observable escalation
2 escalations total: 3i-05 (UNKNOWN) + 3k-A-28 (UNKNOWN). Fresh gemma: 3i-05 →
SUBMISSION (gold LEGAL, still wrong); 3k-A-28 → LEGAL (correct, +1).
Primary 11/16 (+73.4s), secondary 21/33 (+25.8s). R1 improves quality by
exactly one candidate across 49 scored rows.

## 7. R2 stricter escalation
Identical to R1 (11/16, 21/33, same walls): degenerate heuristics fired zero
times — qwen outputs on this data are never placeholder-like or repetitive.
R2 adds no value here; keep the rules documented but do not claim gains.

## 8. Escalation reasons
`unknown` 2/2 (100%). Zero provider errors, timeouts, malformed, schema or
category violations from qwen on these 57 rows — qwen's reliability starves
the router of triggers. Cold-load caveat: first escalation attempts timed out
at 90s (gemma evicted, ~86–92s reload); warm retry succeeded — model residency
dominates first-escalation latency on this hardware (see §12).

## 9. Model disagreement
Routing-observed (escalated only): 1 fixed (LEGAL), 1 still wrong (SUBMISSION).
Context from 4B full pairwise: unanimous 10/16+14/41, single-differ 21/57 —
models err differently, so headroom exists IF triggers existed. Collective
TECHNICAL agreement on non-gold only 3/57 (no joint collapse).

## 10. Quality comparison
R0 11/16, 20/33 → R1/R2 11/16, 21/33. Gain: +1 correct candidate for 2
escalations (+99s). Collapse unchanged (1+1). Diversity unchanged. UNKNOWN
count: R0 1+1 → R1 0+0 (both UNKNOWNs resolved away — one rightly, one wrongly).

## 11. Latency
Sequential router walls: primary 176.3s (103.0 qwen + 73.4 gemma), secondary
258.8s (233.0 + 25.8). Per-100 projection ≈ 30min (escalation rate ~4%).
Escalation cost is gemma-latency-dominated (26–73s warm; ~90s cold-loaded).

## 12. Resource usage
Disk 1.9 + 8.1GB resident models. VRAM snapshots 2468–2792/4096 MiB
(point-in-time, not peaks — no precise claims). 8.5GB RAM free during probe.
Key operational datum: single-model residency on 4GB VRAM; switching models
costs a full reload (cold escalation ≈ timeout threshold).

## 13. Concurrency
4 fixed candidates, qwen25: warmed c1 = 20.7s (all ok), c2 = 14.1s (all ok) —
repeated 3× with c2 pinned at 14.1s (deterministic workload: temp 0, same
prompts → same compute). ~1.5× wall, zero errors, zero instability. Small n:
do NOT generalize; 4D should run warmed c1-vs-c2 at n≥32 with error/latency
distributions before any production claim.

## 14. Oracle upper bound (DIAGNOSTIC, not a policy)
Perfect escalation of every known qwen error: primary 14/16 (escalate 5),
secondary 26/33 (escalate 13). R1 recovers 0/3 and 1/6 of that headroom —
the gap IS the invisible-error problem (§16).

## 15. Limitations
n=49 scored; single-signal golds; one machine; escalation n=2 (thin evidence
for rates); c=2 probe n=4; VRAM/RAM point snapshots; gemini absent; qwen
reliability on THIS data may not represent harder tenders (where triggers
would be more frequent — the router's value scales with primary failure rate).

## 16. Architectural implications — detectably bad vs valid-but-wrong
16/49 scored qwen errors are valid-but-wrong (4 primary + 12 secondary:
neighbor confusions like PERSONNEL→EXPERIENCE, EQUIPMENT→TECHNICAL) — NO
observable signal exists for them, by construction of the minimal contract.
Observable routing can only ever harvest the detectably-bad slice (here: 2
UNKNOWNs). Any future gain must come from (a) better uncertainty/calibration
signals, (b) capability-specific routing, or (c) a better primary — NOT from
more output heuristics (R2 exhausted that direction on this data).

## 17. Decision
KEEP the Router abstraction (clean, tested, zero prod cost); DO NOT enable
automatic escalation in production — measured gain (+1/49 for +99s) does not
justify it on current evidence. Stay on qwen2.5:3b default. No frontend, prompt,
contract, provenance, or decision-engine changes (all verified untouched).

## 18. Recommended Stage 4D
(a) warmed concurrency at n≥32 with distributions; (b) confidence/uncertainty
signal research (the binding constraint — §16); (c) capability-specific routing
(e.g. mandatory-field or Arabic-language lanes, where 4B showed model
separation); (d) Gemini/API challenger when credentials exist; (e) re-run R1 on
a harder tender where qwen triggers are frequent, to measure the router where
it can actually matter.
