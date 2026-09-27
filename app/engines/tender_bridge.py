"""Stage 5C — decision bridge for uploaded tenders.

Before this, the decision engine (status.py / decision.py) only ever saw the
seeded Sarai rows: requirements extracted from uploaded tenders lived in
TenderAnalysis JSON and never reached Requirement/Evidence/EvidenceMatch, so
no uploaded tender could get a BID/REVIEW/NO_BID decision.

This module:
1. sync_requirements(): copies the latest analysis requirements into
   Requirement rows (ids "<tender_id>::<REQ-xxx>"). Bidder-qualification
   categories are mandatory unless the model explicitly said optional;
   specification/schedule/submission items are informational (never block).
   UNKNOWN is quarantined (not synced) per the two-stage schema contract.
2. Company documents: uploaded once, reused for every tender.
3. evaluate_tender(): for each mandatory requirement, picks the most relevant
   company-document paragraphs (lexical) and asks the existing HybridMatcher
   (deterministic rules + LLM + post-validation). PASS/FAIL/REVIEW become
   Evidence + EvidenceMatch rows with file/page/quote provenance; MISSING
   stays missing. The final decision is computed by the unchanged engine.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (Company, CompanyDocument, Decision, Evidence, EvidenceMatch,
                        MissingEvidence, Requirement, TenderAnalysis)

COMPANY_ID = "OUR_COMPANY"

# Bidder capability -> a proven contradiction here is a hard gate (NO_BID).
HARD_GATE_CATEGORIES = {"LEGAL", "EXPERIENCE", "FINANCIAL", "EQUIPMENT", "PERSONNEL", "QA_QC"}
# Also require company evidence, but a gap is REVIEW, never a hard gate.
QUALIFICATION_CATEGORIES = HARD_GATE_CATEGORIES | {"COMMERCIAL", "HSE", "SUBCONTRACTOR"}
# Shown with provenance but never block the decision.
INFORMATIONAL_CATEGORIES = {"TECHNICAL", "SCHEDULE", "SUBMISSION"}

TOP_K_PARAGRAPHS = 2
MIN_PARAGRAPH_CHARS = 40

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def req_prefix(tender_id: str) -> str:
    return f"{tender_id}::"


# ---------------------------------------------------------------- requirements
def _latest_analysis(db: Session, tender_id: str) -> Optional[TenderAnalysis]:
    return (db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id)
            .order_by(TenderAnalysis.created_at.desc()).first())


def _clear_bridge_rows(db: Session, tender_id: str, keep_requirements: bool = False) -> None:
    prefix = req_prefix(tender_id)
    req_ids = [r.id for r in db.query(Requirement.id).filter(Requirement.id.like(f"{prefix}%"))]
    if req_ids:
        ev_ids = [m.evidence_id for m in db.query(EvidenceMatch).filter(EvidenceMatch.requirement_id.in_(req_ids))]
        db.query(EvidenceMatch).filter(EvidenceMatch.requirement_id.in_(req_ids)).delete(synchronize_session=False)
        if ev_ids:
            db.query(Evidence).filter(Evidence.id.in_(ev_ids)).delete(synchronize_session=False)
        db.query(MissingEvidence).filter(MissingEvidence.requirement_id.in_(req_ids)).delete(synchronize_session=False)
        if not keep_requirements:
            db.query(Requirement).filter(Requirement.id.in_(req_ids)).delete(synchronize_session=False)
    # Old decisions were computed from rows that no longer exist.
    db.query(Decision).filter(Decision.tender_id == tender_id, Decision.is_override.is_(False)).delete(
        synchronize_session=False)
    db.commit()


def sync_requirements(db: Session, tender_id: str) -> Dict[str, int]:
    """Replace this tender's bridged Requirement rows from its latest analysis."""
    if tender_id == "SA-2018-HV2":  # seeded demo keeps its curated rows
        return {"synced": 0, "skipped_unknown": 0, "mandatory": 0}
    analysis = _latest_analysis(db, tender_id)
    _clear_bridge_rows(db, tender_id)
    if analysis is None:
        return {"synced": 0, "skipped_unknown": 0, "mandatory": 0}
    seen = set()
    synced = skipped = mandatory_n = 0
    for r in analysis.requirements or []:
        cat = str(r.get("category") or "UNKNOWN").upper()
        text = (r.get("summary") or r.get("requirement") or "").strip()
        if cat == "UNKNOWN" or not text:
            skipped += 1
            continue
        key = (cat, text.lower())
        if key in seen:
            continue
        seen.add(key)
        model_mandatory = r.get("mandatory")
        if cat in QUALIFICATION_CATEGORIES:
            mandatory = model_mandatory is not False  # null -> conservative: needs evidence
        else:
            mandatory = False
        mandatory_n += int(mandatory)
        page = r.get("page_number")
        db.add(Requirement(
            id=f"{req_prefix(tender_id)}{r.get('requirement_id') or r.get('id') or uuid.uuid4().hex[:6]}",
            tender_id=tender_id,
            category=cat,
            requirement=text,
            mandatory=mandatory,
            requirement_type=("HARD_GATE" if mandatory and cat in HARD_GATE_CATEGORIES
                              else "QUALIFICATION" if mandatory else "INFORMATIONAL"),
            evidence_required=[],
            evaluation_logic={
                "MISSING_EVIDENCE": "No company evidence found yet for this requirement.",
                "PASS": "A company document supports this requirement (see evidence quote and page).",
                "FAIL": "A company document explicitly contradicts this requirement (see evidence quote).",
                "REVIEW": "Company evidence is partial or ambiguous - human review required.",
                "source_quote": (r.get("source_text") or "")[:400],
            },
            source_document=r.get("source_document") or "",
            page_or_section=f"p.{page}" if page else "",
            applicable_entity="ANY",
        ))
        synced += 1
    db.commit()
    return {"synced": synced, "skipped_unknown": skipped, "mandatory": mandatory_n}


