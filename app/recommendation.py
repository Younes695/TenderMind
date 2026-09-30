"""Stage 5J — plain-language bid recommendation and a first-draft email.

Both are built only from facts the system already holds (decision engine rows,
the tender analysis, open review items, the company profile), so nothing is
invented. The decision itself stays rule-based (app/engines/decision.py); this
module explains it and turns it into next steps. English and Arabic text.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

T = {
    "en": {
        "BID": "Recommendation: bid.",
        "NO_BID": "Recommendation: do not bid.",
        "REVIEW": "Recommendation: bid only if the conditions below are met.",
        "NONE": "No recommendation yet — process the tender and run Evaluate with your company documents.",
        "why_fail": "Mandatory requirements your documents contradict",
        "conditions": "Before bidding, close these gaps",
        "review": "Needs a decision by your team",
        "deadlines": "Key dates",
        "risks": "Watch out for",
        "open_items": "{m} missing item(s) and {q} open question(s) in this tender.",
        "not_evaluated": "Company match not measured yet — upload your company documents and run Evaluate.",
        "counts": "Mandatory requirements: {p} met, {f} contradicted, {r} unclear, {x} without evidence.",
        "subject": "Expression of interest and clarification requests — {title}",
        "greet": "Dear {client},",
        "intro": "{company} is pleased to express its interest in tender {ref} — {title}.",
        "about": "About us:",
        "ask": "Before submitting our offer, we kindly ask for clarification on the following points:",
        "missing": "We also could not find these documents referenced in the tender package; we would be grateful if you could share them:",
        "close": "We look forward to your reply and to submitting a competitive offer.",
        "regards": "Best regards,",
        "client": "Tender Committee",
    },
    "ar": {
        "BID": "التوصية: الدخول في المناقصة.",
        "NO_BID": "التوصية: عدم الدخول في المناقصة.",
        "REVIEW": "التوصية: الدخول فقط بعد استيفاء الشروط التالية.",
        "NONE": "لا توجد توصية بعد — حلّل المناقصة ثم شغّل التقييم بمستندات شركتك.",
        "why_fail": "متطلبات إلزامية تتعارض معها مستنداتكم",
        "conditions": "قبل الدخول، استكملوا ما يلي",
        "review": "يحتاج قرارًا من فريقكم",
        "deadlines": "مواعيد مهمة",
        "risks": "انتبهوا إلى",
        "open_items": "{m} عنصر ناقص و{q} سؤال مفتوح في هذه المناقصة.",
        "not_evaluated": "لم تُقَس مطابقة الشركة بعد — ارفع مستندات شركتك وشغّل التقييم.",
        "counts": "المتطلبات الإلزامية: {p} مستوفى، {f} متعارض، {r} غير واضح، {x} بلا دليل.",
        "subject": "إبداء اهتمام وطلب استيضاحات — {title}",
        "greet": "السادة {client} المحترمين،",
        "intro": "يسر {company} أن تبدي اهتمامها بالمناقصة رقم {ref} — {title}.",
        "about": "نبذة عن الشركة:",
        "ask": "قبل تقديم عرضنا، نرجو التكرم بتوضيح النقاط التالية:",
        "missing": "كما لم نجد المستندات التالية المشار إليها في ملف المناقصة، ونرجو التكرم بإرسالها:",
        "close": "نتطلع إلى ردكم الكريم وإلى تقديم عرض تنافسي.",
        "regards": "وتفضلوا بقبول فائق الاحترام،",
        "client": "لجنة المناقصات",
    },
}

_DEADLINE_TYPES = {"submission": ("Submission", "آخر موعد للتقديم"), "opening": ("Bid opening", "فتح المظاريف"),
                   "validity": ("Bid validity", "صلاحية العرض"), "completion": ("Completion", "مدة التنفيذ")}


def build_recommendation(detail: Dict[str, Any], analysis: Optional[Dict[str, Any]],
                         review: Optional[Dict[str, int]], lang: str = "en") -> Dict[str, Any]:
    tx = T["ar" if lang == "ar" else "en"]
    if not detail or not detail.get("available"):
        return {"decision": None, "headline": tx["NONE"], "sections": []}
    dec = (detail.get("decision") or {}).get("decision") or "REVIEW"
    mand = [r for r in detail.get("requirements") or [] if r.get("mandatory")]
    by = {s: [r for r in mand if r.get("status") == s] for s in ("PASS", "FAIL", "REVIEW", "MISSING_EVIDENCE")}
    line = lambda r: f"{r.get('requirement')} ({r.get('source_document') or ''} {r.get('page_or_section') or ''})".replace(" ()", "").strip()
    sections: List[Dict[str, Any]] = []
    if by["FAIL"]:
        sections.append({"title": tx["why_fail"], "items": [line(r) for r in by["FAIL"][:6]]})
    if by["MISSING_EVIDENCE"]:
        sections.append({"title": tx["conditions"], "items": [line(r) for r in by["MISSING_EVIDENCE"][:8]]})
    if by["REVIEW"]:
        sections.append({"title": tx["review"], "items": [line(r) for r in by["REVIEW"][:6]]})
    dates = []
    for d in (analysis or {}).get("deadlines") or []:
        if d.get("date") and d.get("type") in _DEADLINE_TYPES:
            label = _DEADLINE_TYPES[d["type"]][1 if lang == "ar" else 0]
            dates.append(f"{label}: {d['date']}")
    if dates:
        sections.append({"title": tx["deadlines"], "items": dates[:5]})
    risks = [r.get("description") or r.get("summary") for r in (analysis or {}).get("risks") or []]
    risks = [r for r in risks if r][:5]
    if risks:
        sections.append({"title": tx["risks"], "items": risks})
    notes = [tx["counts"].format(p=len(by["PASS"]), f=len(by["FAIL"]), r=len(by["REVIEW"]), x=len(by["MISSING_EVIDENCE"]))]
    if review and (review.get("missing_open") or review.get("question_open")):
        notes.append(tx["open_items"].format(m=review.get("missing_open", 0), q=review.get("question_open", 0)))
    evaluated = any(r.get("evidence") for r in mand) or by["PASS"] or by["FAIL"]
    match = round(100 * len(by["PASS"]) / len(mand)) if mand and evaluated else None
    if mand and not evaluated:
        notes.insert(0, tx["not_evaluated"])
    return {"decision": dec, "headline": tx.get(dec, tx["REVIEW"]), "notes": notes, "sections": sections,
            "match_percent": match, "mandatory_total": len(mand), "mandatory_met": len(by["PASS"])}


def build_email(tender: Dict[str, Any], company: Optional[Dict[str, Any]], questions: List[Dict[str, Any]],
                missing: List[Dict[str, Any]], lang: str = "en") -> Dict[str, str]:
    tx = T["ar" if lang == "ar" else "en"]
    c = company or {}
    name = c.get("name") or ("[اسم الشركة]" if lang == "ar" else "[Company name]")
    title = tender.get("title") or tender.get("id")
    body = [tx["greet"].format(client=tender.get("client") or tx["client"]), "",
            tx["intro"].format(company=name, ref=tender.get("id"), title=title)]
    if c.get("intro"):
        body += ["", tx["about"], c["intro"]]
    qs = [q for q in questions if q.get("detail") or q.get("title")][:10]
    if qs:
        body += ["", tx["ask"]]
        for i, q in enumerate(qs, 1):
            where = f" ({q['source_document']}{', p. ' + q['page'] if q.get('page') and len(q['page']) < 20 else ''})" if q.get("source_document") else ""
            text = (q.get("detail") or q.get("title") or "").split("\n")[0]
            body.append(f"{i}. {text}{where}")
    ms = [m for m in missing if m.get("detail")][:5]
    if ms:
        body += ["", tx["missing"]] + [f"- {m['detail'][:400]}" for m in ms]
    sign = [x for x in (c.get("contact_name"), c.get("contact_title"), name, c.get("phone"), c.get("email"), c.get("website"), c.get("address")) if x]
    body += ["", tx["close"], "", tx["regards"], *sign]
    return {"subject": tx["subject"].format(title=title), "body": "\n".join(body)}
