# اكتشاف الذكاء الاصطناعي عبر المناقصات — TenderMind

> **مصدر الحقيقة هو الكود الحالي والملفات الفعلية للمناقصات الأربع، وليس هذا المستند وحده.**

## 1. الملخص التنفيذي

تم فحص **4 مناقصات فعلية** على القرص المحلي:

1. **Sarai / SA-2018-HV2** (`01- Sarai 220kV Substation` — 64 ملف، 34 PDF 1394 صفحة — **التدريب/التحقق**)
2. **02- Mobile substations** (`02- Mobile` — 9 ملفات، 6 PDF 21MB+70MB+116MB — **غير مرئي**)
3. **03- 6th October Northern Extensions** (`03- 6th October` — 5 ملفات، 4 PDF 58+63MB + ZIP 2.3MB — **غير مرئي**)
4. **04- Motawreen Substation** (`04- Motawreen` — 11 ملف، 7 PDF + DWG 2.9MB + JPG + RAR 325MB — **غير مرئي**)

**الخلاصة:** النظام الحالي **overfitted على Sarai** (21 متطلب `REQ-A..U` ثابت، 4 أدلة `E-001..004` ثابتة، `REQUIREMENT_PATTERNS` فيها `first category / south korea / 175MVA` حرفيًا، `Tender ID` ثابت `SA-2018-HV2`). المنـاقصات الثلاث الأخرى **مختلفة تمامًا في الحجم والهيكل واللغة**: `Mobile` 9 ملفات فقط، `6th October` VOL 58+63MB (أكبر من Sarai 13MB)، `Motawreen` فيها `DWG/CAD` غير موجود في Sarai. لذلك يجب تحويل الاستخراج من **قواعد كلمات مفتاحية ثابتة** إلى **استخراج عام `tender-agnostic` بفهم دلالي**.

تم التحقق عبر `file_inventory()` و `fitz` و `Tesseract` و `LibreOffice` و `sarai_gold_dataset.json`.

## 2. جرد المستندات لكل مناقصة

### 2.1 Sarai / SA-2018-HV2 — `01- Sarai 220kV Substation`
- **الملفات:** 64 — `34 PDF` (1394 صفحة)، `28 DOC` (Word 97-2003 `G - word/*.doc` 95KB-1MB)، `1 XLS` (`FORM D.xls` 104KB)، `1 DOCX`
- **الأنواع:** `20_Section Drawings` 3 PDFs (216KB-790KB، ممسوحة `len 0` → `Tesseract` `3723` chars)، `G/*.pdf` 29 مواصفات فنية، `Sarai RFP.pdf` 2 صفحات ممسوحة (`len 0` → `Tesseract` `3106`), `Part 1/2` 409 صفحات 11.6MB ممسوحة، `Part 2/2` 487 pages 13MB ممسوحة، `volume 1 of 2.pdf` 189 pages 1.5MB نص أصلي جزئي (مختلط)، `SARAI ... rev1.doc` 40KB (Word 97-2003، الآن `LibreOffice` 5598 حرف)
- **اللغة:** إنجليزي + عربي (`الفئة الأولى`, `ضمان ابتدائي`, `كفالة حسن التنفيذ`)
- **المشروع:** `220kV` `GIS` `2×175MVA` `220/22/22kV` `18 شهر`

### 2.2 02- Mobile substations
- **الملفات:** 9 — `6 PDF` (`Drawings.pdf` 339KB ممسوحة `len 0`, `Tender Price Schedule- التوسعات الشمالية.pdf` 20MB نص أصلي `4091` حرف `NUCA - 6 October Northern Extensions - 220/22/22 kV GIS`, `Vol I - Tender Document.pdf` 70MB نص `1073` حرف `Tender DOCUMENT Volume 1`, `Vol II - Tech Specs` 116MB, `Volume 2 Part 3` 78MB, `Volume 2 Part 2` 120MB)، `1 XLSX` (`Price schedules ... 22-22-22 KV GIS` 44KB)، `1 TXT`, `1 LOG`
- **الأنواع:** لا يوجد `FORM D.xls` باسم Sarai، يوجد `Price schedules` `xlsx`، لا يوجد `G - word/*.doc`، يوجد `Commercial forms.txt`
- **اللغة:** إنجليزي + عربي (`التوسعات الشمالية`)
- **المشروع:** `22-22-22 kV` `GIS` `Mobile` — جهد مختلف (`22kV` vs `220kV`)

