"""Stage 8 — the assistant: answers the Tender Manager's questions from the company's own data.

Known questions (English or Arabic wording) are answered directly from the records — overdue tasks,
deadlines, suitability, why the recommendation, similar tenders, client history, certificates /
partners, the submission checklist, contradictions. Anything else: the tender's requirements are
searched and the best matching quotes are returned with file + page; when the local model is up it
writes a short answer from those quotes only. Every answer carries its sources. Nothing is invented.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

INTENTS = [  # narrow phrases only; anything unsure goes to the search
    ("overdue", r"overdue|متأخر|متاخر|فات ميعاد"),
    ("deadlines", r"\bdeadlines?\b|submission date|when .* submit|مواعيد|موعد التقديم|ميعاد التقديم|امتى .*نقدم"),
    ("why", r"\bwhy\b.{0,40}(recommend|score|go\b|no-?go|decision)|reason for the (recommendation|score|decision)|"
            r"(ليه|لماذا|سبب).{0,20}(التوصية|الدرجة|القرار|نو جو|راجع)"),
    ("suitable", r"suitable|eligib|should we (bid|go)|worth (it|bidding)|مناسب|ندخل|أهلية|اهلية"),
    ("certificates", r"certif|partner|iso\b|prequal|approved|شهاد|شريك|تأهيل|تاهيل|اعتماد"),
    ("client", r"client|customer|owner|worked with|العميل|عميل"),
    ("similar", r"similar|participated|done .{0,20} before|مشابه|شبه|قبل كده|قبل كدا"),
    ("checklist", r"checklist|submission (items|documents)|what .* submit|مستندات التقديم|قائمة|قايمة"),
    ("conflicts", r"conflict|contradict|disagree|تعارض|اختلاف"),
    ("bulk", r"bulk|same materials?|شراء مجمع|نفس الماد|نفس الخامات"),
]
_RX = [(k, re.compile(p, re.IGNORECASE)) for k, p in INTENTS]


def intent_of(question: str) -> str:
    q = question or ""
    # "why" wins when combined with a recommendation / score word
    for k, rx in _RX:
        if rx.search(q):
            return k
    return "search"


_WHO = {"bidder": "the company", "partner": "a manufacturer / supplier / subcontractor", "staff": "staff",
        "unclear": "not stated"}
_STATUS = {"MISSING": "missing", "PARTNER_NEEDED": "partner needed", "CHECK": "to check", "HELD": "held"}


def L(key: str, **vars_) -> Dict[str, Any]:
    return {"key": key, "vars": vars_}


_QSTOP = {"what", "which", "does", "the", "this", "that", "tender", "with", "have", "for", "are", "how", "about",
          "is", "was", "our", "there", "any", "from", "and", "can"}


def _query_terms(question: str):
    # Latin and Arabic words (the packages mix both; Arabic documents are searched too)
    words = [w for w in re.findall(r"[a-z0-9]{3,}|[\u0621-\u064a]{3,}", question.lower()) if w not in _QSTOP]
    phrases = [f"{a} {b}" for a, b in zip(words, words[1:])]
    return set(words), phrases


def _score(text: str, words, phrases) -> float:
    low = text.lower()
    sc = sum(1.0 for w in words if w in low) + sum(2.5 for p in phrases if p in low)
    if sc and re.search(r"\d", low):
        sc += 0.5  # an answer usually carries a number / date / percentage
    return sc


def _search(db, tender_ids: List[str], question: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Best matching sentences of the tender pages (one tender) or requirements (several tenders)."""
    from app.models import TenderAnalysis
    words, phrases = _query_terms(question)
    if not words:
        return []
    hits = []
    if len(tender_ids) == 1:
        try:
            from app.sections import sources_from_cache
            pages = sources_from_cache(tender_ids[0])
        except Exception:
            pages = []
        for p in pages:
            for sent in re.split(r"(?<=[.;])\s+|\n{2,}", p.text or ""):
                sent = " ".join(sent.split())
                if 25 <= len(sent) <= 600:
                    sc = _score(sent, words, phrases)
                    if sc >= 2:
                        hits.append((sc, tender_ids[0], p.source_document, p.page_number, sent))
    if not hits:
        for tid in tender_ids:
            a = (db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tid)
                 .order_by(TenderAnalysis.created_at.desc()).first())
            for r in (a.requirements if a else None) or []:
                text = " ".join(f"{r.get('summary') or ''} {r.get('source_text') or ''}".split())
                sc = _score(text, words, phrases)
                if sc:
                    hits.append((sc, tid, r.get("source_document"), r.get("page_number"),
                                 " ".join(str(r.get("source_text") or r.get("summary") or "").split())))
    hits.sort(key=lambda h: -h[0])
    seen, out = set(), []
    for _sc, tid, f, pg, q in hits:
        if q[:80] in seen:
            continue
        seen.add(q[:80])
        out.append({"tender_id": tid, "file": f, "page": pg, "quote": q[:300]})
        if len(out) == limit:
            break
    return out


