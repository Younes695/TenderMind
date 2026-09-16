# TenderMind — Test #001 Vertical Slice
**Sarai 220/22kV GIS Substation (No. SA/2018/HV2) — HYOSUNG / GIZA SYSTEMS CONSORTIUM**

Status: Validation prototype — evidence-driven Tender Decision Intelligence Engine (not a chatbot).

## Core Flow Proven
`Tender Documents → Requirements (21) → Evidence (4) → EvidenceMatch → PASS/FAIL/MISSING_EVIDENCE/REVIEW → Risks (7) → Missing-Evidence → BID/REVIEW/NO_BID + Full Provenance`

**Live result (dynamic, not hard-coded): `REVIEW — DO NOT BID YET` — LOW confidence, 0 hard fails, 1 mandatory HARD_GATE missing (REQ-A), 7 risks as REVIEW.**

## Tech Stack
- FastAPI + SQLAlchemy (SQLite in %TEMP%\opencode\tendermind) + Pydantic
- No AI hallucination: all evidence carries `source_document + page/section + quote + confidence`; missing stays missing.

## Project Layout
```
TenderMind/
  app/
    database.py          # SQLite (temp) to avoid space/path issues
    models.py            # Company, Tender, Requirement, Evidence, EvidenceMatch, Risk, MissingEvidence, Decision, Audit
    seed.py              # 21 requirements A-U + 4 evidences + 7 risks per spec §5/7/8 + corrections §19
    engines/
      status.py          # PASS/FAIL/MISSING/REVIEW evaluation
      decision.py        # Hierarchy §6: FAIL→NO_BID, MISSING→REVIEW, Risk→REVIEW, never MISSING→FAIL
      missing_evidence.py # CRITICAL/HIGH/MEDIUM/LOW + owner + why_needed
      risk.py (in models) # separate from qualification
    api/routes.py        # REST API + export + override + audit
    main.py              # FastAPI app + startup seed + static frontend
  frontend/index.html    # 6 screens: Tender Intake → Requirements → Evidence → Decision → Evidence Requests → Audit
  tests/test_decision_engine.py # 6 automated tests proving dynamic decision logic
  requirements.txt
  tendermind.db (temp)
```

## Key Implementation Rules (Spec §2,6,15,19)
- **MISSING_EVIDENCE ≠ FAIL** — never convert absence into failure.
- **RISK ≠ NO_BID** — risks are REVIEW only.
- **REVIEW** for ambiguous validity (e.g., REQ-U consortium intent vs bank capacity — E-004 is REVIEW, not PASS).
- **Provenance** on every PASS: `evidence_id + source_document + page/section + quote + confidence`.
- Deterministic, reproducible: same input → same decision; override via audit trail.

## Data Model (Spec §11)
`Company — CompanyDocument — Tender — TenderDocument — Requirement — Evidence — EvidenceMatch — Risk — Decision — MissingEvidence — DecisionAudit`

Stored ID for URL safety: `SA-2018-HV2` (original No. `SA/2018/HV2` preserved in title).

## Requirements (21)
| ID | Category | Mandatory | Type | Current Status | Note |
|---|---|---|---|---|---|
| REQ-A | LEGAL | YES | HARD_GATE | MISSING | First-category membership — CRITICAL |
| REQ-B | TECHNICAL | YES | HARD_GATE | PASS (E-002) | South Korea approved; component check still needed |
| REQ-C | COMMERCIAL | YES | SUBMISSION | MISSING | Tender security 5.7M — CRITICAL |
| REQ-D..I | EXPERIENCE | YES | EXPERIENCE | MISSING | Form E, operation, window, certs, 220kV, 175MVA |
| REQ-J | TECHNICAL | NO | TECH | PASS (E-003) | OEM structural, not per-equipment |
| REQ-K,L | TECH/EQUIP | YES | - | MISSING | Type-tests, operating refs |
| REQ-M,N,O,P | PERSONNEL/HSE/QA/EQUIP | YES | - | MISSING | CVs, HSE, QA, plant |
| REQ-Q | SUBCONTRACTOR | NO | - | MISSING | Low |
| REQ-R | LEGAL | YES | HARD_GATE | PASS (E-001) | Consortium agreement |
| REQ-S,T | FINANCIAL/SCHEDULE | YES | - | MISSING | No invented numbers |
| REQ-U | COMMERCIAL | YES | - | REVIEW (E-004) | Joint liability ≠ bank facility — **correction #1** |

Evidences: E-001 (R PASS), E-002 (B PASS), E-003 (J PASS), E-004 (U REVIEW). All others → no evidence.

## Run

```powershell
cd "C:\Users\EgyTech\Documents\Default Project\TenderMind"
pip install -r requirements.txt
python -c "from app.seed import seed; seed()"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- UI: http://127.0.0.1:8001
- API docs: http://127.0.0.1:8001/docs
- Health: http://127.0.0.1:8001/health

## API Quick Test
```
GET  /api/tenders
GET  /api/tenders/SA-2018-HV2/requirements   -> each shows status + provenance + source page
GET  /api/tenders/SA-2018-HV2/evidence       -> 4 evidences
GET  /api/tenders/SA-2018-HV2/risks          -> 7 risks (all REVIEW)
GET  /api/tenders/SA-2018-HV2/missing-evidence -> actionable checklist with owner/priority
GET  /api/tenders/SA-2018-HV2/decision       -> BID/REVIEW/NO_BID + confidence + blockers + risks
GET  /api/tenders/SA-2018-HV2/export         -> full JSON (Section 12 audit)
POST /api/tenders/SA-2018-HV2/decision/override {reviewer, new_decision, reason}
GET  /api/tenders/SA-2018-HV2/audit          -> decisions + audits
```

## Automated Tests
```
python -m tests.test_decision_engine  # via python -c wrapper due to Windows encoding
# Tests:
# - REVIEW not NO_BID on missing
# - Dynamic recompute after adding evidence (not hard-coded)
# - FAIL triggers NO_BID
# - Provenance present on every PASS
# - Risks separate (7, all REVIEW)
# - MISSING not FAIL + U is REVIEW
```

## Definition of Done — All 12 Checked
1. Sarai tender exists (SA-2018-HV2, MNHD) — /api/tenders
2. Requirements visible (21) — /requirements screen
3. HYOSUNG/GIZA evidence exists (4) — /evidence
4. Evidence matched — EvidenceMatch + provenance per requirement
5. Each requirement shows PASS/FAIL/MISSING/REVIEW — table + engine
6. Risks shown separately (7, REVIEW) — Risks card
7. Missing evidence actionable (ME-A..ME-U with owner/priority) — Missing card
8. System produces BID/REVIEW/NO_BID — Decision badge + API
9. Click decision/blocker shows source doc + page/section — provenance chain + export
10. Full decision exported as JSON — /export (Section 12)
11. Automated tests prove logic — tests/test_decision_engine.py
12. Human override with audit — Override button + /audit (DecisionAudit)

## Guardrails Implemented
- No hallucinated evidence (seed only 4 real evidences, others remain missing)
- No invented pages/quotes (all quotes from agreement preamble)
- Blank Form E → missing, not proof of no projects (§19 #5)
- U = REVIEW, C = MISSING submission, J ≠ K/L (§19 #1-3)
- Tender source and company source separate datasets
- Legal interpretation not presented as advice

## Next Step
Vertical slice passes. Do NOT build full platform until reviewer approves this slice via UI + JSON + tests.