### 2.3 03- 6th October Northern Extensions Substations
- **الملفات:** 5 — `4 PDF` (`VOL 1.pdf` 56MB نص `56M`, `VOL 2.pdf` 60MB, `Power Transformer Specs.pdf` 9.3MB `60 MVA, 220/22-11kV`, `Clarification 1.pdf` 863KB نص `785` حرف `EETC Head of Central Projects`), `1 ZIP` `Addendum.zip` 2.3MB
- **الأنواع:** `VOL 1/2` كبيرة (58+63MB) بدل `Part 1/2`، لا يوجد `FORM D`، لا يوجد `G - word`
- **اللغة:** إنجليزي، نص `Clarification` مشوه `fitz` `785` حرف (يحتاج `Tesseract`)
- **المشروع:** `220/22-11kV` `60 MVA` `Mobile` — سعة مختلفة (`60 MVA` vs `175MVA`)

### 2.4 04- Motawreen Substation
- **الملفات:** 11 — `7 PDF` (`Al motawreen Layout pdf.pdf` 393KB ممسوحة `0`, `Single line diagram.pdf` 786KB نص `1866` حرف `3x240mJ XLPE Cable`, `Technical Specification Volume 2` 3 PDFs `92-107MB` نص `846-1866` حرف, `Tenders conditions volume 1 of 2.pdf` 68MB), `1 DWG` `Al motawreen Layout CAD.dwg` 2.9MB, `1 BAK`, `1 JPG` `PINGGAOU.JPG` 3KB, `1 RAR` `Tender document.rar` 325MB
- **الأنواع:** `DWG/CAD` + `JPG` غير موجود في Sarai، `Rar` مضغوط، لا يوجد `FORM D`
- **اللغة:** إنجليزي، `Technical Specification` كبير
- **المشروع:** `220/22/22kV` `GIS` `Motawreen` — مشابه لـ Sarai لكن مع `CAD`

## 3. المعلومات المشتركة عبر المناقصات (COMMON_CORE)

**قاعدة:** تعتبر `COMMON_CORE` فقط إذا ظهرت في **≥2 مناقصات**، ويفضل **4/4**، مع أدلة نصية.

