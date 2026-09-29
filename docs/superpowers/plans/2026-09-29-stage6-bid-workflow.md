# Stage 6 Bid Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eligibility gate before AI, RFP sections + past suppliers, shared-login team with tasks and department votes, a weighted Go/No-Go score, cleaner Q&A, no value estimate.

**Architecture:** New focused backend modules (`eligibility.py`, `sections.py`, `team.py`, `scoring.py`) behind thin FastAPI routes in `app/api/routes.py`; new SQLAlchemy tables created by `init_db` (`create_all`) plus one `ALTER` for `tenders.outcome`. Frontend: new cards in Settings and TenderWorkspace, grouped-task notifications.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, pytest; React/Vite/Tailwind, vitest; i18n via `useT()` + `src/i18n/ar/*.js`.

**Spec:** `docs/superpowers/specs/2026-09-29-stage6-bid-workflow-design.md`

Plan is intentionally compact: the user asked to start right after the spec, and to economise tokens. Each task lists files, interfaces and the tests that pin it; code follows existing patterns in the named files.

## Global Constraints
- Per-account isolation: every new row carries `owner_email` (via `app/access.owner_for_new_rows`) and every read filters by it; other accounts get 404.
- Gate is deterministic (no model call) and must finish in seconds.
- Default weights 40/20/15/25; thresholds GO >= 70, REVIEW 50-69, NO_GO < 50; any hard-gate FAIL -> NO_GO.
- UI strings English in code, Arabic (MSA) in `src/i18n/ar/*.js`; straight quotes in code.
- No git push; commit per task.

## Review Focus
1. Empty capability profile -> gate skipped with a visible note, never blocks. (Task 3 test)
2. Tender with no detectable kV/country -> UNCLEAR, not FAIL. (Task 3 test)
3. Override on an INELIGIBLE tender reprocesses without re-running extraction and never re-blocks. (Task 3 test)
4. Score with zero available factors -> score None + "not enough data", no division by zero. (Task 6 test)
5. Another account cannot read/write tasks, votes, capability, sections of someone else's tender. (Task 5 test)

---

### Task 1: Accuracy fixes (Q&A items, rule cues, email)
**Files:** Modify `app/pipeline/ambiguity.py` (consumer only), `app/issues.py`, `app/pipeline/rule_category.py`, `app/api/routes.py` (email uses questions); Test `tests/test_6_fixes.py`, update `tests/test_5h_features.py` as needed.
- Questions only from kinds `missing-value` (TBD) and genuine clarifications; `unclear-applicability` and `undefined-term` (model doubts) are no longer created as questions and their open, unanswered rows are superseded.
- Each question detail = requirement quote (<=300 chars) from the analysis row; source file + page kept.
- New rule cues: LEGAL for "Paragraph N.N"/"Schedule "A|B|C"" clause edits and notices between the Parties; PERSONNEL for "CONTRACTOR('s) personnel"; TECHNICAL for overload, short circuit, withstand, surge, handling/delivery/storage, trend.
- Tests: question detail contains the quote; model-doubt kinds produce no question; new cue parametrized cases; re-measure on a new blind sample (reported, not a unit test).
- Commit.

### Task 2: Remove expected value
**Files:** Delete `app/market.py`; modify `app/api/routes.py` (drop `/value-estimate`), `app/news.py` (drop `refresh_awards` call), `app/models.py` (drop `MarketAward`), `frontend/src/components/RecommendationPanel.jsx`, `frontend/src/api/client.js`, `frontend/src/i18n/ar/recommendation.js`; tests `tests/test_5j_recommendation.py` (drop estimate tests).
- Test: `GET /api/tenders/X/value-estimate` -> 404; panel test has no value block.
- Commit.

### Task 3: Capabilities + eligibility gate
**Files:** Modify `app/models.py` (`CompanyCapability`, `EligibilityResult`), `app/processing.py` (hook after EXTRACTION), `app/api/routes.py`; Create `app/eligibility.py`; Test `tests/test_6_eligibility.py`.
**Interfaces (produces):**
- `CompanyCapability(id=account key, work_types JSON list, max_kv float, countries JSON list, registrations JSON list, certifications JSON list, years_experience float, annual_turnover float, turnover_currency str)`
- `check(capability: dict|None, title: str, sources: list[SourceText]) -> {"status": "ELIGIBLE"|"INELIGIBLE"|"SKIPPED", "checks": [{"key","label","result": "PASS"|"FAIL"|"UNCLEAR","detail","evidence": {"file","page","quote"}|None}]}`
- `EligibilityResult(tender_id pk, result JSON, override_by str|None, override_reason str|None, created_at)`
- Routes: `GET/PUT /api/company-capability`; `GET /api/tenders/{id}/eligibility`; `POST /api/tenders/{id}/eligibility/override {reason}` -> starts processing again.
- Processing: after EXTRACTION, unless an override exists: run `check`; store result; if INELIGIBLE -> `job.status="INELIGIBLE"`, stage `ELIGIBILITY`, HIGH issue kind `ineligible` with reasons, return before AI.
- Tests: empty profile -> SKIPPED; kV above max -> FAIL with evidence page; work type mismatch -> FAIL; missing country -> UNCLEAR; ISO demanded but not held -> FAIL; override path -> gate skipped; job status INELIGIBLE on FAIL (processing unit test with a stub source list).
- Commit.

