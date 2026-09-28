# ✅ آخر حالة (28 سبتمبر 2026، بعد Stage 5J)
- تصنيف المتطلبات: "غير مصنّف" في طريف نزل من **19% لـ 4.4%** بقواعد ثابتة بتشتغل بس على اللي الموديل ما صنّفوش (دقة ~93% على 240 بند اتراجعوا بالإيد).
- الاختبارات: الباك اند **505 ناجح**، والفرونت اند **73/73**، وبناء الإنتاج سليم.
- آخر commit: `43635d8` على فرع `stage-5g-production-hardening` (من غير push).
- الجديد: التوصية ونسبة المطابقة، والقيمة المتوقعة، ومسودة الإيميل، وبيانات الشركة، وأخبار الكهرباء، والموردين، والإعدادات، والعربي كامل.
- عشان يتنشر: محتاج سيرفر (يفضّل بكارت شاشة 8GB أو أكتر) ودومين. الخطوات تحت.

---

# ✅ الحالة بعد Stage 5G (28 سبتمبر 2026)

## التشغيل بـ Docker (الطريقة الموصى بيها)
```bash
cp .env.example .env      # حط TENDERMIND_SESSION_SECRET (32 حرف على الأقل)
docker compose up -d --build
```
بيشغّل التطبيق + Ollama وبينزّل qwen2.5:3b و qwen3:4b أول مرة (~4.5 GB). التطبيق على `127.0.0.1:8001` —
حط قدامه reverse proxy بـ HTTPS (Caddy / nginx). البيانات في volume اسمه `tendermind-data`.
⚠️ ملفات Docker اتكتبت واتعملها `docker compose config` بس **ماتبنتش** على جهاز التطوير لأن Docker Desktop بايظ عليه — أول بناء على السيرفر هو أول تجربة حقيقية.

## اللي اتصلح (التفاصيل في `docs/STAGE_5G_PRODUCTION_HARDENING.md`)
- 🔴 أي حساب جديد كان بيشوف ويمسح مناقصات وملفات كل الحسابات التانية → دلوقتي كل حساب شايف بياناته بس.
- 🔴 ثغرة دخول على حساب أي حد عن طريق Microsoft sign-in → اتقفلت.
- 🔴 تسطيب نضيف من `requirements.txt` كان بيقع وقت التشغيل (5 مكتبات ناقصة) → اتضافت.
- ثغرات معروفة في Pillow و Starlette و python-dotenv → اتحدّثت، `pip-audit` و `npm audit` صفر.
- حماية من تخمين الباسورد، security headers، `/docs` مقفولة في البرودكشن، `/health` بيفحص قاعدة البيانات.

## الـ AI (التفاصيل في `docs/STAGE_5G_ESCALATION.md`)
تصنيف المتطلبات على 70 بند: **60/70 (0.857) → 62/70 (0.886)** بإن البنود اللي qwen2.5:3b مش متأكد منها بتتسأل تاني لـ qwen3:4b.

---

# ⚡ أسرع طريقة تشغيل (3 أوامر)
```bash
pip install -r requirements.txt && apt-get install -y tesseract-ocr tesseract-ocr-ara
cp .env.example .env        # واملى الإيميل والباسورد والـ SESSION_SECRET
./run_prod.sh
```
`run_prod.sh` بيتأكد قبل التشغيل من: الأسرار موجودة، الـ secret طوله ≥32، مكتبات بايثون متسطبة، tesseract موجود (تحذير بس)، والفرونت اند مبني (ولو مش مبني بيبنيه). لو في حاجة ناقصة بيرفض يقوم ويقولك إيه بالظبط. اتجرب: من غير أسرار رفض، وبالأسرار قام وسيرف الصفحة وقفل الـ API على غير المسجلين.

## حالة الاختبارات النهائية
- الباك اند: **369 ناجح + 1 متخطّى** (اختبار Azure smoke محتاج ملفات تندر ساراي الأصلية اللي مش في الريبو).
- الفرونت اند: **46/46**.
- الـ 8 اختبارات القديمة اتحدّثت: بقت بتتأكد من مسار الملف من قاعدة البيانات، **وكمان** بتتأكد إن الـ API مابيسربش مسارات السيرفر للعميل (يعني الإصلاح الأمني بقى محمي باختبار بدل ما كان بيكسره). ومسار الـ fixture اتصلح لمسار نسبي جوه المشروع بدل ديسكتوب المطوّر.

---

# نشر سريع للبروداكشن — بعد الإصلاحات (تحديث 2)