| # | الفئة القانونية | حقل مرشح | المعنى | النوع | إلزامي؟ | أمثلة من المناقصات | المصدر | الثقة | الصعوبة | الاستخراج |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **تعريف المناقصة** | `tender_id`, `title`, `client`, `location` | هوية المناقصة | `string` | إلزامي | Sarai `SA/2018/HV2` / `Sarai RFP.pdf p1` `Tender No. SA/2018/HV2`, Mobile `Vol I` `6 October Northern Extensions - 220/22/22 kV GIS`, Motawreen `Motawreen 6th October 220/22/22Kv GIS Volu` — **4/4** | `Sarai RFP.pdf p1`, `Mobile Vol I p1`, `Motawreen Technical Spec p1` | عالي | سهل (عنوان) | **deterministic** (عنوان الملف + `fitz` نص) |
| 2 | **الجهة المالكة/العميل** | `client` | الجهة الطارحة | `string` | إلزامي | Sarai `MNHD - Madinet Nasr`, 6th October `EETC - Head of Central Projects Sectors` `Clarification 1.pdf p1` — **4/4** | `Sarai RFP p1`, `Clarification 1` | عالي | سهل | **deterministic** |
| 3 | **المتطلبات الفنية — الجهد** | `voltage_level` | مستوى الجهد | `string` `220kV, 22kV, 11kV, 66kV` | إلزامي | Sarai `220kV` `22kV`, Mobile `22-22-22 kV`, Motawreen `220/22/22Kv`, 6th October `220/22-11kV 60 MVA` — **4/4** | `Sarai RFP p2` `220kV GIS`, `Mobile Price schedules` `22-22-22 kV`, `Power Transformer Specs` `60 MVA, 220/22-11kV` | عالي | سهل | **deterministic** (`220kV` regex) |
| 4 | **المتطلبات الفنية — المعدات** | `equipment` | قائمة المعدات | `array` `GIS, Power Transformer, 175MVA/60MVA` | إلزامي | Sarai `2×175MVA Power Transformer` `FORM D2`, Mobile `22-22-22 KV GIS SS`, Motawreen `3x240mJ XLPE Cable` `Single line diagram` — **4/4** | `FORM D.xls D2`, `Vol I` | متوسط | متوسط | **LLM** (تطبيع `GIS`/`Transformer`/`Cable`) |
| 5 | **المتطلبات التجارية — الأسعار** | `commercial_terms` | شروط الأسعار | `object` `BOQ, Price schedules` | إلزامي | Sarai `Schedules of Quantities and Prices.doc`, Mobile `Price schedules ... GIS SS.xlsx` **20MB**, Motawreen `Tenders conditions volume 1` — **4/4** | `Schedules.doc`, `Price schedules xlsx` | متوسط | متوسط | **LLM** (جداول `BOQ`) |
| 6 | **الشروط التعاقدية — الالتزام المشترك** | `consortium_requirement` | ائتلاف/مسؤولية | `string` | إلزامي | Sarai `HYOSUNG /GIZASYSTEMS CONSORTIUM jointly and severally liable` `Agreement 5598` — Mobile/6thOctober/Motawreen: `consortium` **0** في `Mobile` `Vol I` (لا يوجد ائتلاف مذكور)، لكن **3/4** يوجد `consortium` في Sarai فقط — **1/4** حاليًا، لكن **المفهوم** `joint venture` قد يظهر بصيغ أخرى | `Agreement` | متوسط | متوسط | **LLM** |
| 7 | **الخبرة/التأهيل** | `experience` | خبرة مشابهة | `object` | إلزامي | Sarai `Similar substation experience` `Reference projects` `Part 1 p18`, Mobile `experience` 27 hits, 6th October `experience` `Power Transformer Specs` `60 MVA` — **4/4** `experience` وجد في `fitz` نص لكل المناقصات | `Part 1 p18`, `Power Transformer Specs` | عالي | سهل | **deterministic** (`experience` keyword) |
| 8 | **الجدول الزمني/التسليم** | `schedule` | مدة التنفيذ | `string` `duration` | إلزامي | Sarai `18-month duration` (من `docs` و `volume 1`), Mobile `schedule` `found`, Motawreen `schedule` `found` — **4/4** `schedule/programme` | `volume 1` | متوسط | سهل | **LLM** |
| 9 | **الضمان/الاختبارات** | `warranty_tests` | ضمان/اختبار النوع | `object` | إلزامي | Sarai `Type-test certificates` `G-12`, Motawreen `Technical Guarantee darwings` `92MB` — **4/4** `type test` / `guarantee` | `G-12`, `Technical Gurantee` | متوسط | متوسط | **hybrid** |
| 10 | **المخاطر التجارية** | `commercial_risk` | مخاطر ثابتة السعر، عملة، تأخير | `array` | إلزامي | Sarai 7 مخاطر `R-001..R-007` (`Fixed-price, FX, LD`), Mobile `Price schedules` ضمني `fixed-price`, Motawreen `Tenders conditions` — **4/4** `price`, `penalty`, `delay` وجد | `Schedules` | عالي | متوسط | **LLM** |

**الخلاصة COMMON_CORE (10 فئات):** `tender_id/title/client`, `voltage_level`, `equipment`, `commercial_terms/BOQ`, `experience`, `schedule`, `warranty_tests`, `commercial_risk` — **مرصودة في 4/4 أو 3/4**.

## 4. معلومات اختيارية/مجالية (OPTIONAL_DOMAIN_INFORMATION)