# ----------------------------------------------------------- company documents
def ensure_company(db: Session) -> Company:
    c = db.query(Company).filter(Company.id == COMPANY_ID).first()
    if c is None:
        c = Company(id=COMPANY_ID, name="Our Company", country="", role="BIDDER")
        db.add(c)
        db.commit()
    return c


def extract_pages(path: Path) -> List[Dict[str, Any]]:
    """Same extractors as tender processing (incl. scanned images, ZIP/RAR,
    CAD, .bak). Returns [{page_number, text, document}] across inner files."""
    from app.pipeline.file_extractors import extract_any
    from evaluation.run_real_benchmark import extract_pdf_text
    out = []
    for inner_name, res in extract_any(path, path.name, lambda p, h: extract_pdf_text(str(p))):
        for i, pg in enumerate(res.get("pages") or []):
            n = pg.get("page_number") or pg.get("source_page_number") or (i + 1)
            out.append({"page_number": int(n), "text": pg.get("text") or "",
                        "inner": inner_name if inner_name != path.name else ""})
    return out


_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _paragraphs(doc_title: str, pages: List[Dict[str, Any]], window: int = 350) -> List[Dict[str, Any]]:
    """Split each page into short passages that never cross a heading or bullet.

    Each passage carries its section heading (helps relevance) and its page
    (provenance). Short consecutive plain lines are packed up to ~window chars.
    """
    paras = []
    for pg in pages:
        heading = ""
        buf: List[str] = []

        def flush():
            if buf:
                text = " ".join(buf)
                if len(text) >= MIN_PARAGRAPH_CHARS // 2:
                    paras.append({"document": f"{doc_title}/{pg['inner'].split('/', 1)[-1]}" if pg.get("inner") else doc_title,
                              "page": pg["page_number"], "text": text, "heading": heading})
                buf.clear()

        for raw in (pg["text"] or "").splitlines():
            line = " ".join(raw.split())
            if not line:
                flush()
                continue
            if line.startswith("#"):
                flush()
                heading = line.lstrip("#").strip()
                continue
            if _BULLET.match(line) or sum(len(b) for b in buf) + len(line) > window:
                flush()
            buf.append(line)
        flush()
    return paras


def company_paragraphs(db: Session) -> List[Dict[str, Any]]:
    out = []
    for d in db.query(CompanyDocument).filter(CompanyDocument.company_id == COMPANY_ID).all():
        p = Path(d.source_path or "")
        if p.is_file():
            out.extend(_paragraphs(d.title or p.name, extract_pages(p)))
    return out


# ------------------------------------------------------------------ evaluation
def _tokens(text: str) -> set:
    from app.matchers.hybrid_matcher import _tokens as hyb_tokens
    return {t for t in hyb_tokens(text) if len(t) > 3}


def _top_paragraphs(req_text: str, paras: List[Dict[str, Any]], k: int) -> List[Tuple[float, Dict[str, Any]]]:
    rt = _tokens(req_text)
    if not rt:
        return []
    scored = []
    for p in paras:
        pt = p.setdefault("_tok", _tokens(f"{p.get('heading', '')} {p['text']}"))
        overlap = len(rt & pt)
        if overlap:
            scored.append((overlap / len(rt), p))
    scored.sort(key=lambda x: -x[0])
    return scored[:k]


def matcher_model() -> str:
    """Same model as the rest of the pipeline unless TENDERMIND_MATCHER_MODEL says otherwise.
    (OllamaMatcher's own default is qwen3:4b with thinking on: ~90s per call and it
    evicts the normalization model from memory on every switch.)"""
    import os
    return (os.environ.get("TENDERMIND_MATCHER_MODEL") or os.environ.get("OLLAMA_MODEL")
            or "qwen2.5:3b").strip()