## جولة إصلاحات إضافية بعد مراجعة ثانية (verified against real test run + live E2E)
بعد المراجعة الأولى، تم اكتشاف باگ **حرج فعلي** إضافي عبر تشغيل test suite كامل ومقارنته بمراجعة خارجية:

### 🔴 اكتُشف وأُصلح: مسار Tesseract كان مكتوب بصيغة Windows فقط
`evaluation/tesseract_local_ocr.py` كان فيه:
```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```
وده كان بيخلي **أي صفحة PDF محتاجة OCR (ممسوحة ضوئيًا) أو حتى صفحة فيها أقل من 100 حرف نص أصلي** تفشل بصمت على أي سيرفر Linux وترجع نص فاضي — يعني تندر حقيقي جديد ممكن يطلع بصفر requirements من غير أي error ظاهر. ده كان بيفسّر جزء كبير من فشل 9 اختبارات كانت شكلها "منطق استخراج بايظ" بينما هي فعليًا سبب واحد بسيط.

**الإصلاح**: `_resolve_tesseract_cmd()` بقى بيدور بالترتيب: env var → `shutil.which` (PATH) → مسارات شائعة (Windows/Linux/Mac) → fallback لاسم الأمر العادي. نفس الباترن اللي كان مستخدم أصلًا مع LibreOffice (`_find_soffice_executable`) وشغال كويس.

**تأثير الإصلاح على الاختبارات**: من 17 فشل → 8 فشل. كل الـ9 اللي اتصلحوا كانوا نفس السبب (tesseract) + واحد إضافي (`xlrd` ناقصة لملفات `.xls` القديمة — اتضافت لـ requirements.txt).

### ✅ تحقق عملي كامل (end-to-end حقيقي، مش mocked)
شغّلت السيرفر بمتغيرات production حقيقية (`TENDERMIND_ENV=production` + أوث مفعّل) وعملت الرحلة كاملة عبر الـ API:
1. طلب على endpoint محمي من غير session → **401** ✅
2. تسجيل دخول بباسورد غلط → **401** ✅
3. تسجيل دخول صح → session cookie اتحطت ✅
4. إنشاء تندر جديد (مش الديمو المزروع) ✅
5. رفع PDF حقيقي فيه نص عن متطلبات فنية/مالية/تجارية ✅
6. تشغيل `/process` ومتابعته لحد `COMPLETED` ✅
7. `/analysis` رجع **5 requirements حقيقية مستخرجة ديترمينستك** (EXPERIENCE, TECHNICAL, COMMERCIAL, FINANCIAL...) مع `source_document` + `page_number` + `quote` لكل واحد ✅
8. تسجيل خروج → نفس الكوكي بقت مرفوضة (401) على أي endpoint محمي ✅

يعني مسار "Login → Session → Protected Dashboard → Create Tender → Upload → Process → Analysis" شغال فعليًا من أول لآخر خطوة، مش مجرد كود موجود ومش متأكد إنه متوصل.

### باقي الـ8 فشل — اتفحصوا واحد واحد، مفيش منهم production bug حقيقي:
| المجموعة | العدد | السبب الحقيقي |
|---|---|---|
| `test_tender_upload_api.py` + `test_e2e_upload_process.py` | 6 | بتتوقع إن الـ API يرجّع `path`/`source_path` (مسار الملف على السيرفر) في الـ response. الكود الحالي **عن قصد** بيشيلهم من كل الـ responses (upload + list) عشان ميسربش مسارات filesystem للعميل — قرار أمني صحيح وثابت، مش regression. الاختبارات نفسها قديمة ومحتاجة تتحدث لتعكس السلوك ده، مش الكود. |
| `test_smoke_azure.py` + `test_llm_generic_extraction.py::test_fixture_does_not_trigger_ocr` | 2 | بيفترضوا مسار ثابت على جهاز مطوّر معيّن (`C:\Users\EgyTech\Desktop\...`) — سكريبتات evaluation/benchmark بتاعة تطوير محلي، مش في مسار التطبيق الحي خالص. |

لو حابب أحدّث الاختبارات القديمة دي تعكس السلوك الفعلي (بدل تجاهلها)، قولّي وأعملها — مش مستعجلة لأنها مش بتأثر على المنتج الشغال.

---

