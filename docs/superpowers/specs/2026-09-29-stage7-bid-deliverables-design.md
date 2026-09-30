# Stage 7 — Bid deliverables: compliance matrix, submission checklist, conflicts, decision pack

Chosen by the user 2026-09-29 from a procurement-evaluation brief, adapted to the bidder's side
(TenderMind serves the contractor, not the tender owner). Same rules: evidence-based, every
result traceable to file + page, nothing invented, no decision taken for the team.

## 1. Compliance matrix (Excel)
`GET /api/tenders/{id}/compliance-matrix.xlsx?lang=en|ar` (openpyxl). Sheets:
- Summary: tender, date, counts by status (PASS / FAIL / REVIEW / MISSING_EVIDENCE / not evaluated),
  compliance % = PASS ÷ mandatory requirements, with the method written out; MISSING and REVIEW
  never count as PASS.
- Matrix: Req ID, requirement (tender's words), category, mandatory, source file, page,
  company evidence (file, page, quote), status, gap, comment (empty, for the team).
Arabic: RTL sheet and Arabic headers. Rows from the decision detail (all synced requirements).

## 2. Submission checklist
`app/checklist.py`: bid-time submission items from the analysis requirements whose text asks the
bidder to submit / attach / sign / fill something with the bid (not execution-time submittals),
deduplicated (Jaccard >= 0.7). Each item: text quote, file, page. Team state per item in
`SubmissionItem` (status TODO / READY / NOT_APPLICABLE, assignee, note), keyed by a stable hash.
`GET /api/tenders/{id}/checklist`, `PUT /api/tenders/{id}/checklist/{key}`.

## 3. Cross-document conflicts
`app/conflicts.py`: typed facts read from page texts with their context word — bid validity (days),
completion period (days/months → days), bid bond %, performance bond %, advance payment %,
retention %, liquidated damages cap %, warranty period (months). A conflict = the same fact with
different values in two or more documents. Each conflict lists every value with file, page,
quote, and becomes a clarification question (kind `conflict`, goes to the email draft).
Memoised on the extraction cache like sections.

## 4a. Certifications & qualifications (first section of the decision pack — user request)
`app/certifications.py`: every certificate / approval the tender demands — ISO standards,
vendor approvals and prequalification (SEC / Aramco / Ma'aden approved, prequalified), contractor
classification, type-test certificates (KEMA / CESI / IEC type test), manufacturer approvals —
each with file, page, quote, and WHO it is demanded from:
- the bidder -> compared with the company's certifications / registrations: HELD / MISSING / CHECK
- a manufacturer / supplier / subcontractor -> "needs a partner or supplier that holds it", with
  past suppliers of the related discipline suggested.
So the team sees at the start whether it needs a partner (e.g. a foreign contractor) instead of
finding out late.

## 4. Decision pack + audit trail
`AuditEvent` (tender, action, detail JSON, actor account, actor name, at). Logged on: eligibility
override, vote saved/removed, outcome set, checklist change, task done/reopened, decision override.
`GET /api/tenders/{id}/decision-pack` aggregates, in this order: certifications & qualifications (4a), eligibility, score + factors,
recommendation text, compliance counts, top gaps, conflicts, open questions, missing documents,
checklist progress, votes, tasks, audit trail. Frontend page `/tenders/:id/pack`: print-ready
(Print / Save as PDF), both languages; sections labelled FACT / CALCULATION / HUMAN REVIEW where
it applies. Statement at the end: the decision belongs to the company's authorised team.

## Plan (native execution, commit per task)
1. conflicts.py + issue kind + tests. 2. checklist.py + model + routes + tests.
3. audit events + logging hooks + tests. 4. compliance matrix xlsx + tests.
5. decision pack endpoint + tests. 6. frontend: checklist card, conflicts in Q&A (existing
IssueCard), matrix download + pack page, Arabic strings, tests. 7. full suites, live check, review.
