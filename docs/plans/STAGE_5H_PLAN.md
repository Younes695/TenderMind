# Stage 5H — Review alerts, Q&A, News, and runs that survive failures

## Goals (from the user, 2026-09-28)
1. Missing files / missing items in a tender create **review items** and show as
   **notifications** so nobody misses them.
2. **Q&A** section: everything unclear — ambiguous clauses, unreadable/low-quality
   scanned pages, requirements the AI could not classify — as questions with
   status and an answer field.
3. **News** section: tenders fetched from official / trusted sources.
4. The system keeps running: no crash that forces a restart and a re-run from zero.

## Design
### Tender issues (one table, two views)
`tender_issues(id, tender_id, category missing|question, kind, title, detail,
source_document, page, priority, status OPEN|RESOLVED, answer, resolved_by,
created_at, resolved_at, dedupe_key)` — unique (tender_id, dedupe_key), so rebuilds
never duplicate and never reopen what a person resolved.

Built by `app/issues.py::sync_issues(db, tender_id)` (idempotent):
- **missing** (review required → notification): package gaps from the analysis
  (missing-file, unsupported-type, failed-extraction, empty-ocr,
  referenced-form-absent), and mandatory requirements with no company evidence
  once the tender has been evaluated.
- **question** (Q&A): grouped ambiguities, unreadable scanned pages (OCR
  confidence < 0.55 or almost no text — recorded per page during extraction as
  `derived_features.page_quality`), requirements left UNKNOWN by the AI.
Runs at the end of processing (best effort — never fails a job) and lazily on read.

API: `GET /api/tenders/{id}/issues?category=`, `PATCH /api/issues/{id}`,
`GET /api/notifications` (open "missing" items across the account's tenders).

### News
`news_items(source, external_id unique per source, title, description,
country, notice_type, published_at, deadline_at, url, organization, relevant)`.
Sources: World Bank procurement notices API (official; Egypt + MENA country
codes) and optional RSS feeds on an explicit allow-list
(`TENDERMIND_NEWS_FEEDS`). Etimad and EBRD refuse automated access (robots.txt
denied / 403) — not scraped. No personal contact data stored.
Refresh: background every 6 h + `POST /api/news/refresh` (min 15 min apart).

### Runs that survive failures
- Extraction checkpoint per file (hash-keyed JSON under the tender's `.cache/`):
  a retried or resumed job skips files already extracted (the 1,530-page file
  is not OCR'd again).
- AI result checkpoint (JSONL per tender + model + prompt): resumed jobs only
  call the model for candidates not answered yet.
- On startup, interrupted jobs are **resumed automatically** (new job, same
  tender) instead of "FAILED — start again".
- Watchdog: a job marked PROCESSING whose worker thread is gone is resumed.
- SQLite WAL + busy timeout (done in 5G), best-effort progress writes (done).

## Delivery rule
The Turaif run in progress must not be interrupted: backend changes are built and
tested beside it and activated after it finishes.
