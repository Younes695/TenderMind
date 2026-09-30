# Stage 8 — Tender intelligence: quick summary, similar tenders & client history, deadlines/stages/notes, manager dashboard, assistant

Chosen by the user 2026-09-29 from a product brief (contractor side). Same rules: evidence first,
sources shown, nothing invented; the assistant answers from the company's own data.

## 1. Quick summary (`app/summary.py`, `GET /api/tenders/{id}/summary`)
One card at the top of the tender page: client (entered, or detected from the text with its page),
type of work, voltage, country, documents/pages, requirement counts (mandatory), key dates, eligibility
status, certificates needing a partner, contradictions, top risks, and "What you need to do" — action
lines derived from the state (fill capabilities, upload company documents and evaluate, answer N
questions, find a partner for X, prepare N submission items, resolve N contradictions, set the
submission deadline). Every line that comes from the tender shows file + page.

## 2. Similar tenders & client history (`app/similarity.py`)
For a tender: the account's other analysed tenders ranked by a similarity score
(0.40 requirement-text cosine over TF-IDF of requirement summaries, 0.25 same client, 0.20 same type
of work, 0.10 voltage within ±40%, 0.05 same country) with the reasons, each one's latest
recommendation and outcome. `GET /api/tenders/{id}/similar`. Same client seen before -> an info
notification "You previously took part in a tender with this client" (+ the tenders). The score's
history factor uses won/lost with the same client first, then the same type of work.

## 3. Deadlines, stages, notes
- `Tender.stage` (ELIGIBILITY / STUDY / PRICING / SUBMISSION / SUBMITTED / CLOSED) and
  `Tender.submission_deadline` (set by the team; suggested from the analysis when found). Changes audited.
- Reminders computed live (`GET /api/reminders`): submission deadline in ≤7 days or passed, tasks due in
  ≤3 days or overdue, open checklist items when the deadline is ≤7 days away.
- `TenderNote` (author name, text, time): add / delete, audited.

## 4. Manager dashboard (`GET /api/dashboard/attention`)
"Needs attention now": overdue tasks, deadlines this week, tenders awaiting a decision (analysed, no
outcome) with their score band, blocked by eligibility, contradictions/partner needs, client-history
hits; plus stage counts. Existing dashboard keeps its tender table below.

## 5. Assistant (`app/assistant.py`, `POST /api/assistant/ask {question, tender_id?, lang}`)
Intent routing (EN + AR phrasing) to answers built from data, each with sources/links: overdue tasks,
deadlines, suitability (eligibility + score + blockers), why the recommendation, similar tenders,
client history, certificates / partner needs, checklist status, contradictions. Other questions:
search the tender's requirements (keyword ranking) and return the best matching quotes with pages;
when the local model is available it phrases a short answer from those quotes only. Chat panel on
every dashboard page (floating button), tender-aware on a tender page.

## Plan (native, commit per task)
1 summary. 2 similarity + client history + score history tweak. 3 stage/deadline/notes/reminders.
4 dashboard attention. 5 assistant. 6 frontend + Arabic + tests. 7 suites, live check, review.
