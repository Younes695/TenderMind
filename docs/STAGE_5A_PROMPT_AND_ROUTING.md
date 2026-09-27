# Stage 5A — Prompt minimal-2, per-task escalation, parallel workers

## What changed
1. **Prompt `minimal-2`** (`app/pipeline/prompts.py`), now the default. Same JSON
   output contract as `minimal-1` (summary/category/mandatory/applicable_entity),
   so parser, post-processing, provenance and schema are unchanged.
   `minimal-1` defined only 8 of the 13 allowed categories (EQUIPMENT, PERSONNEL,
   SUBCONTRACTOR, SUBMISSION, UNKNOWN had no definition) and defined FINANCIAL as
   "financial/commercial", overlapping COMMERCIAL. `minimal-2` defines all 13 and
   adds generic tie-break rules (fragments ≠ EXPERIENCE, JV → LEGAL, any
   guarantee/bond → COMMERCIAL, key staff → PERSONNEL, subcontract % → SUBCONTRACTOR).
   Rollback: `TENDERMIND_PROMPT_VERSION=minimal-1`.
2. **Parallel AI workers actually wired.** `app/processing.py` never passed
   `load_worker_config()` to `run_intelligence`, so `TENDERMIND_WORKERS_ENABLED`
   had no effect. Fixed.
3. **Real model/prompt metadata.** Processing metadata said `qwen2.5:3b` /
   `minimal-1` regardless of `OLLAMA_MODEL`; it now reports the model actually
   called and `prompt_version`.
4. **Per-task escalation** (`EscalatingProvider`, opt-in via
   `TENDERMIND_ESCALATION_MODEL`): the fast model handles every candidate; only
   UNKNOWN/failed ones are re-asked to a stronger model. The stronger answer is
   used only if valid and non-UNKNOWN. Off by default (see measurements).

## Measurements (`evaluation/stage5a/`, `python evaluation/stage5a/score.py`)
Same scoring as Stage 4B (temperature 0, JSON mode, same parser; secondary =
33 English non-MULTI rows). Sarai = 21 gold requirements from a different
tender, used as holdout.

| Model / prompt | Primary (16) | Secondary (33) | Sarai (21) | avg latency |
|---|---|---|---|---|
| qwen2.5:3b minimal-1 (4B baseline) | 11 = 0.688 | 20 = 0.606 | 11 = 0.524 | ~5s |
| gemma3:12b minimal-1 (4B baseline) | 14 = 0.875 | 23 = 0.697 | — | ~32s |
| **qwen2.5:3b minimal-2** | **15 = 0.938** | **28 = 0.848** | **18 = 0.857** | ~5s |
| phi4-mini minimal-2 (partial) | 15 = 0.938 | 11/15 = 0.733 | — | ~9s |

Remaining qwen minimal-2 errors (9/70) include several debatable gold labels
(e.g. "tender documents at the office of the financial department" gold
FINANCIAL, predicted SUBMISSION; indemnity clause gold PERSONNEL, predicted
LEGAL). Prompt tuning was stopped here to avoid fitting the test sets.

Caveats, stated plainly: the sets are small (70 rows total). Sarai gold text is
clean English summaries, not raw OCR fragments. The Sarai list was visible while
writing the definitions (no Sarai wording is in the prompt), so treat it as a
soft holdout.

Escalation probe (gemma3:12b + minimal-2 on the 3 qwen UNKNOWNs): 1 fixed, 1
different-but-wrong, 1 HTTP 500; 130–220s per call on this laptop (4GB VRAM,
CPU offload). Not worth enabling on this hardware; worth re-measuring on a GPU
server.

## Live E2E (6th October: Clarification 1.pdf + Power Transformer Specs.pdf)
Same files as the Stage 4G pilot; real server, flag on, qwen2.5:3b, minimal-2,
2 workers, isolated DB/storage.

- First run: processing finished but **PERSISTENCE FAILED** — two-stage
  requirements/evidence carry `confidence: null` by design, the 2-stage schema
  required a number, and strict validation only runs when `jsonschema` is
  installed (it was not in requirements.txt). Fixed: schema permits null
  confidence for requirements/evidence; `jsonschema` pinned; regression test.
- Second run: **COMPLETED in 340s** (4G: ~11 min sequential). 131 calls, 131 ok,
  0 failures, 0 timeouts, avg 5.0s, p95 6.0s. 130 requirements / 130 evidence.
  Categories: TECHNICAL 95, UNKNOWN 20 (4G: 22), HSE 11, COMMERCIAL 2,
  EQUIPMENT 1, SCHEDULE 1.
- Remaining real errors seen in that run: penalty/price formulas and delivery
  terms (DAP) returned UNKNOWN instead of COMMERCIAL; equipment-protection
  fragments (tripping, overheating) returned HSE instead of TECHNICAL.
- A refined prompt with rules for exactly those cases was tried and **rejected**:
  it fixed 1 benchmark row and broke 4 (secondary 28→26, Sarai 18→17). Its raw
  outputs are kept in `evaluation/stage5a/rejected_variant/`. Next step is a
  labeled sample from real fragments, not more prompt rules.

## Rollout
Default model stays qwen2.5:3b. Recommended production env:
`TENDERMIND_TWO_STAGE_LLM=1`, `TENDERMIND_WORKERS_ENABLED=1`,
`TENDERMIND_MAX_AI_WORKERS=2`. Leave `TENDERMIND_ESCALATION_MODEL` unset.
