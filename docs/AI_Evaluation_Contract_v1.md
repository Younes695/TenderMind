# TenderMind AI Evaluation Contract v1
**Based on Test #001: Sarai 220/22kV GIS Substation (No. SA/2018/HV2) — HYOSUNG / GIZA SYSTEMS CONSORTIUM**
**Status: Specification / Evaluation Phase — NOT implementation**
**Owner: AI Layer — Abd-Elrahman (AI Engineer)**
**Source of truth: `TenderMind_OpenCode_Build_Package_Test001.md` + `app/models.py` + `app/seed.py` (SA-2018-HV2)**

---

## 0. Invariants (Test #001 Semantics — Non-Negotiable)

| Rule | Meaning | Enforcement |
|---|---|---|
| `MISSING_EVIDENCE ≠ FAIL` | Absence of evidence is not proof of failure | Engine must never auto-convert missing to FAIL; `HARD_GATE_FAIL` only if explicit contradictory evidence |
| `RISK ≠ NO_BID` | Risks are REVIEW, never automatic NO_BID | `Risk.decision_impact` is always REVIEW per §7 |
| `Ambiguity/Conflict → REVIEW` | Conflicting or ambiguous evidence requires human | `status=REVIEW` + `conflicts[]` + explanation, not arbitrary PASS/FAIL |
| `PASS/FAIL ⇒ Provenance` | Every material PASS/FAIL must cite `source_document + page/section + evidence_id + quote` | `status.py` provenance check; test_7 enforces |
| `Expired ≠ PASS` | Historical validity does not imply current qualification | `valid_until < now` → REVIEW (test_9) |
| `Entity-specific ≠ interchangeable` | GIZA-first-category cannot be satisfied by HYOSUNG cert | `applicable_entity` strict filter (test_6) |
| `Tender-stage ≠ Company-permanent` | Tender security `REQ-C` is submission item, not company FAIL | `REVIEW` with `reusable=False` semantics (test_5) |
| `Human override preserved` | AI recommends, human decides | `Decision.is_override` + `DecisionAudit` (test_12) |

Any AI that violates these fails evaluation regardless of accuracy.

---

## 1. Arabic Document Extraction Contract

**Goal:** From Arabic/English tender PDFs (native + scanned) extract layout-aware, page-grounded text + tables + deadlines + quantities.

**Input:** Tender package PDF(s) — native or scanned (Arabic). Example: `Sarai RFP p.2`, `Volume 1 Section 1 p.2`, `External Consortium Agreement rev1.doc`.

**Output (per page):**
```json
{
  "tender_id": "SA-2018-HV2",
  "source_document": "Sarai RFP.pdf",
  "page_number": 2,
  "language_detected": "AR",
  "text_blocks": [{"bbox": [x1,y1,x2,y2], "text_ar": "عضوية الاتحاد المصري للتشييد فئة أولى", "text_normalized": "First-category Egyptian Union membership", "confidence": 0.99}],
  "tables": [{"table_id": "T-001", "bbox": [...], "headers": ["Requirement"], "rows": [["First Category"]], "extraction_confidence": 0.97}],
  "ocr_applied": false,
  "ocr_model": null,
  "extraction_confidence": 0.98,
  "checksums": {"page_hash": "sha256:..."}
}
```

**Requirements:**
- Preserve `original Arabic text + normalized text + (optional) translated interpretation` — never erase Arabic evidence (spec §10).
- Preserve `page_number + section/heading + table location + bbox` for provenance.
- `ocr_applied` flag + model/version; `extraction_confidence` per page + per block.
- Page-level provenance required for every downstream requirement — no requirement without `tender source/page`.
- Table extraction for BoQ, guarantee amounts (EGP 5,700,000), voltage (220kV), capacity (175MVA).

**Evaluation:** Page-level text F1 ≥0.95 on native, ≥0.85 on scanned Arabic; table cell accuracy ≥0.90; page number accuracy 100% (see §7 metrics).

---

## 2. Requirement Extraction Contract

**Goal:** From extracted pages, produce structured requirement objects — **do not invent**.

