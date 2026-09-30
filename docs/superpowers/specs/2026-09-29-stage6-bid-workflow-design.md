# Stage 6 — Bid workflow: eligibility gate, RFP sections, team, votes, Go/No-Go score

Approved in chat 2026-09-29. Answers: capability form + documents; ineligible stops with
"continue anyway"; one shared company login + named team list; score weights 40/20/15/25.

## 0. Fixes from the accuracy review (Turaif, blind 100-row sample)
- Rule-classified rows 40/40 correct, model rows 35/40, remaining UNKNOWN 17/20 classifiable.
  -> add cues to `app/pipeline/rule_category.py` (contract clause references, personnel,
  electrical ratings); re-measure on a new blind sample; no cue -> stays UNKNOWN.
- Q&A items: 31 of 48 were internal model doubts ("binding force unclear", "model abstained")
  with no requirement text, and the email draft sent them to the tender owner.
  -> `app/issues.py`: questions only for real clarification needs (TBD/missing value); each
  shows the requirement text (quote) + file + page. Model doubts are not questions.
  Email draft uses only those.

## 1. Company capabilities (Settings)
`CompanyCapability` (one row per account): work_types (substation, overhead line, cable,
distribution, generation, solar/renewables, other), max_kv, countries, registrations
(free-text list, e.g. "SEC approved vendor", "Contractors classification grade 1"),
certifications (ISO 9001/14001/45001 ...), years_experience, annual_turnover (+currency).
Empty profile = gate skipped, with a note.

## 2. Eligibility gate (`app/eligibility.py`)
Runs inside processing after EXTRACTION, before AI (seconds, deterministic). Checks on the
extracted text, each -> PASS / FAIL / UNCLEAR with evidence (file, page, quote):
- work type: tender kind (title first) in company work_types
- voltage: tender main kV <= max_kv
- country: tender country (title/client/text) in countries (UNCLEAR if not found)
- certifications: ISO standards the tender demands vs company certifications
- registrations: prequalification/approved-vendor/classification demands -> UNCLEAR unless a
  company registration matches words
- experience years / turnover: numbers demanded in the text vs profile
Any FAIL -> job status `INELIGIBLE`, a HIGH "Tender not suitable" issue with reasons, AI
skipped. `POST /api/tenders/{id}/eligibility/override` records who/why and resumes (extraction
is cached). Result stored on the job/analysis and shown in the workspace.

## 3. RFP sections + suppliers (`app/sections.py`)
Split each document on headings (SECTION/PART/SCHEDULE/APPENDIX/ANNEX/numbered "N.N TITLE"
upper-case lines) into sections with page ranges; tag a discipline by keywords (civil,
electrical primary, protection & control, SCADA/telecom, HVAC, fire, cables, commercial,
legal, HSE). Suppliers per discipline from the account's past quotations (Rfq.discipline /
package): count of quotes, times selected, average technical fit, last tender. Endpoint
`GET /api/tenders/{id}/sections`.

## 4. Team (shared login)
Login stays one account per company. `TeamMember` (name, department, role). Settings card.

## 5. Tasks
`TenderTask` (tender, title, assignee member, department, due date, status OPEN/DONE, notes).
Similar open tasks across tenders are grouped (normalized-token Jaccard >= 0.6) and shown as
one notification: "N similar tasks in M tenders — do once". Workspace card + Notifications.

## 6. Department votes
`DepartmentVote` (tender, member, department, vote APPROVE/REJECT/ABSTAIN, comment,
unique per tender+member). Per-department and overall approve %.

## 7. Go/No-Go score (`app/scoring.py`)
0-100 = weighted mean of available factors (weights editable, default 40/20/15/25):
- fit: mandatory PASS % after evaluation; before evaluation, eligibility PASS share
- similar past tenders: `Tender.outcome` (WON/LOST/SUBMITTED/NOT_SUBMITTED); among past
  tenders of the same kind (and kV band when known): won / (won+lost)
- past partners: share of the tender's technical disciplines that have a past supplier
- department votes: approve / (approve+reject)
Missing factor -> dropped, weights renormalised, listed as "not counted". >=70 GO,
50-69 REVIEW, <50 NO_GO; any mandatory FAIL (hard gate) -> NO_GO whatever the score.
Shown in the recommendation panel with each factor's value and reason.

## 8. Remove expected value
Remove value-estimate endpoint, panel block, `app/market.py`, award refresh and the model.

## Testing
Unit tests per module; API tests for endpoints; frontend tests for new cards; full suites;
live run on Turaif in the browser (gate, sections, tasks, votes, score).
