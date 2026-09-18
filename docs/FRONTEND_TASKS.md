# مهام Frontend — TenderMind

> **مصدر الحقيقة هو الكود الحالي في المستودع، وليس هذا المستند وحده.**
> المستودع القانوني: `C:\Users\EgyTech\Desktop\TenderMind` — `origin https://github.com/Younes695/TenderMind.git` — `main`

## ما هو TenderMind؟

TenderMind منصة لتقييم مناقصات **Sarai 220/22kV GIS Substation (SA/2018/HV2)** لصالح **MNHD**. التدفق: `رفع المناقصة → جرد الملفات → استخراج المستندات/OCR (Tesseract 5.4.0 ara+eng + LibreOffice 26.8.0.3 للـ .DOC) → استخراج المتطلبات (21 متطلب A-U) → استخراج الأدلة (4 أدلة) → مطابقة HybridMatcher → قرار حتمي BID/REVIEW/NO_BID → شرح + provenance → تقرير`.

**الـ Frontend غير منفذ حاليًا في الـ repository** — لا يوجد `frontend/src` بعد، يوجد فقط `frontend/index.html` — لذلك المهام التالية هي **Implementation Tasks** وليست تعديلات.

## ما المطلوب من مهندس Frontend؟

بناء واجهة كاملة تستهلك `app/api/routes.py` (13 endpoint **EXISTING**) وتعمل بـ **Mock** حيث الـ Backend لسه `PROPOSED` (رفع، حالة المعالجة). كل شاشة يجب أن تعمل بالـ Mock عبر `evaluation/sarai_gold_dataset.json` (21 req, 4 ev, 7 risks) بدون انتظار AI مثالي.

## ما الموجود حاليًا؟

- **Backend EXISTS:** `GET /api/tenders`, `/tenders/{id}/requirements`, `/evidence`, `/decision`, `/explanation`, `/export`, `/audit` — كلها ترجع `SA/2018/HV2` مع `decision REVIEW`
- **Frontend:** لا يوجد — تبدأ من الصفر
- **Mock:** `sarai_gold_dataset.json` هو مصدر Mock جاهز

## ما الذي يمكنك البدء به فورًا؟

كل المهام أدناه **يمكن البدء بها الآن** باستخدام Mock — لا تنتظر OCR مثالي أو `0.93` أو `ProcessingJob`.

---

### FE-001 — App Shell + Navigation

- **الهدف:** هيكل التطبيق والتنقل
- **User Story:** كمستخدم أريد التنقل بين المناقصات والمتطلبات والقرار
- **المطلوب:** React/Vite + Tailwind, `Header` (TenderMind), `Sidebar` (Tender List, Overview, Requirements, Evidence, Review, Decision, Report), `Router`
- **الشاشة:** `App.tsx`, `Layout.tsx`
- **البيانات:** لا يوجد
- **API:** لا يوجد
- **Mock:** لا
- **ملفات قراءة:** `app/main.py:8`, `frontend/index.html`
- **ملفات تعديل:** `frontend/src/*` (جديد)
- **هل يمكن البدء الآن؟** نعم
- **Acceptance:** Shell يعمل، navigation بين 7 صفحات، لا أخطاء console
- **Priority:** P0 **Definition of Done:** Shell + navigation + 404 page

### FE-002 — Tender List

- **الهدف:** عرض المناقصات
- **User Story:** كمستخدم أريد رؤية كل المناقصات وحالتها
- **المطلوب:** جدول/كروت: `id`, `title`, `client`, `location`, `decision` badge, `last updated`
- **البيانات:** `Tender {id, title, client, location}`
- **API:** `GET /api/tenders` **EXISTING** `app/api/routes.py:13`
- **Mock:** `sarai_gold_dataset.json` tender `SA-2018-HV2`
- **ملفات قراءة:** `app/models.py`, `app/api/routes.py:13`
- **Acceptance:** 1 صف على الأقل، badge `REVIEW` يظهر، click يذهب لـ Overview
- **Priority:** P0

### FE-003 — Tender Creation (PROPOSED)

- **الهدف:** إنشاء مناقصة جديدة
- **User Story:** كمدير أريد إنشاء مناقصة
- **المطلوب:** فورم `title, client, location`, زر `Create`
- **API:** `POST /api/tenders` **PROPOSED** (غير موجود — اعمل Mock يضيف للـ list المحلي)
- **هل يمكن البدء الآن؟** نعم (Mock)
- **Blocker:** Backend `POST /tenders` **PROPOSED** — تجاوزه بـ Mock
- **Acceptance:** فورم ينشئ tender وهمي ويظهر في القائمة
- **Priority:** P1

### FE-004 — File Upload

