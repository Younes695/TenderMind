# TenderMind — FRONTEND ANALYSIS (actual repo inspection)

> Date: 2026-09-20 | Role: FRONTEND | Repo: https://github.com/Younes695/TenderMind
> Source of truth: actual source code (`frontend/index.html`, `app/main.py`, `app/api/routes.py`,
> `app/models.py`, `app/seed.py`, `app/engines/*`, `schemas/*`, `evaluation/sarai_gold_dataset.json`,
> `tests/test_decision_engine.py`, `docs/FRONTEND_TASKS.md`, `docs/FRONTEND_BACKEND_HANDOFF.md`).
> Handoff docs were cross-checked against code — disagreements noted explicitly.

Labels used below: `EXISTING` | `PARTIAL` | `MISSING` | `SARAI-SPECIFIC` | `NEEDS REFACTOR` | `BLOCKED` | `PROPOSED`

---

## 1. Current Frontend architecture

- **Framework: none. `EXISTING`** — plain static `frontend/index.html` (150 lines, inline `<style>` + inline `<script>`, no build, no npm, no React/Vue/Next/Tailwind).
  The `FRONTEND_TASKS.md` proposal (React/Vite + Tailwind, `frontend/src/*`) was **never implemented** — there is no `frontend/src`, no `package.json`, no `vite.config`, no Tailwind.
- **Serving: `EXISTING`** — `app/main.py:28-36` mounts `frontend/` at `/static` and serves `index.html` at `GET /`. No SPA router, no bundler.
- **Data flow: `PARTIAL`** — 5 parallel `fetch()` calls on page load directly to REST endpoints (no client layer, no caching, no retry, no mock fallback). Tender id is a file-level constant.
- **Screens in one page (no navigation): `EXISTING`** — header badge + workflow buttons + Decision card + Risks card + Missing card + Provenance card + Requirements table + Evidence table. There is **no** tender list, tender creation, upload, processing-status, requirement-detail, review-center, or report route — the doc claim of "6 screens" (`README.md:29`) is really 6 `<div>`s on one page.

## 2. Existing screens/components

| Screen | Status | Notes (file:line) |
|---|---|---|
| Header + decision badge (`REVIEW/…`) | `EXISTING` but `SARAI-SPECIFIC` | `frontend/index.html:35-44` — hardcoded title/subtitle |
| Workflow buttons (Recompute / Export / Override) | `EXISTING` | `index.html:50-52,130-146` — works against `EXISTING` APIs |
| Decision detail + blockers + risks | `EXISTING` | `index.html:61-62,106-113` — assumes `top_blockers/top_risks/rules_triggered` arrays |
| Risks list | `EXISTING` | `index.html:64,115` — renders any length, but untested beyond 7 |
| Missing-evidence list | `EXISTING` | `index.html:66,117` — renders any length |
| Provenance / audit chain + export links | `EXISTING` | `index.html:69-72,127` |
| Requirements table | `EXISTING` but `SARAI-SPECIFIC` | `index.html:76,119-123` — heading hardcodes `(21)` |
| Evidence table | `EXISTING` but `SARAI-SPECIFIC` | `index.html:84,125` — heading hardcodes company name |
| Tender list / selector | `MISSING` | No `GET /api/tenders` usage in frontend at all |
| Tender creation form | `MISSING` (`PROPOSED` API) | `POST /api/tenders` does not exist in `routes.py` |
| File upload (drag-drop, progress) | `MISSING` (`PROPOSED` API) | No `POST …/files` in `routes.py`; backend reads fixed filesystem path |
| Processing-status timeline + polling | `MISSING` (`BLOCKED`) | No `ProcessingJob` model, no `/process` or `/processing/status` endpoints; backend pipeline is synchronous |
| Requirement-detail view | `MISSING` (`PROPOSED` API) | No `GET …/requirements/{reqId}` |
| Evidence-detail view | `MISSING` (`PROPOSED` API) | No `GET …/evidence/{evId}` |
| Review / conflict center page | `PARTIAL` | Data available via `requirements` + `audit`, but no dedicated UI or `GET …/review` |
| Report page (print/PDF) | `PARTIAL` | JSON export link exists; PDF export `PROPOSED`, no backend |
| Loading / empty / error states | `MISSING` | Only static `LOADING` badge text; no skeletons, no 404/empty handling, failed `fetch` throws uncaught |
| API client layer | `MISSING` | Raw `fetch` inline in 5 places, zero abstraction |
| Mock-data layer | `MISSING` | No mock file, no offline mode; UI dead without live backend |

## 3. Existing API integration

Verified against `app/api/routes.py` (205 lines, 14 routes + `/health`):