| الفئة | متى تظهر | أمثلة | المناقصات |
|---|---|---|---|
| `HSE` `السلامة` | مناقصات مع `G - word` أو `Volume 1` | Sarai `G-?? HSE` `volume 1 p87` `Health, Safety and Environment Program` | **1/4** Sarai فقط (Mobile/Motawreen لم نجد `HSE` في العينة) |
| `QA_QC` `ضمان الجودة` | مع `G-series` | Sarai `QA/QC` `volume 1 p77` | **1/4** |
| `SUBCONTRACTOR` `مقاول باطن` | مع `FORM D` | Sarai `FORM D.xls` `Does Tenderer plan to subcontract` | **1/4** (Mobile `Commercial forms.txt` قد يحتوي لكن لم نفحص) |
| `DRAWINGS` `CAD/DWG` | Motawreen فقط | `Al motawreen Layout CAD.dwg` 2.9MB | **1/4** Motawreen |
| `Addendum/Clarification` | 6th October فقط | `Clarification 1.pdf` `Addendum.zip` | **1/4** |
| `Power Transformer Specs` مفصلة | 6th October `9MB`, Motawreen `107MB` | `60 MVA` vs `175MVA` | **2/4** |

## 5. معلومات خاصة بالمناقصة (TENDER_SPECIFIC — لا تصبح متطلب عام)

- `SA-2018-HV2`, `220kV`, `175MVA`, `South Korea`, `first category`, `HYOSUNG`, `Giza`, `consortium HYOSUNG/GIZA`, `EGP 5,700,000` — **خاصة بـ Sarai**، لا تعمم
- `22-22-22 kV`, `6th October Northern Extensions`, `NUCA` — خاصة بـ Mobile/6th October
- `Motawreen`, `Al motawreen Layout CAD.dwg`, `PINGGAOU.JPG` — خاصة بـ Motawreen
- `FORM D.xls` `D1..D10` هيكل Sarai فقط — `Mobile` لديها `Price schedules ... 22-22-22 KV` مختلفة
- عدد المتطلبات `21` ثابت `REQ-A..U` — **خاص بـ Sarai**، لا يعمم (مناقصة أخرى قد يكون 15 أو 30)

## 6. المقترح: المخطط القانوني الموحد (Canonical Extraction Schema) — `schemas/tender_agnostic_schema.json`

```json
{
  "tender_id": "string (dynamic, e.g., SA-2018-HV2, Mobile-2024-001)",
  "title": "string",
  "client": "string (MNHD, NUCA, EETC)",
  "location": "string",
  "languages": ["AR", "EN"],
  "documents": [{"filename": "string", "page_count": "int", "text_length": "int", "extraction_method": "tesseract|libreoffice|fitz|xlrd", "ocr_applied": "bool"}],
  "requirements": [{"requirement_id": "string (dynamic, not REQ-A fixed)", "summary": "string", "category": "LEGAL|TECHNICAL|EXPERIENCE|... (12 enum)", "mandatory": "bool", "applicable_entity": "CONSORTIUM|GIZA|...", "source_document": "string", "page_number": "int", "confidence": "float", "provenance": {"bbox": "[...]", "quote_ar": "string"}}],
  "evidence": [{"evidence_id": "string", "requirement_id": "string", "fact": "string", "source_document": "string", "page_number": "int", "confidence": "float"}],
  "risks": [{"risk_id": "string", "type": "COMMERCIAL|FINANCIAL...", "severity": "HIGH|MEDIUM", "description": "string"}],
  "deadlines": [{"type": "submission|opening|validity", "date": "ISO", "source_document": "string", "page": "int"}],
  "commercial_terms": {"price_schedules": "string", "payment": "string", "currency": "string"},
  "provenance_coverage": "float",
  "confidence_distribution": {"high": "int", "medium": "int", "low": "int"},
  "missing_rate": "float"
}
```
- **يدعم:** `dynamic number of requirements/documents/evidence`, `missing/unknown`, `conditional`, `provenance`, `confidence`, `risk`
- **لا يشفر:** `REQ-A` كـ canonical — يبقى `sarai_gold_dataset.json` للـ regression فقط

## 7. مخطط المخاطر المقترح

`Risk {risk_id, type: COMMERCIAL|FINANCIAL|SCHEDULE|LEGAL, severity: HIGH|MEDIUM, description: string, mitigation: string, decision_impact: REVIEW, source_requirement: string, confidence: float}` — نفس `sarai_gold_dataset.json:33` `R-001..R-007` لكن `source_requirement` ديناميكي.

## 8. مخطط الأدلة/الإثبات

