# Stage 4G — Production Pilot Validation

## Baseline
d58cbb2/c193c78, fetched, preserved. Live E2E on isolated DB/storage.

## Fresh tender (6th October, never a primary benchmark)
Clarification 1.pdf (3pp) + Power Transformer Specs.pdf (19pp) + Addendum.zip
(→ UNSUPPORTED, exercising PARTIAL truthfulness). No Mobile/Sarai content
(leakage markers all false). No XLSX exists in this tender (honest absence;
structured path covered by generic tests + 4F BOQ experiment).

## End-to-end (4G3, flag ON, real qwen, ~11 min)
Create → 3 uploads → process → duplicate-POST 409 → COMPLETED → analysis →
byte-identical re-GET. 169 candidates → 127 reqs / 127 evidence, provenance
254/254, 8 categories (TECHNICAL 85, UNKNOWN 22, HSE 6, COMMERCIAL 5, SCHEDULE
3, EQUIPMENT/FINANCIAL/LEGAL 2). Gaps 4, ambiguities 78, risks 3, synthesis
true. Commercial/schedule from deterministic extractors; clarifications 0
explicit records (Clarification.pdf processed as ordinary source with
SUPERSESSION_UNKNOWN lifecycle where applicable).

## Bugs found live, fixed, re-verified
1. `extraction_method: two-stage` rejected by 2-stage schema copy → added
   documented enum value (base schema untouched; 4A regression test updated to
   assert exactly the two documented deltas).
2. Terminal COMPLETED despite PERSISTENCE failure → honesty rule: no persisted
   analysis + real documents ⇒ FAILED. (First run proved the rule fires.)

## Job hardening
`stage_events` table (auto-created, no migration): INVENTORY/EXTRACTION/
PERSISTENCE/COMPLETED events with timestamps+counts+errors on every run;
surfaced additively in GET job (refresh/reconnect recovery). 409 on active
re-POST preserved; reprocess after terminal creates a NEW job (no silent dup).
`progress` stays a coarse marker; counts are the truth (documented).

## UI/API/persistence
All 6 contracts exercised live and backward-compatible. Intelligence section
renders 4F payload sections with fallbacks (44 frontend tests). Re-GET
byte-identical → persistence proven. Analysis payload additive-only.

## Security (audit, no enterprise overbuild)
Traversal sanitized + confined (tested); 50MB cap; collision rename; invalid
ext → UNSUPPORTED; per-doc failure isolation; ORM-only queries (migration
PRAGMA/ALTER only); no eval/pickle/yaml/subprocess; no secrets; no live
dev paths; no tender text in logs/telemetry. One low: `original_filename`
echoes unsanitized input in metadata (storage unaffected) — sanitize echo next.
