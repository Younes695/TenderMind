# TenderMind — AI Pipeline Contracts (Stage 4A)

Code: `app/pipeline/contracts.py`. UI-facing shape unchanged
(`GET /tenders/{id}/analysis` fields); these types govern the internals.

## Separation rule

`RAW SOURCE != CANDIDATE != LLM OUTPUT != CANONICAL REQUIREMENT != EVIDENCE`

| Type | Built by | Carries | Must NEVER carry |
|---|---|---|---|
| `DocumentArtifact` | ingestion/extraction | filename, path, ext, status, counts, error | conclusions |
| `SourceText` | extraction | document, page, text, method, ocr flag | categories |
| `StructuredTable` / `FormRecord` / `CommercialLineItem` / `ProjectExperienceRecord` | structured adapter | normalized rows/fields | interpretations |
| `RequirementCandidate` | discovery | candidate_id (`chunk-XXXX-seg-YY`), parent ref, doc, page, text, span, signal categories, quality flags, merged_from | model output |
| `LLMNormalizationResult` | model ONLY | summary, category, mandatory, applicable_entity | ids, provenance, source, evidence |
| `ValidatedRequirement` | post-processing | canonical `REQ-XXX` + LLM semantics + candidate provenance | model-supplied identity |
| `EvidenceLink` | post-processing | 1-to-1 link, fact == summary, same source | anything generated |
| `ProcessingStageResult` | every stage | stage, status, real counts, errors, latency | fake percentages |
| `TenderAnalysisResult` | runner | full canonical payload + failures listed | silent drops |

## Minimal LLM contract (production two-stage path)

Model returns ONLY:
`{"requirements": [{"summary": "...", "category": "...", "mandatory": null, "applicable_entity": null}]}`
(one object; category from the validated 13-value list incl. UNKNOWN).
The model MUST NOT produce candidate IDs, evidence IDs, source_document, page,
provenance, or canonical IDs — the provider drops anything beyond the four
fields, and post-processing binds provenance deterministically from the candidate.

Stage 3C integrity rules preserved: per-chunk ID correction intent (here by
construction — IDs are never requested), cross-chunk attachment rejected by the
chunk-prefix drift guard, orphan evidence rejected, `UNKNOWN != FALSE` and
UNKNOWN is never coerced (it flows to finals as a quarantine category to be
filtered before decision surfacing).

## Failure semantics

`FailureCode` enum, explicit at every boundary: discovery rejections
(`no_signal`, `mixed_multi_category`, `ocr_garbage`, `tiny`, `SKIPPED_TINY_INPUT`),
LLM outcomes (`timeout`, `http_error`, `transport_error`, `empty`, `malformed`,
`wrong_shape`, `multi`, `bad_category`), validation (`grounding measured`,
`provenance_drift`, `orphan_evidence`), documents (`COMPLETE/PARTIAL/FAILED/
UNSUPPORTED`). Timeout/malformed/contract-violation → candidate failed/unknown,
NO requirement fabricated, NO silent recovery. Fallback models plug into
`Router.fallback_policy` later; policy today: explicit failure.

## Provenance guarantees

`provenance.validate_provenance()` (R1–R6): requirement fields == candidate
fields (doc/page/text); parent chunk present; evidence links an existing
same-candidate requirement with identical doc/page and fact == summary; final
IDs canonical `REQ-XXX`. Empty violation list == integrity holds. The runner
runs it on every job (VALIDATING stage); violations downgrade the job to PARTIAL
with the violations listed.
