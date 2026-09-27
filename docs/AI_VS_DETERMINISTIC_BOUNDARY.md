# TenderMind — AI vs Deterministic Boundary (Stage 4E)

Full per-capability table: `evaluation/stage4e/capability_inventory.json`
(47 capabilities; matrix: 24 deterministic-implementation, 17 AI, 1 human-only,
5 hybrid-natured). No scores, no invented severity (tested).

## Rule
DETERMINISTIC when facts extract without semantic inference. AI when natural-
language interpretation is required. HYBRID when deterministic facts feed AI
clause interpretation with deterministic provenance.

## Decided
Deterministic: inventory, typing, PDF/DOC/XLSX/TXT extraction, OCR routing,
discovery, segmentation, compression, deadlines, dates (absolute), validity,
currency, payment, bid-security patterns, BOQ normalization, missing docs,
gap counts, evidence binding + R1–R6 validation, supersession record-keeping.
AI (lightweight): normalization, category (same call — never a separate model),
mandatory/entity (null-default), schedule/commercial clause interpretation
(unwired), risk phrasing over grounded signals, obligation/question listing.
AI (strong, unwired): contradictions, reconciliation, addendum impact,
synthesis pack. Human-only, permanently: business impact/severity, BID/NO-BID.
Hybrid: delivery/completion, risk signals (deterministic facts → AI phrasing,
severity never assigned).

## Notes
- Category shares normalization's call by design (one model, many capabilities).
- Mandatory/entity stay null-default; phi's explicit-true cases are the future
  supervised seed, not a backend.
- Relative-date anchors, multi-currency first-match, security-clause recall,
  expected-document checklists: listed as unresolved per capability, not hidden.