| Endpoint | Used by frontend? | Status |
|---|---|---|
| `GET /api/tenders` | NO | `EXISTING` (`routes.py:13`) — frontend never calls it |
| `GET /api/tenders/{id}` | NO | `EXISTING` (`:17`) — never called |
| `GET …/requirements` | YES | `EXISTING` (`:24`) — called, response shape consumed correctly (`status/evidence_ids/reason/provenance`) |
| `GET …/evidence` | YES | `EXISTING` (`:47`) — called |
| `GET …/risks` | YES | `EXISTING` (`:53`) — called |
| `GET …/missing-evidence` | YES | `EXISTING` (`:58`) — called |
| `GET …/decision` | YES | `EXISTING` (`:66`) — called |
| `POST …/decision/recompute` | YES | `EXISTING` (`:92`) — called |
| `POST …/decision/override` | YES | `EXISTING` (`:97`) — called via `prompt()` |
| `GET …/audit` | link only | `EXISTING` (`:142`) — only an `<a href>`, never rendered inline |
| `GET …/export` | link only | `EXISTING` (`:152`) — `window.open`, never rendered |
| `GET …/explanation` | NO | `EXISTING` (`:189`) — never called |
| `GET /api/company/{id}` | NO | `EXISTING` (`:199`) — never called |
| `GET /health` | NO | `EXISTING` (`main.py:38`) — never called |

Contract fidelity: the 5 consumed endpoints match the backend response keys actually used
(`decision/confidence/rules_triggered/hard_fail_count/mandatory_missing_evidence_count/top_blockers/top_risks/supporting_*`,
`provenance[].evidence_id/fact/source_document/page_or_section/extraction_confidence`). No invented APIs in frontend code.

## 4. Existing Mock data

- **`MISSING`** — frontend has zero mock data, zero mock client, zero offline switch.
- Usable seed (not yet wired): `evaluation/sarai_gold_dataset.json` — keys `tender/gold_requirements(21)/gold_evidences(4)/gold_risks(7)/expected_decision/adversarial_examples`.
  Tender object: `{id:"SA-2018-HV2", original_no:"SA/2018/HV2", title, client, location}` — generic-shaped, reusable as one mock tender.
- Disagreement with docs: `FRONTEND_TASKS.md:14,20` says "Mock: sarai_gold_dataset.json is ready" — in reality nothing in `frontend/` reads it; it is only consumed by `evaluation/*.py`.

## 5. Sarai-specific coupling (do-not-repeat list)

All in `frontend/index.html` (+ one backend serving string):

1. `SARAI-SPECIFIC` — `<title>TenderMind — Test #001 — Sarai 220/22kV GIS</title>` (`:5`).
2. `SARAI-SPECIFIC` — header subtitle `Sarai 220/22kV GIS Substation — SA/2018/HV2 — HYOSUNG / GIZA SYSTEMS CONSORTIUM` (`:38`).
3. `SARAI-SPECIFIC` — `const tenderId = "SA-2018-HV2"` (`:92`); entire page is single-tender, no selector, no `?tender=` param, `GET /api/tenders` never called.
4. `SARAI-SPECIFIC` — heading `Requirements (21)` (`:76`); count is literal, not `reqRes.length`.
5. `SARAI-SPECIFIC` — heading `Company Evidence (HYOSUNG / GIZA)` (`:84`); company baked into UI.
6. `SARAI-SPECIFIC` — backend serving strings `main.py:8` (`title="TenderMind Test001 - Sarai…"`) and `:36,40` (`tender: "SA/2018/HV2"`) leak into `/docs` and `/health` (frontend-adjacent, documented not changed).
7. Implicit `SARAI-SPECIFIC` assumptions — code works today only because backend returns Sarai shapes: `REQ-A..U` ids, `E-001..E-004` ids, `220kV/175MVA/South Korea/first-category` facts, 7 risks. Nothing validates generic ids; `decision.top_blockers[:6]` / `top_risks[:4]` slicing lives in backend `decision.py:116-117` and the UI prints whatever arrives (accidentally generic) but was only ever tested with Sarai lengths.

## 6. Problems found