- **الهدف:** رفع ملفات المناقصة (PDF/DOC/XLS)
- **User Story:** كمستخدم أريد رفع 64 ملف Sarai
- **المطلوب:** منطقة drag-and-drop، `accept .pdf,.doc,.docx,.xls,.xlsx`, عرض `filename, size, type`, validation, progress bar
- **API:** `POST /api/tenders/{id}/files` **PROPOSED** (حالياً `ROOT` ثابت `C:\Users\EgyTech\Desktop\01- Sarai...` في `evaluation/run_real_benchmark.py:18`)
- **Mock:** `localStorage` + `sarai_gold_dataset.json`
- **Acceptance:** رفع 3 ملفات تجريبية يعرضها في القائمة، progress يصل 100%
- **Priority:** P0

### FE-005 — Processing Screen

- **الهدف:** عرض حالة المعالجة الطويلة (7919s)
- **User Story:** كمستخدم أريد متابعة `OCR → Requirements → Evidence → Matching → Decision`
- **المطلوب:** Timeline `QUEUED → PROCESSING → EXTRACTING → OCR → REQUIREMENTS → EVIDENCE → MATCHING → DECISION → COMPLETED`, progress `0-100`, polling كل 2 ثانية, `error` banner
- **API:** `POST /api/tenders/{id}/process` + `GET /api/tenders/{id}/processing/status` **PROPOSED** (حالياً `run_document_intelligence()` synchronous يعلق)
- **Mock:** `setTimeout` يحاكي `QUEUED 0% → 100%` في 5 ثوان
- **Acceptance:** شاشة تتحرك من `QUEUED` إلى `COMPLETED` وهمياً, polling يعمل
- **Priority:** P0

### FE-006 — Tender Overview/Dashboard

- **الهدف:** نظرة عامة
- **User Story:** أريد رؤية `top_blockers` و `top_risks`
- **المطلوب:** هيدر `SA/2018/HV2` + `hard_fail 0` + `mandatory_missing 1` + `top_blockers` 6 + `top_risks` 4 chips
- **API:** `GET /api/tenders/{id}` + `GET /api/tenders/{id}/decision` **EXISTING** `66`
- **Acceptance:** `REVIEW` badge + `top_blockers` تظهر
- **Priority:** P0

### FE-007 — Requirements Dashboard

- **الهدف:** جدول المتطلبات 21
- **User Story:** أريد تصفية المتطلبات حسب `category` و `status`
- **المطلوب:** جدول `REQ-A..U`, `category` (`LEGAL, TECHNICAL...`), `mandatory`, `status` (`PASS/FAIL/MISSING/REVIEW` pills), `applicable_entity` (`GIZA/CONSORTIUM`), بحث, ترتيب
- **API:** `GET /api/tenders/{id}/requirements` **EXISTING** `24` (يرجع `status` من `evaluate_all()`)
- **Acceptance:** 21 صف، 3 `PASS` (B,J,R) + 1 `REVIEW` (U) + 17 `MISSING`, فلتر `LEGAL` يعرض `REQ-A,R`
- **Priority:** P0

### FE-008 — Requirement Details

- **الهدف:** تفاصيل متطلب واحد
- **User Story:** أريد رؤية `source_document` و `page_or_section` و `evidence_ids`
- **المطلوب:** صفحة `REQ-A` تعرض `First-category membership` + `source_document Sarai RFP.pdf Page 2` + `applicable_entity GIZA` + `evidence_ids []` + `reason`
- **API:** `GET /api/tenders/{id}/requirements` (نفسه) أو `GET /api/tenders/{id}/requirements/{reqId}` **PROPOSED**
- **Mock:** `sarai_gold_dataset.json` `gold_requirements` + `source_spans` `bbox`
- **Acceptance:** `REQ-A` يعرض `Page 2` و `GIZA`
- **Priority:** P1

### FE-009 — Evidence Panel

- **الهدف:** عرض الأدلة 4
- **User Story:** أريد رؤية `fact` و `source_document`
- **المطلوب:** كروت `E-001 R PASS CONSORTIUM`, `E-002 B PASS HYOSUNG`, `E-003 J PASS HYOSUNG`, `E-004 U REVIEW` مع `fact`, `source_document`, `page_or_section`, `extraction_confidence`
- **API:** `GET /api/tenders/{id}/evidence` **EXISTING** `47`
- **Acceptance:** 4 كروت تظهر
- **Priority:** P0

### FE-010 — Evidence Traceability