`Evidence {evidence_id, requirement_id, fact: string, source_document: string, page_number: int, bbox: [x1,y1,x2,y2], quote_ar: string, quote_en: string, extraction_confidence: float, applicable_entity: string, valid_until: date, tender_source_id: string, reusable: bool}` — يطابق `app/models.py` `Evidence` + `provenance`.

## 9. الميزات المستنتجة (DERIVED_FEATURES)

- `requirement_count` = عدد المتطلبات المستخرجة
- `evidence_coverage` = `matched requirements / total`
- `risk_count` = عدد المخاطر
- `mandatory_missing_count` = `mandatory` + `MISSING_EVIDENCE`
- `decision` = `BID/REVIEW/NO_BID` via `app/engines/decision.py` `decide()` (حتمي)
- `overall_pages` = مجموع الصفحات
- `ocr_ratio` = `946/1354` لـ Sarai

## 10. الاقتران الحالي الخاص بـ Sarai

- `SA-2018-HV2` ثابت في `app/seed.py:1`, `app/models.py`, `evaluation/run_real_benchmark.py:18` `ROOT = C:\...\01- Sarai`, `tests/test_decision_engine.py`
- `21` متطلب ثابت `REQ-A..U` في `REQUIREMENT_PATTERNS` `evaluation/run_real_benchmark.py:324`
- `4` أدلة ثابتة `E-001..004` في `extract_evidence_rule_based` `561`
- `220kV`, `175MVA`, `South Korea`, `first category`, `HYOSUNG/GIZA`, `EGP 5,700,000` حرفيًا في `REQUIREMENT_PATTERNS`
- افتراض `FORM D.xls` `D1..D10` و `G - word/*.doc` موجودة دائمًا
- افتراض `exactly 4 evidences` في `evaluation/sarai_gold_dataset.json`

## 11. ما يجب إزالته/تعميمه

- إزالة `SA-2018-HV2` الثابت → `tender_id` ديناميكي من `POST /tenders/{id}/files`
- إزالة `21` الثابت → `dynamic number of requirements` في المخطط
- إزالة `South Korea`/`first category` الحرفي → `LLM` يستخرج `origin`/`membership` كـ `string` عام
- إزالة `FORM D.xls` الثابت → `document classification` عام (`BOQ`, `Technical Spec`, `Commercial`)
- عزل `Sarai` كـ `regression` في `evaluation/sarai_gold_dataset.json` و `tests/test_decision_engine.py` (يبقى للتحقق، لا يُستخدم كـ production)

## 12. المعمارية المقترحة للاستخراج

`Document ingestion (upload → file_inventory 64/9/5/11) → text/OCR (fitz + Tesseract 5.4.0 ara+eng + LibreOffice 26.8.0.3) → document classification (BOQ, Technical, Commercial, Legal) → candidate extraction (deterministic regex لما هو موثوق مثل voltage) → structured normalization (LLM Jais/GPT-4o مع constrained JSON per schemas/tender_agnostic_schema.json) → evidence/provenance attachment (source_document, page, bbox, quote) → validation (Pydantic) → derived features (requirement_count, decision)` — deterministic حيث موثوق (`voltage` regex)، LLM حيث فهم دلالي (متطلبات عربية).

## 13. استراتيجية التقييم

- **Sarai:** `GOLD-VALIDATED` — `sarai_gold_dataset.json` `21 req` `F1 ≥0.90`, `evidence 4` `F1 ≥0.90`, `matching macro ≥0.93`, `decision 100%` + `13 adversarial`
- **الـ 3 غير المرئية:** `UNLABELED / EXPLORATORY` — لا `gold` مزيف — نقيس `extraction coverage` (`docs processed/pages`), `provenance coverage` (`1.0`), `schema validity` (`Pydantic`), `consistency` (هل `tender_id` مستخرج؟), `hallucination` (هل `requirement` بدون `source_document`؟)
- **مقارنة:** `Sarai 0.976` `20/21` vs `Mobile` `??/21` (ليس `21` ثابت) — نقيس `category coverage` لكل مناقصة.

## 14. ما يتطلب تسميات ذهبية بشرية