P1 — `const tenderId` hardcoded: product cannot open tender 02/03/04 at all. (`NEEDS REFACTOR`)
P2 — No tender list: `GET /api/tenders` (`EXISTING`, cheapest integration) completely unused. (`MISSING`)
P3 — Fixed headings (`Requirements (21)`, company name) misreport any non-Sarai tender. (`SARAI-SPECIFIC`)
P4 — No `fetch` error handling: one 404/500 (e.g. unknown tender id) rejects `Promise.all` and leaves the page half-blank with a stuck `LOADING` badge. No 404, empty, or error states anywhere. (`MISSING`)
P5 — Backend `GET …/evidence` (`routes.py:47-51`) returns **all** evidences (`db.query(Evidence).all()`, ignores `tender_id`); same for `missing-evidence` (`:64`) and unscoped audits (`:145`). Single-tender today, multi-tender wrong. **Backend dependency — documented, not silently fixed.** (`BLOCKED` on backend for correct multi-tender scoping)
P6 — `app/main.py:18` startup checks `Tender.id == "SA/2018/HV2"` (slash) while `seed.py:25` creates `"SA-2018-HV2"` (hyphen) → check never matches → `seed()` re-runs **and wipes all tables** (`seed.py:16-17`) on every cold start. Multi-tender data cannot survive a restart. **Backend dependency.** (`BLOCKED`)
P7 — `seed.py` is Sarai-only (21 REQ rows, 4 evidences, 7 risks, company `HYOSUNG_GIZA`) — fine as seed, but there is no seed/endpoint path for tenders 02/03/04. (`SARAI-SPECIFIC`, backend scope)
P8 — No requirement-detail or evidence-detail endpoints (`GET …/requirements/{reqId}`, `GET …/evidence/{evId}` `PROPOSED`) and no `source_spans/bbox` in `GET …/requirements` response (schema `requirement_schema.json:21` defines `source_spans` but `routes.py:24-45` never returns it) → source viewer can only show text provenance. (`BLOCKED`/`PROPOSED`)
P9 — No upload / processing-job backend (`POST …/files`, `POST …/process`, `GET …/processing/status` all `PROPOSED`; pipeline synchronous, ~7919 s full OCR per handoff doc) → upload + processing UI can only be mock-driven. (`BLOCKED`, mock adapter required)
P10 — Override form uses blocking `prompt()` with no validation feedback; audit list never rendered inline. (`NEEDS REFACTOR`, minor)
P11 — Styling inline in `<head>`; zero component reuse; table columns assume requirement/evidence field set (no defensive rendering for unknown categories/types). (`NEEDS REFACTOR`)

## 7. Required refactoring

R1. `NEEDS REFACTOR` — `frontend/index.html`: remove all Sarai literals; tender id from selector + `?tender=` (deep-linkable); headings computed (`Requirements (N)`, `Evidence (N)`); company name from API (`GET /api/company/{id}` or evidence `company_id`), never literal.
R2. `NEEDS REFACTOR` — split inline script into `frontend/js/api-client.js` (single `fetch` wrapper, base URL, error mapping) + `frontend/js/app.js` (render) + `frontend/js/mock-data.js` (offline tenders). No framework change (keep zero-build static serving — matches `main.py` static mount; React/Vite proposal in docs rejected as over-engineering for this slice).
R3. `NEEDS REFACTOR` — renderers must be shape-driven: iterate `requirements/evidences/risks/missing` arrays; pills for any `status` (`PASS/FAIL/MISSING_EVIDENCE/MISSING/REVIEW/NOT_APPLICABLE/…`); filters built from distinct `category` values present, never a fixed category list; ids rendered opaquely (no `REQ-A..U` / `E-001` regexes in UI).
R4. `NEEDS REFACTOR` — per-panel loading skeletons + empty (`No requirements yet`) + error (`Tender not found (404)`) states; `Promise.allSettled` instead of `Promise.all` so one failing panel doesn't blank the page.
R5. `PROPOSED` (new, mock-backed) — tender-list view, upload view (mock progress + `localStorage`), processing-status view (mock `QUEUED→COMPLETED` timeline), review-queue derivation (`status REVIEW/MISSING` client-side until `GET …/review` exists), report view (`export` JSON pretty-print + print CSS).

## 8. Missing functionality

M1. `MISSING` — Tender list + tender switcher (`GET /api/tenders` `EXISTING`, just unwired).
M2. `MISSING` — Tender overview header driven by `GET /api/tenders/{id}` (`EXISTING`, unwired).
M3. `MISSING` — Explanation panel (`GET …/explanation` `EXISTING`, unwired).
M4. `MISSING` — Inline audit trail (`GET …/audit` `EXISTING`, only linked).
M5. `MISSING` — Upload UI (backend `PROPOSED` → mock adapter).
M6. `MISSING` — Processing-status UI (backend `BLOCKED` → mock adapter with polling-shaped API so real endpoint drops in).
M7. `MISSING` — Requirement-detail / evidence-detail inline expansion (backend detail endpoints `PROPOSED`; expandable rows from list payload meanwhile).
M8. `MISSING` — Search/filter/sort on requirements + status/category filters derived from data.
M9. `MISSING` — Mock-mode banner + toggle (`?mock=1`, auto-fallback when backend unreachable).
M10. `MISSING` — PDF report (`GET …/export/pdf` `PROPOSED` backend; frontend prints JSON + `window.print()` meanwhile).