def _llm_answer(question: str, sources: List[Dict[str, Any]], lang: str) -> Optional[str]:
    """Short answer from the quotes only, if the local model is available (best-effort)."""
    try:
        import requests
        from app.pipeline.config import ollama_endpoint, llm_model
    except Exception:
        try:
            import os
            import requests
            base = (os.environ.get("TENDERMIND_OLLAMA_ENDPOINT") or os.environ.get("OLLAMA_BASE_URL")
                    or "http://localhost:11434").rstrip("/")
            model = os.environ.get("TENDERMIND_OLLAMA_MODEL") or os.environ.get("OLLAMA_MODEL") or "qwen2.5:3b"
        except Exception:
            return None
    else:
        base, model = ollama_endpoint().rstrip("/"), llm_model()
    quotes = "\n".join(f"[{i + 1}] {s['file']} p.{s['page']}: {s['quote']}" for i, s in enumerate(sources))
    prompt = (("Answer in Arabic. " if lang == "ar" else "Answer in English. ")
              + "Use ONLY the numbered quotes from the tender below. If they do not answer the question, say so. "
                "Cite quote numbers like [1]. At most 4 sentences.\n\nQuotes:\n" + quotes + "\n\nQuestion: " + question)
    try:
        r = requests.post(f"{base}/api/generate", json={"model": model, "prompt": prompt, "stream": False,
                                                         "options": {"temperature": 0}}, timeout=45)
        r.raise_for_status()
        text = (r.json() or {}).get("response", "").strip()
        return text or None
    except Exception:
        return None


