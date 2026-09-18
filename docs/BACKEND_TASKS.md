# مهام Backend — TenderMind

> **مصدر الحقيقة هو الكود الحالي في المستودع، وليس هذا المستند وحده.**
> المستودع: `C:\Users\EgyTech\Desktop\TenderMind` — `origin https://github.com/Younes695/TenderMind.git` — `main`

## ما هو TenderMind؟

نفس تعريف Frontend: منصة تقييم مناقصات Sarai (SA/2018/HV2) 64 ملف 1394 صفحة، تدفق `Upload → Inventory → OCR (Tesseract) + DOC (LibreOffice) → Requirements (20/21) → Evidence (1/4 → 4/4 مع LibreOffice في الاختبار المعزول) → Matching (deterministic 0.604, Hybrid 0.797 معزول) → Decision (REVIEW)`.

## ما الموجود حاليًا في Backend؟

- `app/main.py:8` `FastAPI` + `app/api/routes.py:205` 13 endpoint **EXISTING** (`GET /tenders`, `/requirements`, `/evidence`, `/decision`, `/explanation`, `/export`, `/audit` etc.)
- `app/models.py` `Tender, Requirement, Evidence, EvidenceMatch, Risk, MissingEvidence, Decision, DecisionAudit` + `TenderDocument` (موجود لكن غير معروض) + `SQLite` `app/database.py` `SessionLocal` `init_db` `app/seed.py` `SA/2018/HV2`
- `app/engines/status.py` `evaluate_all()` + `decision.py` `decide()` — حتمي، يمر `6/6` اختبارات
- `evaluation/run_real_benchmark.py:187` `extract_pdf_text(ocr_needed_hint)` + `310` `extract_docx_text` مع `LibreOffice 26.8.0.3` `5598` chars (تم تثبيته `b2af0fb`)
- **لا يوجد:** `POST /tenders`, `POST /files`, `ProcessingJob` async

## ما المطلوب تنفيذه؟

توفير `Tender/File` + `ProcessingJob` + `Requirements/Evidence/Decision` APIs كاملة مع `Pydantic` + `persistence` + `async processing` + `integration tests`، مع الحفاظ على `MISSING≠FAIL` و `0$`.

## ما APIs الموجودة؟

`GET /api/tenders`, `GET /tenders/{id}`, `GET /tenders/{id}/requirements` (مع `status`), `GET /evidence`, `GET /risks`, `GET /missing-evidence`, `GET /decision`, `POST /decision/recompute`, `POST /decision/override`, `GET /audit`, `GET /export`, `GET /explanation`, `GET /company/{id}`, `GET /health` — **13 EXISTING**.

## ما APIs المطلوبة؟

`POST /tenders`, `POST /tenders/{id}/files`, `GET /tenders/{id}/files`, `POST /tenders/{id}/process`, `GET /tenders/{id}/processing/status` (5 **PROPOSED**).

## ما الذي ينتظره Frontend؟

`TenderDocument` + `ProcessingJob` + `progress` + `error` — frontend حاليًا يعمل بـ `Mock` `sarai_gold_dataset.json` حتى يتوفر `POST /files` + `POST /process`.

## ما الذي يعتمد على AI/evaluation؟

`extract_docx_text` LibreOffice + `extract_pdf_text` Tesseract routing (`ocr_needed_hint`) + `REQUIREMENT_PATTERNS` (20/21) + `extract_evidence_rule_based` (1/4 في E2E الكامل، 4/4 في الاختبار المعزول) — كلها **PROVEN** في `Temp` لكن `E2E` الكامل لا يزال `1/4` بسبب `64-file` timeout.

---

### BE-001 — Tender Model + Persistence

- **الهدف:** تثبيت نموذج المناقصة
- **المطلوب:** مراجعة `app/models.py` `Tender {id, title, client, location, original_no}` + `Base` + `init_db()`، تأكد `seed()` ينشئ `SA/2018/HV2`
- **ملفات فحص:** `app/models.py`, `app/database.py`, `app/seed.py`
- **ملفات تعديل:** لا يوجد (موجود)
- **API:** `GET /api/tenders` **EXISTING**
- **Acceptance:** `GET /api/tenders` يرجع `SA/2018/HV2`
- **Priority:** P0 **يمكن البدء الآن؟** نعم

### BE-002 — Tender File Upload — TenderDocument

- **الهدف:** رفع ملفات المناقصة
- **المطلوب:** `POST /api/tenders/{id}/files` `multipart/form-data` `files[]` → حفظ في `uploads/{tender_id}/` + إنشاء `TenderDocument {id, tender_id, filename, path, size, type, upload_timestamp}` في `SQLite`, `GET /api/tenders/{id}/files` لإرجاع القائمة
- **Existing code to reuse:** `evaluation/run_real_benchmark.py:63` `file_inventory()` `ROOT.rglob` + `app/models.py` `TenderDocument` (موجود لكن غير مستخدم عبر API)
- **ملفات تعديل:** `app/api/routes.py` (إضافة 2 endpoint), `app/models.py` (تأكيد `TenderDocument`), `app/database.py`
- **API:** `POST /files` **PROPOSED**, `GET /files` **PROPOSED**
- **Persistence:** `SQLite` `TenderDocument` table
- **Acceptance:** رفع `3` ملفات `pdf` يظهر في `GET /files` مع `size` و `filename`
- **Priority:** P0 **Blocker:** لا يوجد — يمكن البدء فورًا

### BE-003 — ProcessingJob + Async Status