**Output per requirement (maps 1:1 to `Requirement` model):**
```json
{
  "requirement_id": "REQ-A",
  "tender_id": "SA-2018-HV2",
  "category": "LEGAL",
  "requirement": "First-category Egyptian Union for Construction Contractors membership required for local partner",
  "mandatory": true,
  "requirement_type": "HARD_GATE",
  "evidence_required": ["valid_first_category_membership_certificate/card"],
  "evaluation_logic": {"PASS":"Valid evidence confirms","FAIL":"Evidence shows insufficient","MISSING_EVIDENCE":"No valid evidence","REVIEW":"Ambiguity"},
  "source_document": "Sarai RFP p.2; Volume 1 Section 1 p.2",
  "page_or_section": "RFP p.2 / Vol1 S1 p.2",
  "applicable_entity": "GIZA",
  "ambiguity_note": null,
  "confidence": 0.96,
  "source_spans": [{"page":2, "bbox":[...], "quote_ar": "عضوية الفئة الأولى", "quote_en": "First-category membership"}]
}
```

**Fields:**
- `category`: VERIFIED enum `LEGAL | COMMERCIAL | TECHNICAL | EXPERIENCE | PERSONNEL | HSE | QA_QC | EQUIPMENT | SUBCONTRACTOR | FINANCIAL | SCHEDULE | SUBMISSION`
- `requirement_type`: `HARD_GATE | EXPERIENCE | TECHNICAL | SUBMISSION | ...` (spec §4)
- `mandatory`: boolean (HARD_GATE always mandatory)
- `applicable_entity`: `CONSORTIUM | GIZA | HYOSUNG | ANY | AMBIGUOUS` — per spec §19 #6. If tender clause does not specify, AI must output `AMBIGUOUS` + `ambiguity_note` → downstream `REVIEW`.
- `evidence_required`: list of document types (from tender clause, not invented).
- `tender source/page` + `confidence` (0-1) + `source_spans` with Arabic quote + bbox.

**Test #001 Gold:** Exactly 21 requirements A-U per `seed.py` — no hallucinated extra, no missing mandatory. Categories/types/mandatory/applicable_entity must match gold.

**Evaluation:** Requirement Set F1 (precision/recall on requirement IDs + text similarity ≥0.85) + Mandatory accuracy 100% + Applicable entity accuracy ≥0.95.

---

## 3. Evidence Extraction Contract

**Goal:** From company documents (consortium agreement, certs, projects, CVs), extract evidence facts with provenance — **do not invent**.

**Output per evidence (maps to `Evidence` model):**
```json
{
  "evidence_id": "E-001",
  "company_id": "HYOSUNG_GIZA",
  "requirement_supported": "REQ-R",
  "evidence_type": "CONSORTIUM_AGREEMENT",
  "fact": "Hyosung and Giza Systems form a consortium with joint and several liability.",
  "status": "PASS",
  "source_document": "SARAI 220KV GIS Substation - External Consortium Agreement rev1.doc",
  "page_or_section": "Page 1, Preamble + Joint Liability section",
  "source_quote": "Consortium between Hyosung Corporation and Giza Systems...",
  "extraction_confidence": "HIGH",
  "applicable_entity": "CONSORTIUM",
  "valid_from": null,
  "valid_until": null,
  "tender_source_id": null,
  "reusable": true,
  "notes": "Spec §5 R — PASS"
}
```

