# Stage 5G — Escalation to qwen3:4b on by default

## Change
`default_router()` now wraps qwen2.5:3b in `EscalatingProvider` with
`qwen3:4b` unless `TENDERMIND_ESCALATION_MODEL=off`. Only candidates the
primary returns as UNKNOWN or fails to parse are re-asked; rows the primary
settled are never touched. An escalation answer is used only when it is valid
and non-UNKNOWN. Escalation timeout default 240s → 150s (max observed 88s).

## Measurement (`python evaluation/stage5g/escalation_probe.py <model>`)
Same 70 rows and scoring as Stage 5A (primary 16, secondary 33, Sarai 21),
starting from the stored qwen2.5:3b minimal-2 outputs.

| Escalation model | Primary | Secondary | Sarai | Total |
|---|---|---|---|---|
| none (5A stored) | 15/16 | 27/33 | 18/21 | 60/70 = 0.857 |
| phi4-mini | 15/16 | 28/33 | 18/21 | 61/70 = 0.871 — **rejected** |
| **qwen3:4b** | 15/16 | 28/33 | 19/21 | **62/70 = 0.886** |

phi4-mini was rejected: it answered all 7 escalated rows and 4 of them were
wrong labels. An UNKNOWN is quarantined from the bid decision; a wrong label is
not, so trading UNKNOWN for wrong labels is worse even at +1.
qwen3:4b: 2 fixed (TECHNICAL, EQUIPMENT), 1 wrong (indemnity fragment → LEGAL,
gold PERSONNEL — debatable), 4 stayed UNKNOWN.

## Cost
13–88s per escalated row on this laptop (4GB VRAM). On the 5A live E2E (~20
UNKNOWN of 130 rows, 2 workers) that is roughly +5–7 min on a 340s run.
If throughput matters more than coverage, set `TENDERMIND_ESCALATION_MODEL=off`.

## Caveat
70 rows is a small set; +2 rows is a real but modest gain. The next honest
lever is a labeled sample of real OCR fragments, not more prompt rules.