JUDGE_SYSTEM = """You check whether ONE passage from a bidder's company document satisfies ONE tender requirement.
Return ONLY JSON: {"verdict": "PASS|FAIL|REVIEW|MISSING", "confidence": 0.0, "quote": "..."}
- PASS: the passage explicitly states the company has or meets what the requirement asks for.
- FAIL: the passage explicitly states a fact that means the company does NOT meet it (for example fewer years, a lower amount, a lower category than required).
- REVIEW: the passage is related but only partly answers it, or the required level cannot be confirmed.
- MISSING: the passage is about something else.
- quote: copy, word for word, the sentence from the passage that justifies PASS, FAIL or REVIEW. Empty for MISSING.
Do not use outside knowledge. Do not invent facts."""


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


class EvidenceJudge:
    """LLM judge for one (requirement, company passage) pair, with grounding rules
    enforced in code: PASS/FAIL/REVIEW need a verbatim quote from the passage, and
    FAIL needs high confidence, otherwise the pair is downgraded to REVIEW. The model
    can therefore never turn a guess into a NO_BID or an invented quote into a PASS."""
    name = "evidence-judge"
    FAIL_MIN_CONFIDENCE = 0.8

    def __init__(self, model: str, timeout: int = 60, transport=None):
        self.model = model
        self.timeout = timeout
        self._transport = transport or self._ollama

    def _ollama(self, system: str, user: str) -> str:
        import requests
        from app.pipeline.config import load_config
        payload = {"model": self.model, "stream": False, "format": "json",
                   "options": {"temperature": 0},
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.model.startswith("qwen3"):
            payload["think"] = False
        r = requests.post(f"{load_config().ollama_base_url}/api/chat", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return (r.json().get("message") or {}).get("content", "")

    def match(self, inp):
        import json as _json
        from app.matchers.base import MatcherOutput
        user = (f'Requirement ({inp.requirement_category}):\n"""{inp.requirement_text}"""\n\n'
                f'Company passage ({inp.source_document} {inp.page_or_section}):\n"""{inp.evidence_fact}"""')
        try:
            data = _json.loads(self._transport(JUDGE_SYSTEM, user) or "{}")
        except Exception as e:
            return MatcherOutput(support=None, contradiction=False, applicability="REVIEW", confidence=0.0,
                                 missing_facts=[f"judge error: {type(e).__name__}"],
                                 reason=f"Evidence judge failed ({type(e).__name__}) - REVIEW, not guessed")
        verdict = str(data.get("verdict", "")).upper()
        if verdict not in ("PASS", "FAIL", "REVIEW", "MISSING"):
            verdict = "REVIEW"
        try:
            conf = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        except (TypeError, ValueError):
            conf = 0.0
        quote = str(data.get("quote") or "").strip()
        grounded = len(_norm(quote)) >= 12 and _norm(quote) in _norm(inp.evidence_fact)
        note = ""
        if verdict in ("PASS", "FAIL") and not grounded:
            verdict, note = "REVIEW", " (downgraded: quote not found verbatim in the company document)"
        if verdict == "FAIL" and conf < self.FAIL_MIN_CONFIDENCE:
            verdict, note = "REVIEW", f" (downgraded: FAIL confidence {conf:.2f} < {self.FAIL_MIN_CONFIDENCE})"
        facts = [quote] if grounded and quote else []
        return MatcherOutput(
            support=True if verdict == "PASS" else False if verdict in ("FAIL", "MISSING") else None,
            contradiction=verdict == "FAIL",
            supporting_facts=facts if verdict == "PASS" else [],
            contradictory_facts=facts if verdict == "FAIL" else [],
            missing_facts=[] if verdict != "MISSING" else ["passage does not address the requirement"],
            applicability=verdict, confidence=conf,
            reason=f"{verdict} by evidence judge ({self.model}, confidence {conf:.2f}){note}")


def _default_matcher():
    import os
    from app.matchers.hybrid_matcher import HybridMatcher
    try:
        timeout = int(os.environ.get("TENDERMIND_MATCHER_TIMEOUT", "60"))
    except ValueError:
        timeout = 60
    # Hybrid keeps the shared deterministic pre/post rules and the relevance gate;
    # the judge replaces the minimal 2-field prompt with a grounded verdict + quote.
    return HybridMatcher(llm_matcher=EvidenceJudge(matcher_model(), timeout=timeout))


def evaluate_tender(db: Session, tender_id: str, matcher=None,
                    progress: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Match mandatory requirements against company documents, then decide."""
    from app.engines.decision import get_or_create_decision
    from app.matchers.base import MatcherInput

    if not db.query(Requirement).filter(Requirement.id.like(f"{req_prefix(tender_id)}%")).first():
        sync_requirements(db, tender_id)
    _clear_bridge_rows(db, tender_id, keep_requirements=True)
    ensure_company(db)
    paras = company_paragraphs(db)
    reqs = (db.query(Requirement).filter(Requirement.id.like(f"{req_prefix(tender_id)}%"),
                                         Requirement.mandatory.is_(True)).all())
    matcher = matcher or _default_matcher()
    counts = {"requirements": len(reqs), "paragraphs": len(paras), "PASS": 0, "FAIL": 0,
              "REVIEW": 0, "MISSING": 0, "llm_calls": 0}
    if progress is not None:
        progress.update({"total": len(reqs), "done": 0})
    rank = {"PASS": 3, "FAIL": 2, "REVIEW": 1, "MISSING": 0}
    snapshot = [(r.id, r.requirement, r.category, r.requirement_type) for r in reqs]

    def _best_for(item):
        rid, text, cat, rtype = item
        best = None
        errors = []
        for _score, para in _top_paragraphs(text, paras, TOP_K_PARAGRAPHS):
            inp = MatcherInput(
                requirement_id=rid, requirement_text=text,
                requirement_category=cat, requirement_type=rtype or "UNKNOWN",
                mandatory=True, applicable_entity="ANY",
                evidence_id=f"{para['document']}#p{para['page']}", evidence_fact=para["text"],
                current_tender_id=tender_id, source_document=para["document"],
                page_or_section=f"p.{para['page']}")
            try:
                out = matcher.match(inp)
            except Exception as e:  # one bad pair must not stop the evaluation
                errors.append(f"{rid}: {type(e).__name__}")
                continue
            if best is None or rank[out.applicability] > rank[best[0].applicability]:
                best = (out, para)
            if out.applicability == "PASS":
                break
        if progress is not None:
            progress["done"] = progress.get("done", 0) + 1
        return best, errors

    # Model calls in parallel (same worker setting as processing); DB writes stay here.
    from app.pipeline.capability_tiers import load_worker_config
    wc = load_worker_config()
    workers = wc.max_workers if wc.enabled else 1
    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_best_for, snapshot))
    else:
        results = [_best_for(it) for it in snapshot]

    for req, (best, errors) in zip(reqs, results):
        if errors:
            counts.setdefault("errors", []).extend(errors)
        counts["llm_calls"] = getattr(matcher, "llm_calls", counts["llm_calls"])
        verdict = best[0].applicability if best else "MISSING"
        counts[verdict] += 1
        if best and verdict in ("PASS", "FAIL", "REVIEW"):
            out, para = best
            ev_id = f"EV-{uuid.uuid4().hex[:8].upper()}"
            facts = out.supporting_facts if verdict == "PASS" else out.contradictory_facts or out.missing_facts
            db.add(Evidence(
                id=ev_id, company_id=COMPANY_ID, requirement_id=req.id,
                evidence_type="COMPANY_DOCUMENT",
                fact=("; ".join(facts) if facts else para["text"][:300]),
                status=verdict, source_document=para["document"], page_or_section=f"p.{para['page']}",
                source_quote=(facts[0] if facts else para["text"])[:600],
                extraction_confidence=("HIGH" if out.confidence >= 0.8 else "MEDIUM" if out.confidence >= 0.5 else "LOW"),
                notes=out.reason[:1000], applicable_entity="ANY", tender_source_id=None, reusable=True,
                created_at=datetime.utcnow()))
            db.add(EvidenceMatch(id=f"EM-{uuid.uuid4().hex[:8].upper()}", requirement_id=req.id,
                                 evidence_id=ev_id, match_confidence=str(round(out.confidence, 2)),
                                 notes=out.reason[:500]))
            db.commit()
    dec, _ = get_or_create_decision(db, tender_id)
    counts["decision"] = dec.decision
    counts["confidence"] = dec.confidence
    return counts


# ---------------------------------------------------------- background runner
def start_evaluation(tender_id: str) -> Dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(tender_id)
        if job and job.get("status") == "RUNNING":
            return dict(job)
        job = {"tender_id": tender_id, "status": "RUNNING", "started_at": time.time(),
               "total": 0, "done": 0, "result": None, "error": None}
        _jobs[tender_id] = job

    def _run():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            job["result"] = evaluate_tender(db, tender_id, progress=job)
            job["status"] = "COMPLETED"
        except Exception as e:
            job["status"] = "FAILED"
            job["error"] = f"{type(e).__name__}: {e}"[:500]
        finally:
            job["finished_at"] = time.time()
            db.close()

    threading.Thread(target=_run, daemon=True).start()
    return dict(job)


def evaluation_status(tender_id: str) -> Dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(tender_id)
        return dict(job) if job else {"tender_id": tender_id, "status": "NOT_STARTED"}