**Fields:**
- `evidence_type`: `CONSORTIUM_AGREEMENT | CERTIFICATE | PROJECT_REFERENCE | CV | HSE etc.`
- `applicable_entity`: who the evidence belongs to (CONSORTIUM vs HYOSUNG vs GIZA)
- `valid_from / valid_until`: for time-bound certs (e.g., membership 2024-2025). If `valid_until < now` → downstream REVIEW (test_9), not PASS.
- `tender_source_id + reusable`: if `tender_source_id != current tender` and `reusable=false` (e.g., other tender's bid security) → must not be used for Sarai.
- `source_document + page/section + quote + confidence` mandatory for every PASS/FAIL.
- `status`: AI's preliminary assessment of the fact (PASS/FAIL/REVIEW) — final requirement status decided by matching engine, not evidence alone.

**Test #001 Gold:** Exactly 4 evidences: E-001(R PASS CONSORTIUM), E-002(B PASS HYOSUNG), E-003(J PASS HYOSUNG), E-004(U REVIEW CONSORTIUM). All other requirements have **zero** evidence → MISSING, not invented.

---

## 4. Evidence Matching Contract

**Goal:** Decide per requirement: `PASS | FAIL | MISSING_EVIDENCE | REVIEW | NOT_APPLICABLE` with **why**.

**Input:** One `Requirement` + 0..N `Evidence` linked via `EvidenceMatch`.

**Matching Rules (implemented in `status.py`):**

| Condition | Output |
|---|---|
| No applicable evidence (0 matches or all filtered by applicability/expiry/wrong-tender) | `MISSING_EVIDENCE` + reason = `evaluation_logic.MISSING_EVIDENCE` |
| Any non-expired applicable evidence `status=FAIL` and no conflict | `FAIL` + provenance |
| Any `valid_until < now` | `REVIEW` + `expired:true` + reason "Evidence expired — human review required" |
| `applicable_entity` mismatch (e.g., GIZA req + HYOSUNG evidence) | Filtered → `MISSING_EVIDENCE` with `applicability_mismatch:true` |
| `tender_source_id != current AND reusable=false` | Filtered → MISSING |
| `AMBIGUOUS` requirement | `REVIEW` + ambiguity_note |
| Multiple evidences with conflicting status (PASS vs FAIL) or conflicting facts (First vs Second, 175MVA vs 100MVA) | `REVIEW` + `conflicts:[{evidence_ids, reason}]` (test_8) |
| All applicable `PASS` and none of above | `PASS` |
| Any `REVIEW` among applicable | `REVIEW` |

**Output per requirement:**
```json
{
  "requirement_id": "REQ-A",
  "status": "MISSING_EVIDENCE",
  "evidence_ids": [],
  "reason": "No valid evidence found.",
  "provenance": [],
  "conflicts": [],
  "expired": false,
  "applicability_mismatch": false
}
```

**OEM Isolation (Test 4):** Evidence `E-003` matched only to `REQ-J`. It must **not** satisfy `REQ-K/L/D/I` — enforced by explicit `EvidenceMatch`; no implicit cross-requirement inference.

---

## 5. Decision Logic Contract

**Goal:** From all requirement statuses + risks, produce `BID | REVIEW | NO_BID` deterministically per spec §6 hierarchy:

1. If any `mandatory HARD_GATE` is `FAIL` → `NO_BID` (`HARD_GATE_FAIL`, HIGH confidence)
2. Else if any `mandatory HARD_GATE` is `MISSING_EVIDENCE` → `REVIEW` (`MANDATORY_GATE_MISSING`, LOW)
3. Else if any `mandatory HARD_GATE` is `REVIEW` → `REVIEW` (`MANDATORY_GATE_REVIEW`, LOW)
4. Else if any `mandatory EXPERIENCE/TECHNICAL/...` is `MISSING/REVIEW` → `REVIEW` (`EXPERIENCE_EVIDENCE_MISSING`, LOW)
5. Else if any `HIGH` risk → `REVIEW` (`COMMERCIAL_RISK_REVIEW`, MEDIUM)
6. Else → `BID` (`ALL_MANDATORY_PASS`, HIGH)

**Never:** `MISSING → FAIL`, `Risk HIGH → NO_BID`.

**Output (Decision):**
```json
{
  "tender_id": "SA-2018-HV2",
  "decision": "REVIEW",
  "confidence": "LOW",
  "hard_fail_count": 0,
  "mandatory_missing_count": 1,
  "top_blockers": ["First-category membership", "Tender security EGP 5.7M", "..."],
  "top_risks": ["Fixed-price exposure", "FX exposure", "..."],
  "rules_triggered": ["MANDATORY_GATE_MISSING"],
  "supporting_requirements": ["REQ-B","REQ-J","REQ-R"],
  "supporting_evidence": ["E-002","E-003","E-001"],
  "missing_evidence": ["ME-A","ME-C", "..."],
  "risks": ["R-001", "..."]
}
```

**Test #001 Expected (dynamic):** `REVIEW, LOW, hard_fail 0, mandatory_missing 1, top 6 blockers (A,C,D,E,F,G ...), top 4 risks (Fixed-price, FX, Schedule/LD, ...)` — per `seed.py` §14.

---

## 6. Explainability Contract

**Every decision must be reproducible via provenance chain:** `Tender → Requirement → Evidence → Evaluation (status+reason+provenance) → Risk → Decision (rules_triggered) → Explanation`

**Machine-readable Explanation Object (required per decision):**
```json
{
  "decision": "REVIEW",
  "confidence": "LOW",
  "summary": "REVIEW — DO NOT BID YET: 18 evidence gaps require human review. Top blocker: First-category membership.",
  "hard_failures": [],
  "missing_evidence": [{"requirement_id":"REQ-A","priority":"CRITICAL","document_needed":"valid_first_category_membership_certificate/card","owner":"Giza Systems / Legal","why_needed":"Mandatory gate","status":"MISSING_EVIDENCE"}],
  "risks": [{"risk_id":"R-001","type":"COMMERCIAL","severity":"HIGH","description":"Fixed-price exposure","mitigation":"Commercial review","decision_impact":"REVIEW"}],
  "supporting_evidence": [{"requirement_id":"REQ-R","evidence_id":"E-001","source_document":"...Agreement rev1.doc","page_or_section":"Page 1, Preamble","fact":"...joint liability","confidence":"HIGH"}],
  "conflicts": [],
  "rules_triggered": ["MANDATORY_GATE_MISSING"],
  "provenance_chain": "Requirement → Evidence → Source Document → Page/Section → Rule → Decision",
  "tender_id": "SA-2018-HV2",
  "decision_id": "DEC-..."
}
```

**Required:** `GET /api/tenders/{id}/explanation` and `GET /export` include explanation; `GET /audit` shows `Decision + DecisionAudit` with reviewer/timestamp/reason; human override creates new `Decision(is_override=true)` + audit, preserving original.

---

## 7. Evaluation Dataset Contract

**File:** `evaluation/sarai_gold_dataset.json` — 21 requirements + 4 evidences + 7 risks as gold, plus 13 adversarial examples covering 7 phenomena:

| Phenomenon | Example IDs | Gold Status | Purpose |
|---|---|---|---|
| Positive (PASS) | E-001→REQ-R, E-002→REQ-B, E-003→REQ-J | PASS | Happy path provenance |
| Negative (FAIL) | E-FAIL-CONTRADICT (Second Category for REQ-A) | FAIL → NO_BID | Explicit contradiction |
| Missing | No evidence for REQ-A/C/D... | MISSING → REVIEW | Absence ≠ failure |
| Conflicting | E-CONFLICT-A (First) + E-CONFLICT-B (Second) vs REQ-A | REVIEW + conflicts[] | Ambiguity detection |
| Expired | E-EXPIRED valid_until 2020-01-01 for REQ-A | REVIEW + expired:true | Validity |
| Wrong-tender | E-WRONG-TENDER (OTHER-001, reusable=false) vs REQ-C | MISSING (filtered) | Reuse policy |
|  | E-WRONG-REUSABLE (OTHER-001, reusable=true) vs REQ-A | PASS (allowed) | Reusable cert |
| Ambiguous | REQ-AMB applicable_entity=AMBIGUOUS | REVIEW + ambiguity_note | Applicability |
| Entity-mismatch | E-HYOSUNG-FOR-GIZA (HYOSUNG for GIZA REQ-A) | MISSING (filtered) | Consortium isolation |
| Tender-stage | REQ-C (submission) missing | MISSING CRITICAL, not permanent FAIL | Stage distinction |

**Metrics (see AI Acceptance Criteria):**
- Arabic page extraction: F1, table cell accuracy, page accuracy
- Requirement extraction: Requirement Set F1 + mandatory/applicable accuracy
- Evidence extraction: Evidence Set F1 + provenance completeness
- Matching: Per-requirement status accuracy (PASS/FAIL/MISSING/REVIEW) macro F1 + conflict detection F1
- Decision: Decision accuracy (BID/REVIEW/NO_BID) + hard_fail vs missing confusion matrix
- Explainability: Provenance completeness (every PASS/FAIL has doc+page) + conflict capture rate

---

## 8. AI Acceptance Criteria (for this contract)

| Metric | Gold | Acceptance (v1) | How Measured |
|---|---|---|---|
| Arabic native page F1 | Sarai PDFs native | ≥0.95 | Token-level F1 vs gold text_blocks |
| Arabic scanned/OCR page F1 | Sample scanned Arabic | ≥0.85 | Same vs gold |
| Table cell accuracy | BoQ/guarantee tables | ≥0.90 | Cell exact match |
| Page number accuracy | All pages | 100% | Must match source page |
| Requirement Set F1 | 21 gold A-U | ≥0.90 (precision/recall on IDs + text ≥0.85) | Compare extracted set vs gold |
| Mandatory / Applicable entity accuracy | Gold mandatory + GIZA/CONSORTIUM | 100% mandatory, ≥0.95 applicable | Exact match |
| Evidence Set F1 | 4 gold evidences | ≥0.90 | Fact + source doc + page match |
| Provenance completeness | Every PASS/FAIL | 100% have doc+page+evidence_id+confidence | Automated check (test_7) |
| Matching status accuracy | 21 statuses + 13 adversarial | ≥0.93 macro F1; `MISSING` never → `FAIL` 100% | Confusion matrix |
| Conflict detection F1 | 2 conflicting examples | ≥0.90 | Detects First/Second conflict as REVIEW |
| Expiry detection | Expired cert | 100% → REVIEW not PASS | Test 9 |
| Decision accuracy | REVIEW/NO_BID/BID | 100% on gold + adversarial (no MISSING→NO_BID) | Test 2/3 |
| Explanation completeness | Per decision | 100% fields present + provenance_chain | Schema validation |

**Gate:** Any invariant violation (MISSING→FAIL, RISK→NO_BID, PASS without provenance, expired PASS, entity-mismatch PASS) → **automatic fail** regardless of F1.

---

## 9. Recommended AI Pipeline Architecture (v1 — Evaluation Phase)

```
[1] Tender Intake (PDF/Doc/ZIP) 
      → Validation → Malware scan
[2] Document Intelligence 
      → Native text extraction (PyMuPDF) + OCR (Azure DI / AWS Textract) per page + language_detect AR/EN
      → Layout analysis (headings, tables via table transformer) + page_number + bbox
      → Output: Arabic Document Extraction JSON (§1) with page provenance
[3] Requirement Extraction (Arabic-capable LLM + Rules)
      → Input: Page JSON + section headings
      → Prompt: Arabic procurement terminology (كراسة، تصنيف، خطاب ضمان) → structured Requirement JSON (§2)
      → Output: Requirement objects with tender source/page + confidence + source_spans (Arabic quote + bbox)
      → Human review gate: requirements diff vs gold
[4] Company Knowledge Base Ingestion
      → Chunking (page/section) + embeddings (Arabic-capable, e.g., Jais/Arctic) + OCR for certs
      → Store: CompanyDocument + Evidence with applicable_entity + valid_until + reusable
      → Output: Evidence JSON (§3)
[5] Evidence Matching (Hybrid Retrieval + Deterministic Rules)
      → Retrieve: hybrid keyword (Arabic) + semantic + filter by applicable_entity/validity/reusable
      → Rerank → EvidenceMatch → Status Engine (status.py) → MISSING/REVIEW vs PASS/FAIL per §4
      → Output: Per-requirement status + provenance + conflicts + expired flags
[6] Risk Engine (Rule-based + LLM Assist)
      → Input: Requirements + Commercial clauses → 7 Sarai risks (fixed-price, FX, LD, guarantee...)
      → Output: Risk objects (type/severity/mitigation) — always REVIEW
[7] Decision Engine (Deterministic §6)  — NOT LLM autonomous
      → Input: statuses + risks → BID/REVIEW/NO_BID + rules_triggered + confidence
      → Output: Decision + build_explanation()
[8] Explainability Layer
      → Machine-readable explanation + provenance chain + export JSON + audit log
      → UI: Tender → Requirements → Evidence → Decision → Missing Checklist → Audit
[9] Evaluation Harness
      → Gold dataset (evaluation/sarai_gold_dataset.json) → metrics per §7 → AI Acceptance gate
```

**Test Ratchet:** Pipeline runs gold + 13 adversarial through `status.py` + `decision.py` + `explanation.py` — same engines used in production (no separate AI vs deterministic path).

---

## 10. AI-Specific Test Cases (Traceable to Engines)

| Test ID | Input | Expected | Engine |
|---|---|---|---|
| AI-DOC-001 | Native Arabic RFP p.2 | Extract “First-category” + page 2 provenance + table guarantee EGP 5,700,000 | Document Intelligence |
| AI-DOC-002 | Scanned Arabic cert | OCR → text F1 ≥0.85 + page provenance | OCR |
| AI-REQ-001 | Sarai pages | 21 requirements A-U exactly, REQ-A mandatory HARD_GATE GIZA | Requirement Extraction |
| AI-REQ-002 | Ambiguous clause | REQ-AMB applicable_entity=AMBIGUOUS → REVIEW | Requirement Extraction + Status |
| AI-EVI-001 | Consortium Agreement rev1.doc Page 1 | E-001 PASS CONSORTIUM with quote + page | Evidence Extraction |
| AI-EVI-002 | Expired cert valid_until 2020 | Extract valid_until + downstream REVIEW not PASS | Evidence Extraction + Status |
| AI-MAT-001 | E-FAIL Second Category vs REQ-A | Status FAIL, decision NO_BID | Matching + Decision |
| AI-MAT-002 | First vs Second conflict vs REQ-A | Status REVIEW + conflicts[] | Matching |
| AI-MAT-003 | Hyosung cert for GIZA REQ-A | Filtered → MISSING (applicability mismatch) | Matching |
| AI-MAT-004 | Other tender non-reusable vs REQ-C | Filtered → MISSING | Matching |
| AI-MAT-005 | OEM E-003 vs REQ-K (type-test) | No cross-match, REQ-K remains MISSING | Matching (explicit EvidenceMatch only) |
| AI-DEC-001 | Base seed (3 PASS, 1 REVIEW, 17 MISSING) | REVIEW LOW MANDATORY_GATE_MISSING, 0 hard fails | Decision |
| AI-DEC-002 | All risks HIGH, no FAIL | REVIEW (COMMERCIAL_RISK_REVIEW) not NO_BID | Decision |
| AI-EXP-001 | Any decision | Explanation has all 8 fields + provenance_chain + summary | Explainability |
| AI-HUM-001 | Human override REVIEW→BID | Original REVIEW preserved, new BID is_override + audit with reviewer/reason | Audit |

All tests must pass against gold — see `tests/test_decision_engine.py` + `tests/test_adversarial.py` as executable contracts.

---

## References
- Models: `app/models.py` — Requirement/Evidence with `applicable_entity`, `valid_until`, `tender_source_id`, `reusable`
- Engines: `app/engines/status.py` (conflict/expiry/applicability), `decision.py` (§6), `explanation.py`, `missing_evidence.py`
- Seed Gold: `app/seed.py` — 21 REQ, 4 E, 7 Risks
- API: `app/api/routes.py` — `/requirements`, `/evidence`, `/risks`, `/missing-evidence`, `/decision`, `/explanation`, `/export`, `/audit`, `/override`
- Evaluation: `evaluation/sarai_gold_dataset.json` + schemas in `schemas/`
