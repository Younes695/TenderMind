# Reconciliation MVP (Stage 4F)

Deterministic only. Input: validated requirements + line items + addenda/
clarifications. No semantic reasoning, no invented winners.

## Behaviors
- Duplicates: cross-document normalized-summary groups (evidence = member IDs).
- Amendments: link ONLY on explicit affected_item/section text match
  (ClarificationRecords match on reference/question/response). Never from
  filenames. Lifecycle: ORIGINAL default; AMENDED / CLARIFICATION with links;
  requirements from addendum/clarification docs without explicit links →
  SUPERSESSION_UNKNOWN (honest unknown, never inferred impact).
- Conflicts: same BOQ item code with differing quantity/unit/price across
  rows/docs; both sides preserved + REVIEW_REQUIRED.
- Measured: 3 real conflicts on Mobile BOQ (same codes, differing quantities).

## Not built (4G+)
Semantic duplicates, conflict auto-resolution, supersession representation
beyond status flags, O(n²) pair strategy for large sets.