- **الهدف:** حالة معالجة غير متزامنة (7919s)
- **المطلوب:** `ProcessingJob {id, tender_id, status, progress, stage, error, started_at, completed_at}` + `POST /api/tenders/{id}/process` → ينشئ `job_id` `QUEUED` ويشغل `run_document_intelligence` في `BackgroundTasks`, `GET /api/tenders/{id}/processing/status` → `{status, progress 0-100, stage, error}` polling كل 2 ثانية
- **Existing code:** `evaluation/run_real_benchmark.py:418` `run_document_intelligence()` synchronous — لفه في `BackgroundTasks`
- **ملفات تعديل:** `app/models.py` (إضافة `ProcessingJob`), `app/api/routes.py` (2 endpoints), `app/database.py`
- **Acceptance:** `POST /process` يرجع `job_id`, `GET /status` يتحرك `QUEUED 0% → PROCESSING 20% → OCR 40% → COMPLETED 100%`
- **Priority:** P0

### BE-004 — Requirements API (تفصيلي)

- **الهدف:** تفاصيل متطلب واحد
- **المطلوب:** `GET /api/tenders/{id}/requirements/{reqId}` → `Requirement` + `status` + `provenance` + `source_spans` `bbox`
- **Existing:** `GET /api/tenders/{id}/requirements` **EXISTING** `24` يرجع كل المتطلبات مع `status`
- **ملفات تعديل:** `app/api/routes.py` (إضافة endpoint)
- **Acceptance:** `GET /requirements/REQ-A` يرجع `First-category` `GIZA` `Page 2`
- **Priority:** P1

### BE-005 — Evidence API (تفصيلي)

- **الهدف:** تفاصيل دليل واحد
- **المطلوب:** `GET /api/tenders/{id}/evidence/{evId}` → `Evidence` + `provenance`
- **Existing:** `GET /api/tenders/{id}/evidence` **EXISTING** `47`
- **Acceptance:** `GET /evidence/E-001` يرجع `consortium` `Page 1`
- **Priority:** P1

### BE-006 — Decision + Explanation

- **الهدف:** الحفاظ على القرار الحتمي
- **المطلوب:** لا تغيير في `app/engines/status.py` `evaluate_all()` و `app/engines/decision.py:12` `decide()` — `MISSING≠FAIL`, `Risk→REVIEW`, `HARD_GATE_FAIL→NO_BID`
- **Existing:** `GET /api/tenders/{id}/decision` `66`, `POST /decision/recompute` `92`, `POST /decision/override` `97`, `GET /explanation` `189` — **EXISTING** ويمر `6/6`
- **Acceptance:** `GET /decision` يرجع `REVIEW` `LOW` `MANDATORY_GATE_MISSING` `hard_fail 0`
- **Priority:** P0

### BE-007 — Review / Conflict API

- **الهدف:** مركز المراجعة
- **المطلوب:** `GET /api/tenders/{id}/review` → `{review_items: Requirement[] where status REVIEW, conflicts: []}` — حالياً عبر `GET /requirements` + `GET /audit` `142`
- **Existing:** `GET /audit` **EXISTING**
- **Acceptance:** `GET /review` يرجع `17 MISSING + 1 REVIEW`
- **Priority:** P1

### BE-008 — Report / Export PDF

- **الهدف:** تصدير PDF (حالياً JSON فقط)
- **المطلوب:** `GET /api/tenders/{id}/export/pdf` → `PDF` (اختياري، يمكن تأجيله)
- **Existing:** `GET /api/tenders/{id}/export` `152` **EXISTING** JSON
- **Acceptance:** `GET /export` يرجع JSON كامل، `GET /export/pdf` **PROPOSED** يرجع `application/pdf`
- **Priority:** P2

### BE-009 — OCR Routing Fix Preservation

- **الهدف:** الحفاظ على إصلاح `ocr_needed_hint`
- **المطلوب:** لا ترجع لـ `file_inventory` بدون `hint` — `evaluation/run_real_benchmark.py:187` `extract_pdf_text(ocr_needed_hint)` + `418` `run_document_intelligence` يمرر `hint` — تم `b2af0fb` (**EXISTING** الآن)
- **ملفات فحص:** `evaluation/run_real_benchmark.py:187`, `evaluation/tesseract_local_ocr.py:31`
- **Acceptance:** `volume 1 of 2.pdf` `189` `NO` → `0 OCR` `0.62s` (مُثبت `tests/test_pdf_ocr_routing.py` `7/7`)
- **Priority:** P0

### BE-010 — DOC Extraction Preservation

- **الهدف:** الحفاظ على `LibreOffice` للـ `.DOC`
- **المطلوب:** `evaluation/run_real_benchmark.py:310` `extract_docx_text` يحاول `libreoffice_headless_txt` `5598` أولاً ثم `olefile` — تم `b2af0fb` (**EXISTING**)
- **Acceptance:** `tests/test_doc_libreoffice.py` `5/5` `DOC_EXTRACTOR=libreoffice` `5598`
- **Priority:** P0

### BE-011 — Integration Tests

- **الهدف:** اختبارات تكامل حقيقية
- **المطلوب:** `tests/test_doc_libreoffice.py` (5) + `tests/test_pdf_ocr_routing.py` (7) + `tests/test_hybrid_*` (7+4) — جميعها `python tests/*.py` **EXISTING** بعد `b2af0fb`
- **Acceptance:** `46 offline tests passed` (`6+17+7+4+5+7`)
- **Priority:** P0

### BE-012 — Frontend Mock Contract

- **الهدف:** توفير Mock للـ Frontend
- **المطلوب:** `GET /api/tenders` يرجع `sarai_gold_dataset.json` كـ mock إذا لم يوجد `DB` — حالياً `seed()` يفعل ذلك
- **Acceptance:** `GET /api/tenders` يرجع `SA/2018/HV2` حتى بدون رفع
- **Priority:** P0
