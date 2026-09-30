# Rules for adding Arabic to a set of React files (TenderMind frontend)

Project: C:\Users\EgyTech\Desktop\TenderMind\frontend\src
Read first: src/i18n/index.jsx (the i18n system) and the finished example
src/pages/Settings.jsx + src/i18n/ar/settings.js.

1. Edit ONLY the files you were given. Other agents edit other files at the same time.
2. In each React component that renders text: `import { useT } from "../i18n";`
   (correct relative path) and `const t = useT();` inside the component, above any
   early `return`. Wrap every user-visible English string — JSX text, placeholders,
   aria-labels, titles, button labels, messages the UI composes — as `t("…")`.
   Values: `t("{n} documents", { n })`.
3. Strings in module-level arrays/objects stay English there; translate where they
   are rendered: `t(item.label)`, `features.map((f) => t(f))`.
4. The English passed to t() must stay EXACTLY as it is now (tests search the
   English text). Do not change data-testid, routes, logic, API calls, props,
   exports or styling (except rule 7).
5. Never translate: brand names (TenderMind, Google, Microsoft, Etimad), tender IDs,
   file names, codes (BID, REVIEW, NO_BID, LEGAL, TECHNICAL…), data from the server,
   technical abbreviations (RFP, BOQ, AI, OCR, kV, HVAC, ISO 27001).
6. Arabic: Modern Standard Arabic, professional and concise, for contractors and
   tender teams in Egypt and the Gulf. Glossary: Tender = مناقصة, Tenders = المناقصات,
   Dashboard = لوحة التحكم, Go / No-Go = قرار الدخول, Requirements = المتطلبات,
   Evidence = الأدلة, Upload = رفع, Start processing = بدء التحليل, Settings = الإعدادات,
   Notifications = الإشعارات, Q&A = الأسئلة والاستيضاحات, Subcontractors = مقاولو الباطن,
   Company Knowledge = مستندات الشركة, Work Packages = حزم العمل, Approvals = الموافقات,
   Documents = المستندات, Analytics = التحليلات, Help = المساعدة, News = أخبار المناقصات,
   New Tender = مناقصة جديدة, Sign out = تسجيل الخروج, Log in = تسجيل الدخول,
   Sign up = إنشاء حساب, Book a Demo = احجز عرضًا توضيحيًا, Talk to Sales = تواصل مع المبيعات.
7. RTL: Arabic makes the page right-to-left. In your files, change side-specific
   classes to logical ones: ml-→ms-, mr-→me-, pl-→ps-, pr-→pe-, left-→start-,
   right-→end-, text-left→text-start, text-right→text-end, border-l→border-s,
   border-r→border-e, rounded-l→rounded-s, rounded-r→rounded-e.
8. Put all your translations in the ONE dictionary file you were given:
   `export default { "English text": "Arabic text", ... };`
9. Finish by running ONLY the test files you were given:
   `cd C:\Users\EgyTech\Desktop\TenderMind\frontend && npx vitest run <files>` — they must pass.
   Do not run the full suite or the build. Do not touch git.
10. Report: files changed, number of strings, test result (one short paragraph).
11. NEVER run git commands (no checkout, restore, stash, reset) and never replace a
    file with an older version. The files contain today's uncommitted work.
    Edit in place only. Do not "fix" quotes or dashes in files you were not given.
12. Use only straight ASCII quotes (" and ') for JavaScript strings and imports.
    Keep em dashes (—) and other characters inside English strings exactly as they are.
