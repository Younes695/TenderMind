"""Tender Decision Summary — a short text for the decision maker (owner / GM / tender manager),
built only from the decision pack's facts. Unknown parts say so; nothing is filled in.
The user sends it from their own mail client (the platform never sends mail on its own)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

T = {
    "en": {
        "subject": "Tender decision summary — {title}",
        "hello": "Dear {to},",
        "intro": "Please find below the decision summary for tender {id} — {title}{client}.",
        "score": "Opportunity score: {s}/100 ({band})",
        "score_na": "Opportunity score: insufficient data",
        "elig": "Eligibility: {p}% — {m} of {n} checks met{extra}",
        "elig_na": "Eligibility: not checked (company capabilities missing)",
        "elig_unclear": ", {n} with information missing",
        "elig_failed": ", {n} not met",
        "cost": "Estimated material cost (ESTIMATE, from supplier price lists): {totals} — {p} of {n} BOQ lines priced",
        "cost_na": "Estimated material cost: no priced BOQ lines (PRICE UNAVAILABLE)",
        "cost_nb": "Estimated material cost: no BOQ with quantities in the documents (INSUFFICIENT DATA)",
        "dates": "Important dates:",
        "risks": "Main risks:",
        "similar": "Similar past tenders:",
        "missing": "Missing information:",
        "none": "none recorded",
        "decision": "Final decision: {d} — {r}",
        "decision_open": "Final decision: not taken yet — the decision belongs to the company's authorised team.",
        "partner": "Certificates need a partner or supplier: {items}",
        "conflicts": "{n} contradiction(s) between the tender documents",
        "gaps": "{n} mandatory requirement(s) failed or not evidenced",
        "failed": "Eligibility not met: {items}",
        "sign": "Prepared with TenderMind. Every fact above links to its source in the decision pack.",
        "outcome": {"WON": "won", "LOST": "lost", "SUBMITTED": "submitted", "NOT_SUBMITTED": "not submitted"},
        "band": {"GO": "strong fit", "REVIEW": "needs review", "NO_GO": "high risk"},
    },
    "ar": {
        "subject": "ملخص قرار المناقصة — {title}",
        "hello": "السيد/ة {to}،",
        "intro": "مرفق أدناه ملخص القرار للمناقصة {id} — {title}{client}.",
        "score": "درجة الفرصة: {s}/100 ({band})",
        "score_na": "درجة الفرصة: بيانات غير كافية",
        "elig": "الأهلية: {p}% — تحقق {m} من {n} شروط{extra}",
        "elig_na": "الأهلية: لم تُفحص (قدرات الشركة غير مسجلة)",
        "elig_unclear": "، {n} بمعلومات ناقصة",
        "elig_failed": "، {n} غير متحقق",
        "cost": "تكلفة المواد التقديرية (تقديري، من قوائم أسعار الموردين): {totals} — {p} من {n} بند مسعّر",
        "cost_na": "تكلفة المواد التقديرية: لا توجد بنود مسعّرة (السعر غير متاح)",
        "cost_nb": "تكلفة المواد التقديرية: لا يوجد جدول كميات بكميات في المستندات (بيانات غير كافية)",
        "dates": "التواريخ المهمة:",
        "risks": "أهم المخاطر:",
        "similar": "مناقصات سابقة مشابهة:",
        "missing": "معلومات ناقصة:",
        "none": "لا يوجد",
        "decision": "القرار النهائي: {d} — {r}",
        "decision_open": "القرار النهائي: لم يُتخذ بعد — القرار لفريق الشركة المخوَّل.",
        "partner": "شهادات تحتاج شريكًا أو موردًا: {items}",
        "conflicts": "{n} تعارض بين مستندات المناقصة",
        "gaps": "{n} متطلب إلزامي غير متحقق أو بدون دليل",
        "failed": "شروط أهلية غير متحققة: {items}",
        "sign": "أُعد باستخدام TenderMind. كل معلومة أعلاه مرتبطة بمصدرها في حزمة القرار.",
        "outcome": {"WON": "فازت", "LOST": "لم تفز", "SUBMITTED": "قُدمت", "NOT_SUBMITTED": "لم تُقدم"},
        "band": {"GO": "توافق قوي", "REVIEW": "تحتاج مراجعة", "NO_GO": "مخاطرة عالية"},
    },
}


DATE_AR = {"Submission deadline": "آخر موعد للتقديم", "Pre-bid / job explanation meeting": "اجتماع ما قبل العطاء / شرح المناقصة"}


def _money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.0f}"


def build(pack: Dict[str, Any], materials: Optional[Dict[str, Any]], similar: List[Dict[str, Any]],
          dates: List[Dict[str, Any]], final: Optional[Dict[str, Any]], lang: str = "en",
          to: str = "") -> Dict[str, Any]:
    L = T["ar" if lang == "ar" else "en"]
    t = pack["tender"]
    lines: List[str] = []
    add = lines.append
    add(L["hello"].format(to=to.strip() or ("Management" if lang != "ar" else "الإدارة")))
    add("")
    add(L["intro"].format(id=t["id"], title=t.get("title") or t["id"],
                          client=f" ({t['client']})" if t.get("client") else ""))
    add("")
    sc = pack.get("score") or {}
    add(L["score"].format(s=sc["score"], band=L["band"].get(sc.get("band"), sc.get("band")))
        if sc.get("score") is not None else L["score_na"])
    es = (pack.get("eligibility") or {}).get("score")
    if es:
        extra = (L["elig_unclear"].format(n=es["unclear"]) if es["unclear"] else "") + \
                (L["elig_failed"].format(n=es["failed"]) if es["failed"] else "")
        add(L["elig"].format(p=es["percent"], m=es["met"], n=es["total"], extra=extra))
    else:
        add(L["elig_na"])
    if not materials or not materials.get("lines"):
        add(L["cost_nb"])
    elif materials.get("totals"):
        totals = " + ".join(_money(x["amount"], x["currency"]) for x in materials["totals"])
        add(L["cost"].format(totals=totals, p=materials["priced"], n=len(materials["lines"])))
    else:
        add(L["cost_na"])
    add("")
    add(L["dates"])
    for d in dates[:6] or []:
        label = DATE_AR.get(d["label"], d["label"]) if lang == "ar" else d["label"]
        add(f"  - {label}: {d['date']}" + (f" ({d['file']}, p.{d['page']})" if d.get("file") else ""))
    if not dates:
        add(f"  - {L['none']}")
    add(L["risks"])
    risks = []
    cs = (pack.get("certifications") or {}).get("summary") or {}
    if cs.get("needs_partner"):
        names = [c["name"] for c in (pack.get("certifications") or {}).get("items", [])
                 if c.get("status") in ("PARTNER_NEEDED", "MISSING")][:4]
        risks.append(L["partner"].format(items=", ".join(names)))
    failed = [c.get("label") for c in ((pack.get("eligibility") or {}).get("checks") or []) if c.get("result") == "FAIL"]
    if failed:
        risks.append(L["failed"].format(items=", ".join(failed[:4])))
    if pack.get("conflicts"):
        risks.append(L["conflicts"].format(n=len(pack["conflicts"])))
    if pack.get("gaps"):
        risks.append(L["gaps"].format(n=len(pack["gaps"])))
    for r in risks or [L["none"]]:
        add(f"  - {r}")
    add(L["similar"])
    for s in similar[:3] or []:
        out = L["outcome"].get(s.get("outcome") or "", "")
        add(f"  - {s['title'] or s['id']} — {s['score']}%" + (f" ({out})" if out else ""))
    if not similar:
        add(f"  - {L['none']}")
    add(L["missing"])
    miss = [m.get("title") or m.get("text") or m.get("summary") for m in (pack.get("missing_documents") or [])][:5]
    for m in [x for x in miss if x] or [L["none"]]:
        add(f"  - {m}")
    add("")
    if final and final.get("decision"):
        add(L["decision"].format(d=final["decision"], r=final.get("reason") or ""))
    else:
        add(L["decision_open"])
    add("")
    add(L["sign"])
    return {"subject": L["subject"].format(title=t.get("title") or t["id"]), "body": "\n".join(lines)}
