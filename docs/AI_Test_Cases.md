# AI-Specific Test Cases — TenderMind v1 (Test #001)
**Executable via `tests/test_decision_engine.py` + `tests/test_adversarial.py` — traceable to engines.**

| Test ID | Component | Input | Expected Output | Engine | Gold Trace |
|---|---|---|---|---|---|
| AI-DOC-001 | Document Intelligence | Native Sarai RFP p.2 PDF (Arabic) | Extract “First-category” + page 2 + table EGP 5,700,000 with bbox + confidence ≥0.95 | Doc Intelligence | document_extraction_schema.json |
| AI-DOC-002 | OCR | Scanned Arabic cert (image) | OCR F1 ≥0.85 + page provenance | OCR | scanned sample |
| AI-REQ-001 | Requirement Extraction | Sarai pages (RFP + Vols) | Exactly 21 requirements A-U, REQ-A HARD_GATE GIZA mandatory true | Requirement Extraction → `seed.py` REQ-A…U | requirement_schema.json + gold_requirements |
| AI-REQ-002 | Requirement Extraction | Ambiguous clause “qualification applies to...” | REQ-AMB applicable_entity=AMBIGUOUS → REVIEW + ambiguity_note | Requirement Extraction + status.py | ADV-AMBIG-001 |
| AI-EVI-001 | Evidence Extraction | Consortium Agreement rev1.doc Page 1 | E-001 PASS CONSORTIUM with quote “Consortium between...” + Page 1 | Evidence Extraction | gold_evidences E-001 |
| AI-EVI-002 | Evidence Extraction | Certificate with valid_until 2020-01-01 | Extract valid_until + status PASS but downstream REVIEW (expired) | Evidence Extraction + status.py | ADV-EXPIRED-001 |
| AI-MAT-001 | Matching | Second Category cert vs REQ-A (GIZA First) | Status FAIL → decision NO_BID + HARD_GATE_FAIL + provenance | status.py + decision.py | ADV-NEG-001 |
| AI-MAT-002 | Matching | First vs Second Category both vs REQ-A | Status REVIEW + conflicts[] with “First vs Second” reason | status.py + explanation.py | ADV-CONFLICT-001 |
| AI-MAT-003 | Matching | HYOSUNG cert for GIZA REQ-A | Filtered → MISSING_EVIDENCE (applicability_mismatch) | status.py | ADV-ENTITY-001 |
| AI-MAT-004 | Matching | Other tender non-reusable vs REQ-C | Filtered → MISSING | status.py | ADV-WRONG-001 |
| AI-MAT-005 | Matching | Reusable First Category from OTHER vs REQ-A | PASS (reusable true) | status.py | ADV-WRONG-002 |
| AI-MAT-006 | Matching | OEM E-003 vs REQ-K (type-test) | No cross-match, REQ-K remains MISSING | status.py (explicit EvidenceMatch) | ADV-OEM-001 |
| AI-DEC-001 | Decision | Base seed (3 PASS, 1 REVIEW, 17 MISSING) | REVIEW LOW MANDATORY_GATE_MISSING, 0 hard fails, 6 blockers | decision.py | expected_decision |
| AI-DEC-002 | Decision | All 7 risks HIGH, no FAIL | REVIEW (COMMERCIAL_RISK_REVIEW) never NO_BID | decision.py | ADV-RISK-001 |
| AI-DEC-003 | Decision | 0 evidences (all missing) | All MISSING, REVIEW, hard_fail 0 | decision.py | ADV-MISSING-001 |
| AI-EXP-001 | Explainability | Any decision | Explanation has 8 fields + provenance_chain + summary + hard_failures/missing/risks/supporting/conflicts/rules | explanation.py | explanation_schema.json |
| AI-EXP-002 | Explainability | Base decision | supporting_evidence 3 items with doc+page, missing 18 with priority/owner, risks 7, conflicts 0 | explanation.py | gold dataset metrics |
| AI-HUM-001 | Audit | System REVIEW → human BID override | Original REVIEW preserved (is_override false), new BID is_override true + audit reviewer/timestamp/reason | api/routes.py /override + audit | ADV-OVERRIDE-001 |
| AI-INT-001 | Provenance | Every PASS/FAIL | Has source_document + page/section + evidence_id + confidence; MISSING has priority/owner/why | status.py + missing_evidence.py | test_7 |
| AI-INT-002 | Tender-stage | REQ-C missing | Priority CRITICAL, MISSING_EVIDENCE not permanent FAIL | missing_evidence.py | ADV-TENDER-STAGE-001 |

**Run:**
```powershell
python -c "import tests.test_adversarial as a; a.test_8_evidence_conflict()"
python -c "from fastapi.testclient import TestClient; from app.main import app; c=TestClient(app); print(c.get('/api/tenders/SA-2018-HV2/explanation').json()['decision'])"
```

**Coverage:** 20 test cases spanning 5 components, all tied to gold dataset phenomena (positive, negative, missing, conflicting, expired, wrong-tender, ambiguous) per spec §7.