## 9. Backend dependencies (documented, not changed)

| # | Need | Endpoint / change | Why | Workaround |
|---|---|---|---|---|
| B1 | Scope evidence per tender | `GET …/evidence` filter `Evidence` by tender (join `EvidenceMatch→Requirement.tender_id` or add `tender_id` col) | Multi-tender correctness (P5) | Mock data already scoped; live Sarai unaffected (single tender) |
| B2 | Scope missing-evidence + audits | `GET …/missing-evidence`, `GET …/audit` filter by `tender_id` in SQL | Same | Same |
| B3 | Fix startup reseed wipe | `main.py:18` id mismatch (`SA/2018/HV2` vs `SA-2018-HV2`) + `seed.py` table wipe | Any second tender deleted on restart (P6) | None — backend must fix before multi-tender persistence |
| B4 | Tender CRUD | `POST /api/tenders`, `GET` already exists | Creation UI real data | Mock local list |
| B5 | File upload + listing | `POST/GET /api/tenders/{id}/files` + `TenderDocument` persistence | Upload UI real data | Mock `localStorage` adapter |
| B6 | Async processing job | `POST …/process` + `GET …/processing/status` (`ProcessingJob{id,tender_id,status,progress,stage,error,…}`) | Processing UI real progress | Mock timeline adapter with identical shape |
| B7 | Detail endpoints | `GET …/requirements/{reqId}`, `GET …/evidence/{evId}`, `GET …/review` | Detail views without over-fetch | Expandable rows from list payload |
| B8 | Provenance spans | include `source_spans[{page,bbox,quote_ar,quote_en}]` in requirements response | Page viewer with bbox highlight | Text-only provenance |
| B9 | PDF export | `GET …/export/pdf` | Printable report | JSON download + print CSS |

## 10. AI dependencies

- None blocking for frontend. Decision semantics (`status.py`/`decision.py`: `MISSING≠FAIL`, `Risk→REVIEW` only, `FAIL→NO_BID`) are consumed, never reimplemented — frontend renders `decision/confidence/rules_triggered` opaquely.
- AI pipeline quality (OCR coverage, requirement F1, evidence recall, HybridMatcher wiring) affects **data**, not UI contracts; mock tenders cover sparse (0-evidence) and dense shapes so UI is proven independent of extractor recall.
- Frozen: `schemas/*` response shapes for requirement/evidence/decision; any AI-side schema change needs a coordinated frontend render check (especially `source_spans`).

## 11. Proposed implementation order (executed below)

1. ✅ This analysis (`docs/FRONTEND_ANALYSIS.md`).
2. `frontend/js/api-client.js` — generic client (`EXISTING` endpoints) + `PROPOSED`-shaped stubs + backend-unreachable auto-mock. 
3. `frontend/js/mock-data.js` — 4 tenders with deliberately different shapes (21/4/7 Sarai, 8/2/3 Mobile, 12/0/1 October, 5/6/2 Motawreen) to break 21/4 assumptions.
4. `frontend/index.html` rewrite — tender-agnostic shell: list view + detail tabs + upload (mock) + processing (mock) + filters + states. Zero Sarai literals.
5. `tests/test_frontend_generic.py` — static + contract assertions (variable counts, no hardcoded ids, states, mock mode).
6. Run `tests/test_decision_engine.py` (regression: decision semantics untouched) + new frontend tests.

## 12. Acceptance criteria

- [ ] Opening `/` with empty DB shows tender list (live or mock), never a Sarai-only page.
- [ ] Switching tenders changes every panel; counts (`Requirements (N)`) computed, never literal.
- [ ] A tender with 8 requirements / 2 evidences and one with 40/0 render correctly (mock proves 8/12/5 + live 21).
- [ ] No `SA-2018-HV2/Sarai/REQ-A..U/E-001..E-004/220kV/175MVA/South Korea/first category` literal in UI code paths (brand strings in mock data only).
- [ ] Unknown tender id → 404 error state, not blank page; empty tender → empty states; slow backend → loading skeletons.
- [ ] Mock mode (`?mock=1` or backend down) fully navigable offline.
- [ ] Decision badge renders `BID/REVIEW/NO_BID` opaquely; no `BID/REVIEW/NO_BID` rules in JS (grep-verified).
- [ ] `tests/test_decision_engine.py` still passes (backend untouched); `tests/test_frontend_generic.py` passes.
- [ ] Backend contract gaps (B1–B9) documented with endpoint/method/request/response (see §9 + `docs/FRONTEND_BACKEND_HANDOFF.md` §PROPOSED).

---

*End of analysis — implementation follows this file in the same task.*
