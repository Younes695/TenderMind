# Stage 4E — Capability Lanes + Structured Data (evaluation/architecture)

Moves "which model does everything?" → "which capability needs what?" No
auto-routing, no new models, no production behavior change.

## Files
- `capability_inventory.json` (47 capabilities, full schema incl. evidence +
  unresolved per item), `capability_matrix.json` (counts + lists),
  `ganna_reference_audit.json` (absence record + source-file field mapping),
  `lane_manifest.json` (mirrors code lanes exactly), `workload_model.json`
  (measured anchors + projections policy), `concurrency_config.json`.
- Code (additive, `app/pipeline/`): `capability_tiers.py` (tiers, tier
  assignment, LaneContract, LANES, WorkerConfig + env loader); `contracts.py`
  gains EquipmentRecord/ScheduleRecord; `structured_data.py` gains generic
  bilingual BOQ normalizer; `jobs.py` gains optional lane/tier/worker/
  structured telemetry fields (defaults preserve 4A behavior).

## Headline
24 deterministic / 17 AI / 1 human-only / 5 hybrid capabilities; structured
path validated end-to-end on Mobile-shape BOQ (generic aliases, row lineage,
non-tables refused); tiers abstract with env names; workers bounded at 2/OFF.