## اللي اتصلح من قبل (لسه سارِ)
1. **requirements.txt** — `PyMuPDF`, `pytesseract`, `Pillow`, `xlrd` (كل الناقص لاستخراج PDF/OCR/Excel القديم).
2. **app/main.py** — بيسيرف `frontend/dist` الحقيقي بدل الكود المصدري الخام، + SPA fallback، + CORS قابل للتهيئة.
3. **frontend/src/App.jsx** — `ProtectedRoute` موصول فعليًا على `/dashboard`, `/go-no-go`, `/tenders/*`.
4. **evaluation/tesseract_local_ocr.py** — اكتشاف Tesseract بيشتغل على أي نظام تشغيل (مش Windows بس).
5. **frontend/dist/** — مبني من جديد بالكود الحالي.

اتأكدت من كل ده حيًّا: 362/370 اختبار باك اند ناجح، 46/46 فرونت اند ناجح، ورحلة E2E كاملة عدّت فعليًا.

## اللي لسه محتاج منك (سيكرتس)
```bash
export TENDERMIND_ENV=production
export TENDERMIND_AUTH_EMAIL="you@company.com"
export TENDERMIND_AUTH_PASSWORD="اختار-باسورد-قوي"
export TENDERMIND_SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export TENDERMIND_COOKIE_SECURE=true          # لو السيرفر شغال على https
```

## القرار بالدليل للمناقصات المرفوعة (Stage 5C) — التفاصيل في `docs/STAGE_5C_DECISION_BRIDGE.md`
- أي مناقصة تترفع وتتعالج بقى ليها قرار BID / REVIEW / NO_BID في صفحة المناقصة.
- ارفع مستندات الشركة (مرة واحدة) من نفس الصفحة → اضغط Evaluate → كل متطلب بيتطابق مع مستندات الشركة ويطلع PASS/FAIL/REVIEW/MISSING بالاقتباس والملف والصفحة.
- أمان: FAIL ماينفعش غير بثقة ≥ 0.8 واقتباس حرفي موجود فعلًا في مستند الشركة، غير كده REVIEW.
- ملف تجريبي (شركة وهمية) للعرض: `demo/Demo_Company_Profile_FICTIONAL.md`.

## تحديث الذكاء الاصطناعي (Stage 5A) — التفاصيل في `docs/STAGE_5A_PROMPT_AND_ROUTING.md`
- برومبت جديد `minimal-2` (الديفولت): دقة تصنيف المتطلبات بنفس الموديل ونفس السرعة
  طلعت من 69% → 94% (primary)، 61% → 85% (secondary)، 52% → 86% (Sarai holdout).
- الـ workers المتوازية كانت مكتوبة بس مش متوصلة — اتوصلت.
- باگ كان بيوقّع أي تشغيل AI في مرحلة الحفظ لما مكتبة `jsonschema` تكون متسطبة (confidence = null) — اتصلح واتضافت `jsonschema` لـ requirements.
- البنود اللي qwen2.5:3b يرجعها UNKNOWN بتتسأل تاني لـ qwen3:4b افتراضيًا (`TENDERMIND_ESCALATION_MODEL`, و `off` يقفله). لازم `ollama pull qwen3:4b` على السيرفر.

إعدادات البروداكشن المقترحة:
```bash
export TENDERMIND_TWO_STAGE_LLM=1
export OLLAMA_MODEL="qwen2.5:3b"
export TENDERMIND_WORKERS_ENABLED=1
export TENDERMIND_MAX_AI_WORKERS=2
# rollback للبرومبت القديم لو احتجت: export TENDERMIND_PROMPT_VERSION=minimal-1
```

## قرار الذكاء الاصطناعي (القديم — قبل 5A)
بالديفولت الاستخراج ديترمينستك فقط (زي ما شفت في التحقق العملي فوق — وده شغال كويس فعلًا). لو عايز مطابقة LLM حقيقية:
```bash
export TENDERMIND_TWO_STAGE_LLM=1
export OLLAMA_BASE_URL="http://<your-ollama-host>:11434"
export OLLAMA_MODEL="qwen2.5:3b"
```
لو مفيش Ollama متاح، سيب الفلاج مقفول — النظام هيفضل شغال بالاستخراج الديترمينستك (زي ما أثبتنا فوق إنه بيرجع نتايج حقيقية مش فاضية).

## خطوات التشغيل
```bash
cd TenderMind
pip install -r requirements.txt
apt-get install -y tesseract-ocr tesseract-ocr-ara   # مطلوب على مستوى النظام لـ OCR

cd frontend && npm install && npm run build && cd ..

# متغيرات البيئة فوق، ثم:
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1
```
> `--workers 1` مهم: SQLite + رفع ملفات على القرص المحلي، أكتر من worker ممكن يتعارض.

## اللي لسه مش production-grade فعليًا (موثّق، مش هيتحل في ساعتين بأمان)
- SQLite بدل قاعدة بيانات حقيقية متزامنة.
- مفيش queue حقيقي (Redis/Celery).
- زرار "تسجيل دخول بجوجل" مش موصول بالباك اند فعليًا (console.log بس).
- مفيش Dockerfile/CI جاهز.