def answer(db, user, question: str, tender_id: Optional[str] = None, lang: str = "en",
           use_model: bool = True) -> Dict[str, Any]:
    from app.api.routes import _account_tenders, _checklist_items, _score_for
    from app.models import EligibilityResult, TenderTask
    from app.reminders import for_tenders
    tenders = _account_tenders(db, user)
    by_id = {t.id: t for t in _account_tenders(db, user, include_demo=True)}  # the route checked read access
    tender = by_id.get(tender_id) if tender_id else None
    kind = intent_of(question)
    lines: List[Dict[str, Any]] = []
    sources: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []

    def link(tid, label=None):
        links.append({"href": f"/tenders/{tid}", "label": label or tid})

    if kind == "overdue":
        rs = [r for r in for_tenders(db, tenders) if r["kind"] in ("task-overdue", "task-due", "deadline-passed")]
        if not rs:
            lines.append(L("Nothing is overdue."))
        for r in rs[:10]:
            lines.append(L("{tender}: " + r["key"], tender=r["tender_id"], **r["vars"]))
            link(r["tender_id"])
    elif kind == "deadlines":
        rs = for_tenders(db, tenders)
        dated = sorted([t for t in tenders if t.submission_deadline], key=lambda t: t.submission_deadline)
        if not dated and not rs:
            lines.append(L("No submission deadlines are set yet — set them on each tender page."))
        for r in [r for r in rs if r["kind"].startswith("task")][:5]:
            lines.append(L("{tender}: " + r["key"], tender=r["tender_id"], **r["vars"]))
        for t in dated[:10]:
            lines.append(L("{tender}: submission {date}", tender=t.id, date=t.submission_deadline.date().isoformat()))
            link(t.id)
    elif kind == "bulk":
        lines.append(L("Material quantities across tenders are not tracked yet, so bulk-purchase grouping is not available."))
    elif kind in ("suitable", "why", "certificates", "checklist", "conflicts", "similar", "client") and tender is None:
        if kind == "client":
            from app.similarity import profile
            groups: Dict[str, List[str]] = {}
            for t in tenders:
                p = profile(db, t)
                if p["client"]:
                    groups.setdefault(p["client"], []).append(t.id)
            for c, ids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
                lines.append(L("{client}: {n} tender(s) — {ids}", client=c, n=len(ids), ids=", ".join(ids[:6])))
            if not groups:
                lines.append(L("No client is recorded on your tenders yet."))
        else:
            lines.append(L("Open a tender and ask again — this question is about one tender."))
    elif kind in ("suitable", "why"):
        sc = _score_for(db, tender.id, user)
        el = db.query(EligibilityResult).filter(EligibilityResult.tender_id == tender.id).first()
        band = {"GO": "Go|band", "REVIEW": "Review|band", "NO_GO": "No-Go|band"}.get(sc.get("band"), "not scored")
        lines.append(L("Go/No-Go score: {score}/100 — {band}.", score=sc.get("score") if sc.get("score") is not None else "—",
                       band=band))
        if sc.get("hard_fail"):
            lines.append(L("No-Go regardless of the score: {reason}", reason=sc["hard_fail"]))
        for f in sc.get("factors") or []:
            lines.append(L("{label}: {value}", label=f["label"],
                           value=(f"{f['value']}%" if f["counted"] else "not counted"))
                         | {"reason": {"key": f.get("reason_key"), "vars": f.get("reason_vars") or {}}})
        if el is not None:
            for c in el.checks or []:
                if c.get("result") == "FAIL":
                    lines.append(L("Eligibility: {label} not met — " + (c.get("detail_key") or c.get("detail") or ""),
                                   label=c["label"], **(c.get("detail_vars") or {})))
                    if c.get("evidence"):
                        sources.append(dict(c["evidence"], tender_id=tender.id))
        link(tender.id)
    elif kind == "certificates":
        from app.certifications import tender_certifications
        from app.eligibility import capability_dict, capability_for
        certs = tender_certifications(tender.id, capability_dict(capability_for(db, tender)), {})
        if not certs:
            lines.append(L("The tender asks for no specific certificates or approvals."))
        for c in certs:
            lines.append(L("{name} — required from {who}: {status}", name=c["name"], who=_WHO[c["who"]],
                           status=_STATUS[c["status"]]))
            if c["evidence"]:
                sources.append(dict(c["evidence"][0], tender_id=tender.id))
        links.append({"href": f"/tenders/{tender.id}/pack", "label": "Decision pack"})
    elif kind == "checklist":
        items = _checklist_items(db, tender.id)
        lines.append(L("{r} of {n} ready, {x} not applicable.", r=sum(i["status"] == "READY" for i in items), n=len(items),
                       x=sum(i["status"] == "NOT_APPLICABLE" for i in items)))
        for i in [i for i in items if i["status"] == "TODO"][:8]:
            lines.append(L("To do: {item}", item=i["title"]))
            sources.append({"tender_id": tender.id, "file": i["file"], "page": i["page"], "quote": i["quote"][:200]})
    elif kind == "conflicts":
        from app.conflicts import tender_conflicts
        cs = tender_conflicts(tender.id)
        if not cs:
            lines.append(L("No contradictions found in the tender documents."))
        for c in cs:
            lines.append(L("{label}: {values}", label=c["label"], values=" / ".join(v["value"] for v in c["values"])))
            sources.extend(dict(v, tender_id=tender.id) for v in c["values"][:2])
    elif kind in ("similar", "client"):
        from app.similarity import for_tender
        res = for_tender(db, tender, user)
        if kind == "client":
            if res["client_history"]:
                lines.append(L("You took part in {n} earlier tender(s) with {client}.", n=len(res["client_history"]),
                               client=res["client"]))
                for h in res["client_history"]:
                    link(h["id"], f"{h['id']} {h.get('outcome') or ''}".strip())
            else:
                lines.append(L("No earlier tender with {client} is recorded.", client=res["client"] or "this client"))
        else:
            if not res["similar"]:
                lines.append(L("No similar earlier tender found."))
            for s in res["similar"]:
                lines.append(L("{id} ({score}% similar) — recommendation {decision}, outcome {outcome}", id=s["id"],
                               score=s["score"], decision=s.get("decision") or "—", outcome=s.get("outcome") or "—"))
                link(s["id"])
    else:
        ids = [tender.id] if tender else list(by_id)
        sources = _search(db, ids, question)
        if not sources:
            lines.append(L("I could not find this in your tenders. Try other words, or open the tender and ask there."))
        else:
            text = _llm_answer(question, sources, lang) if use_model else None
            if text:
                lines.append({"text": text})
            else:
                lines.append(L("These parts of the tender match your question:"))
    return {"intent": kind, "lines": lines, "sources": sources[:8], "links": links[:10]}
