# Stage 3I — Deterministic Pre-Segmentation Rules (evaluation adapter only)

These rules split a parent chunk into small single-purpose candidate spans.
They reuse the existing production `GENERIC_PATTERNS` and never call the LLM.

## Rules

1. **Sentence splitting (abbreviation-safe):** split the parent text on newlines
   first (preserves list structure), then split each line on sentence boundaries
   where a terminator (`.`, `;`, `?`, `!`) is followed by whitespace and an
   uppercase letter, digit, or opening quote (`(?<=[.;?!])\s+(?=[A-Z0-9"\u201c])`).
   This keeps abbreviations such as `No. (1)` intact (`.` followed by `(` does
   not split). Each span records exact `[start, end]` character offsets.

2. **Signal detection:** for each sentence, run the production `GENERIC_PATTERNS`
   regexes (lowercased, same as `extract_requirements_generic`) and record all
   matching categories. No new patterns, no tender-specific terms.

3. **Quality gate (reject, do not silently pass):**
   - empty/whitespace-only → reject `empty`
   - stripped length < 20 chars (`MIN_CANDIDATE_CHARS`) → reject `tiny`
     (e.g., `2- 220 kV GIS`, `Currency: EGP.`, `Schedule No.`)
   - printable ratio < 0.7 (`MIN_PRINTABLE_RATIO`) → reject `ocr_garbage`
   - zero pattern hits → reject `no_signal`
     (e.g., `Client: NUCA …`, `Deadline: submission 15 of March, 2024.`,
     `CVs must be submitted.`, `Manufacturer: Hyosung or equivalent.`)
   - 3+ distinct hit categories → reject `mixed_multi_category`
     (e.g., the `Schedule No. (1) Bill of Quantities … 220/22/22 kV …` title line
     hits SCHEDULE + TECHNICAL + COMMERCIAL)
   - otherwise accept (1–2 hits allowed; the obvious primary-purpose gold is
     recorded separately and may differ from the raw signal list).

4. **Accepted candidate record:** `candidate_id` (`<parent>-seg-NN`),
   `parent_chunk_id`, `source_document`, `page`, verbatim `source_text`,
   `span`, `deterministic_signal_categories`. Source text is never rewritten.

## Known signal gaps (observed, not fixed here)

- The SCHEDULE pattern has no `deadline`/`submission` terms, so an explicit
  `Deadline: submission …` sentence yields `no_signal`.
- No pattern maps to SUBMISSION, so `CVs must be submitted.` yields `no_signal`.
- The TECHNICAL pattern matches the substring `gis` inside `registered`
  (`re**gis**tered`), so the First-Category legal sentence carries a spurious
  TECHNICAL signal.
- `Manufacturer:`/`OEM` have no pattern; `Validity 180 days …` has no pattern.

These gaps are reported as findings; the splitter was not extended to hide them.