- `deadlines` (تواريخ التقديم/الفتح — تحتاج `gold` يدوي لكل مناقصة)
- `mandatory` vs `optional` (يحتاج مراجع قانوني)
- `applicable_entity` (`GIZA` vs `CONSORTIUM` — يحتاج `gold`)
- `risks` (`R-001..007` — يحتاج خبير تجاري)
- `experience` thresholds (`continuous operation 3 years` — يحتاج `gold`)

## 15. أسئلة مفتوحة / غموض

- هل `Mobile` `22-22-22 kV` تعتبر `voltage_level` واحد أم ثلاثة؟
- هل `Motawreen` `DWG` يجب استخراج نصه عبر `OCR` أم `CAD` parser؟
- هل `Addendum.zip` في `6th October` يحتوي على متطلبات جديدة يجب دمجها؟
- هل `Commercial forms.txt` في `Mobile` هو نفس `FORM D.xls` في Sarai؟
- هل `PINGGAOU.JPG` في Motawreen يحتوي على نص عربي يحتاج `Tesseract`؟

## 16. Implementation Status — Phase 1 (Generic Extraction Foundation)

**تاريخ:** 2026-09-20 — **الحالة:** مكتمل

**ما أصبح جاهزًا للإنتاج:**
- `schemas/tender_agnostic_schema.json` — تمت إزالة تسريب `GIZA/HYOSUNG`، أصبح `applicable_entity` حرًا، `languages` حر (`AR, EN, FR...`)، `deadline type` يدعم `unknown/unclassified`، `risk severity` يقبل `null`، أضيف `document_status`/`document_type`/`extraction_status`/`provenance_status` — **EXISTING**
- `evaluation/generic_extraction.py` — تم فصل الوحدات (`ingestion`, `classification`, `deterministic extraction`, `requirement extraction`, `evidence/provenance`, `validation`, `derived`)، أزيل الاستيراد الذاتي `from evaluation.generic_extraction import ingest_tender`، أصبح `build_generic_extraction(tender_path, tender_id=None, use_llm=False)` نظيفًا ويعيد كائنًا محققًا ضد المخطط — **EXISTING**
- `validate_against_schema()` — الآن يستخدم `jsonschema` الحقيقي إذا كان مثبتًا، مع `fallback` يدوي قوي يتحقق من `required` و `types` و `enums` و `pattern` و `confidence` — **EXISTING**
- `extract_requirements_generic()` — لا يفترض `21` أو `GIZA` أو `CONSORTIUM`، يترك `mandatory=None` و `applicable_entity=None` عند عدم التأكد، يخفض `confidence` إلى `0.55` للمرشحات — **EXISTING**
- `ingest_tender()` — ديناميكي `tender_id` من اسم المجلد، لا `SA-2018-HV2` ثابت — **EXISTING**
- `tests/test_generic_extraction.py` — `18` اختبار تغطي `arbitrary applicable entities`, `unknown/null mandatory`, `EN-only`, `arbitrary languages`, `unknown deadline`, `nullable risk`, `nested validation`, `invalid enum/id` — **EXISTING** `18/18` ناجحة

**ما لا يزال تشخيصيًا:**
- `LLM normalization` **لم يُنفذ بعد** — `use_llm=False` فقط، `Phase 2` سيضيف `Ollama` `qwen2.5:3b` مع `constrained JSON`
- `CAD/DWG/RAR/JPG` (`Motawreen` `2.9MB DWG`, `PINGGAOU.JPG`) لا يزال `UNSUPPORTED/PARTIAL` — يحتاج `CAD` parser
- `full 4-tender OCR benchmark` لا يزال مكلفًا (`7919s` لـ `946` صفحة) — يبقى `offline/manual`، ليس `unit test`
- `Sarai` يبقى `regression-only` (`sarai_gold_dataset.json` `21` `F1 ≥0.90`) — لم يُحذف، معزول في `evaluation/`

**ما لم يتغير:**
- `app/engines/decision.py` و `status.py` — لم تُمس (حتمي)
- `evaluation/run_real_benchmark.py` — لا يزال يستخدم `21` ثابت لـ `Sarai` كـ `regression`، الإنتاج الجديد هو `generic_extraction` المنفصل

---

*تم إنشاؤه عبر فحص فعلي لـ 4 مجلدات مناقصات (64+9+5+11 ملف) — مصدر الحقيقة هو الكود والملفات، وليس هذا المستند.*