### Task 4: RFP sections + past suppliers
**Files:** Create `app/sections.py`; modify `app/api/routes.py`; Test `tests/test_6_sections.py`.
**Interfaces:** `split_sections(sources) -> [{"document","title","page_from","page_to","discipline"}]`; `suppliers_by_discipline(db, owner_email) -> {discipline: [{"contractor","quotes","selected","avg_fit","last_tender"}]}`; `GET /api/tenders/{id}/sections` -> `{"sections":[...+"suppliers":[...]], "disciplines": [...]}`. Sources read from the extraction checkpoint cache (`app/pipeline/checkpoint.py`) or, when absent, from analysis requirement pages.
- Tests: headings split with page ranges; discipline tagging; suppliers ranked selected desc then fit; other account's quotations excluded.
- Commit.

### Task 5: Team, tasks, votes, outcome
**Files:** Modify `app/models.py` (`TeamMember`, `TenderTask`, `DepartmentVote`, `Tender.outcome` + ALTER in `app/database.py`); Create `app/team.py`; modify `app/api/routes.py`, `app/issues.py` (task-group notification); Test `tests/test_6_team.py`.
**Interfaces:** `/api/team` CRUD; `/api/tenders/{id}/tasks` CRUD; `/api/tasks/groups` -> `[{"title","tasks":[...],"tenders":[...]}]` (Jaccard >= 0.6 on normalised tokens, >= 2 tasks, >= 2 tenders or same tender dupes); `/api/tenders/{id}/votes` GET/PUT (unique tender+member); `vote_summary(votes) -> {"overall": {"approve","reject","abstain","approve_pct"}, "by_department": {...}}`; `PUT /api/tenders/{id}/outcome`.
- Tests: grouping; vote upsert + percentages; isolation (other account 404); outcome validation.
- Commit.

### Task 6: Go/No-Go score
**Files:** Create `app/scoring.py`; modify `app/api/routes.py` (`GET /api/tenders/{id}/score`, `GET/PUT /api/score-weights`), `app/recommendation.py` (include score); Test `tests/test_6_scoring.py`.
**Interfaces:** `compute(factors: dict[str, float|None], weights: dict, hard_fail: bool) -> {"score": float|None, "band": "GO"|"REVIEW"|"NO_GO"|None, "factors": [{"key","value","weight","counted","reason"}]}`; factor builders `fit_factor`, `history_factor`, `partners_factor`, `votes_factor`.
- Tests: all factors -> weighted mean; missing factor renormalised; none -> score None; hard fail -> NO_GO even at 90; thresholds at 50/70 boundaries.
- Commit.

### Task 7: Frontend
**Files:** Modify `frontend/src/pages/Settings.jsx` (Capabilities, Team, Weights cards), `frontend/src/pages/TenderWorkspace.jsx` (eligibility banner + override, sections/suppliers, tasks, votes, outcome), `frontend/src/components/RecommendationPanel.jsx` (score breakdown), `frontend/src/pages/Notifications.jsx` (task groups), `frontend/src/api/client.js`, NewTender/TenderWorkspace/GoNoGo terminal statuses include `INELIGIBLE`; Create components `EligibilityCard.jsx`, `SectionsCard.jsx`, `TasksCard.jsx`, `VotesCard.jsx`; Arabic in `src/i18n/ar/stage6.js` (registered in the dictionary index); Tests in `src/components/__tests__/stage6.test.jsx`.
- Tests: eligibility banner shows reasons + override button; votes card shows percentages; score shows factors and "not counted".
- Commit.

### Task 8: Verify end to end
- Full backend + frontend suites, production build.
- Live on Turaif in the browser: fill capabilities (a mismatch -> INELIGIBLE banner, then override), sections + suppliers, add tasks (grouped notification), votes, outcome, score.
- `superpowers:verification-before-completion`, code review of the branch diff, final Arabic report.
