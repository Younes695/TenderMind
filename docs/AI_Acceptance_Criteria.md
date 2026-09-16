# AI Acceptance Criteria — TenderMind v1 (Test #001)

Derived from `AI_Evaluation_Contract_v1.md` §8.

## Gate Rule
Any invariant violation = **automatic fail** — regardless of F1:
- MISSING → FAIL conversion
- Risk HIGH → NO_BID
- PASS/FAIL without provenance (doc+page)
- Expired cert treated as PASS
- Entity mismatch treated as PASS
- Hallucinated requirement/evidence not in gold

## Thresholds

| Metric | Gold | Threshold | Method |
|---|---|---|---|
| Arabic native page F1 | Sarai native PDFs | ≥0.95 | Token F1 vs gold text_blocks |
| Arabic scanned F1 | Scanned certs | ≥0.85 | Same |
| Table cell accuracy | BoQ/guarantee tables | ≥0.90 | Exact cell match |
| Page number accuracy | All | 100% | Must match |
| Requirement Set F1 | 21 A-U | ≥0.90 (text ≥0.85) | ID + text similarity |
| Mandatory accuracy | All mandatory flags | 100% | Exact |
| Applicable entity accuracy | GIZA/CONSORTIUM | ≥0.95 | Exact |
| Evidence Set F1 | 4 gold E | ≥0.90 | Fact+doc+page |
| Provenance completeness | PASS/FAIL | 100% | Automated check |
| Matching macro F1 | 21 + 13 adversarial | ≥0.93; MISSING→FAIL = 0% | Confusion matrix |
| Conflict F1 | 2 conflicts | ≥0.90 | Detect First/Second |
| Decision accuracy | REVIEW/NO_BID/BID | 100% on gold+adv | Hard_fail vs missing |
| Explanation completeness | Every decision | 100% fields | Schema validation |

## How to Evaluate
```bash
python -m tests.test_decision_engine   # 6 tests
python -m tests.test_adversarial       # 12 + explanation
# Future: python evaluation/run_evaluation.py --gold evaluation/sarai_gold_dataset.json --pred pred.json
# Metrics: precision/recall/F1 per component, confusion matrix for matching, provenance audit
```

## Example Failure Modes
- AI invents REQ-V not in gold → Requirement Set precision drops → fail
- AI returns E-002 without page → provenance completeness fail
- AI maps Hyosung cert to GIZA REQ-A → applicability fail (test_6)
- AI gives PASS for expired cert → expiry fail (test_9)

Pass = all thresholds + zero invariant violations.