- **الهدف:** ربط متطلب بدليل
- **User Story:** أريد معرفة `REQ-R` مدعوم بـ `E-001`
- **المطلوب:** في `REQ-R` اعرض `supporting_evidence E-001` link إلى `Evidence` panel
- **API:** `GET /api/tenders/{id}/requirements` `supporting_evidence` + `GET /api/tenders/{id}/evidence`
- **Acceptance:** `REQ-R` يعرض `E-001` قابل للنقر
- **Priority:** P1

### FE-011 — Source Document/Page Viewer

- **الهدف:** عرض المصدر مع provenance
- **User Story:** أريد فتح `Sarai RFP.pdf Page 2` ورؤية `bbox`
- **المطلوب:** `PDF` viewer (mock) يعرض `source_document` + `page_or_section` + `bbox` highlight, `quote_ar`
- **API:** `GET /api/tenders/{id}/requirements` `provenance[]` `source_spans[]`
- **Mock:** صورة وهمية + `bbox` مستطيل
- **Acceptance:** `REQ-A` يعرض `Sarai RFP.pdf Page 2` مع highlight
- **Priority:** P1

### FE-012 — Review / Conflict Center

- **الهدف:** مركز المراجعة
- **User Story:** أريد مراجعة `17 MISSING` و `1 REVIEW` و `conflicts`
- **المطلوب:** جدول `REVIEW` queue, `conflicts` banner (`First vs Second`), `Human override` زر
- **API:** `GET /api/tenders/{id}/requirements` `REVIEW` + `GET /api/tenders/{id}/audit` **EXISTING** `142`
- **Acceptance:** `17 MISSING` + `1 REVIEW` تظهر, `conflicts` فارغ (Gold)
- **Priority:** P0

### FE-013 — Review Actions

- **الهدف:** تنفيذ override
- **User Story:** كمراجع أريد تغيير `REVIEW → BID`
- **المطلوب:** فورم `reviewer, new_decision, reason, comments` → `POST /api/tenders/{id}/decision/override` `97`
- **API:** `POST /api/tenders/{id}/decision/override` **EXISTING**
- **Acceptance:** `REVIEW → BID` ينشئ `DecisionAudit` ويظهر في `GET /audit`
- **Priority:** P1

### FE-014 — Decision Dashboard

- **الهدف:** لوحة القرار النهائي
- **User Story:** أريد رؤية `BID/REVIEW/NO_BID` و `confidence` و `rules_triggered`
- **المطلوب:** badge كبير `REVIEW — DO NOT BID YET` `LOW` `MANDATORY_GATE_MISSING`, `hard_fail 0`, `mandatory_missing 1`, `top_blockers` 6, `top_risks` 4, `rules_triggered`
- **API:** `GET /api/tenders/{id}/decision` **EXISTING** `66` + `GET /api/tenders/{id}/explanation` `189`
- **Acceptance:** `REVIEW` badge + `top_blockers` تظهر
- **Priority:** P0

### FE-015 — Report / Export

- **الهدف:** تصدير التقرير
- **User Story:** أريد تصدير JSON للتدقيق
- **المطلوب:** زر `Export JSON` → `GET /api/tenders/{id}/export` `152`, زر `Print`, عرض `provenance_chain`
- **API:** `GET /api/tenders/{id}/export` **EXISTING**, `GET /export/pdf` **PROPOSED**
- **Acceptance:** `Export` يحمل ملف JSON كامل
- **Priority:** P1

### FE-016 — API Client Layer

- **الهدف:** طبقة API معزولة
- **User Story:** كمطور أريد `fetch` wrapper واحد
- **المطلوب:** `frontend/src/api/client.ts` `getTenders()`, `getRequirements(id)`, `getDecision(id)` etc., `baseUrl /api`, error handling
- **Acceptance:** كل `GET` يستخدم `client`, لا `fetch` مباشر في components
- **Priority:** P0

### FE-017 — Mock Data Layer

- **الهدف:** العمل بدون انتظار Backend
- **User Story:** أريد تشغيل الواجهة بدون Backend
- **المطلوب:** `frontend/src/mocks/sarai_gold_dataset.json` (21 req, 4 ev, 7 risks), `mockClient` يحاكي `GET /tenders/{id}/requirements` etc., `isMock = !backendReachable`
- **Acceptance:** `npm run dev` يعرض `21` متطلب وهمي بدون تشغيل `uvicorn`
- **Priority:** P0

### FE-018 — Loading / Empty / Error States

- **الهدف:** حالات واجهة كاملة
- **User Story:** كمستخدم أريد رؤية `Loading` و `Empty` و `Error`
- **المطلوب:** `Skeleton` للجداول, `Empty` `No tenders`, `Error` `404 Tender not found`, `ocr_failed` banner
- **Acceptance:** كل صفحة لها 3 حالات
- **Priority:** P1
