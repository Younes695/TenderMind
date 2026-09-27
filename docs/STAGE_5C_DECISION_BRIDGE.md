# Stage 5C — Decision with evidence for uploaded tenders

## Problem
The decision engine (`app/engines/status.py`, `decision.py`) read only
`Requirement / Evidence / EvidenceMatch` rows, which existed for the seeded
Sarai tender alone. Uploaded tenders produced requirements inside
`TenderAnalysis` JSON and never got a BID / REVIEW / NO_BID decision.

## What was built
- `app/engines/tender_bridge.py`
  - `sync_requirements()` — runs automatically after processing persists
    (and lazily from `/decision-detail` for older tenders). UNKNOWN is
    quarantined. Bidder-qualification categories (LEGAL, EXPERIENCE,
    FINANCIAL, EQUIPMENT, PERSONNEL, QA_QC = hard gates; COMMERCIAL, HSE,
    SUBCONTRACTOR = qualification) are mandatory unless the model said
    optional. TECHNICAL / SCHEDULE / SUBMISSION are informational and never
    block. Starting state: MISSING_EVIDENCE -> decision REVIEW.
  - Company documents (uploaded once, reused for every tender), split into
    section-aware passages with page numbers.
  - `EvidenceJudge` — the LLM step inside the existing `HybridMatcher`
    (deterministic pre/post rules and relevance gate kept). Returns verdict +
    confidence + verbatim quote. Enforced in code: PASS/FAIL need a quote that
    exists in the company passage; FAIL needs confidence >= 0.8; otherwise
    REVIEW. A guess can never become NO_BID and an invented quote can never
    become PASS.
  - `evaluate_tender()` — parallel (TENDERMIND_WORKERS_ENABLED) matching,
    Evidence + EvidenceMatch rows with file/page/quote, then the unchanged
    decision engine.
- API: `GET/POST /api/company-documents`, `DELETE /api/company-documents/{id}`,
  `POST /api/tenders/{id}/evaluate`, `GET /api/tenders/{id}/evaluation`,
  `GET /api/tenders/{id}/decision-detail`.
- UI: `frontend/src/components/DecisionPanel.jsx` on the tender workspace —
  decision badge, mandatory counts, rules in plain language, company-document
  upload + Evaluate with progress, requirement list with tender source
  (file/page/quote) and company evidence (file/page/quote/confidence/reason),
  human override with audit.
- Matcher model: `TENDERMIND_MATCHER_MODEL` (default = `OLLAMA_MODEL`,
  qwen2.5:3b). `OllamaMatcher`'s own default is qwen3:4b with thinking on,
  which took ~90s per call and evicted the pipeline model.

## Measured (Motawreen "Tenders conditions volume 1", 168 pages, fictional demo profile)
| | first matcher (OllamaMatcher 2-field) | EvidenceJudge |
|---|---|---|
| PASS | 1 | 19 (all with verbatim quotes) |
| FAIL | 2 (confidence 0.00, wrong) -> NO_BID | 0 |
| REVIEW | 2 | 23 |
| decision | NO_BID (wrong) | REVIEW (honest: e.g. no tender security in the profile) |
| wall time, 150 mandatory reqs | 557s | 339s |
Spot check: "turnover at least EGP 2 billion" vs profile "EGP 1.2 billion" ->
FAIL 0.90 with the exact quote (correct contradiction).

## Known limits
- Many "mandatory" rows are contract obligations (e.g. liquidated damages),
  not qualification proofs; they stay MISSING/REVIEW, so a full conditions
  volume will rarely reach BID without a human override.
- REVIEW rows show the closest passage, which can be only loosely related.
- `tests/test_adversarial.py::test_12_human_override` is intermittently
  flaky in the full suite (orders two decisions by a timestamp that can tie
  on Windows clock resolution); passes alone and on rerun.
