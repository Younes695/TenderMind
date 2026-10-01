"""Stage 5H — checkpoints/resume, review items + Q&A, notifications, news."""
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _tender_with_files(tmp_path, monkeypatch, n=2, prefix="T5H"):
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    from app.database import SessionLocal, init_db
    from app.models import Tender, TenderDocument
    init_db()
    tid = f"{prefix}-{uuid.uuid4().hex[:6]}"
    (tmp_path / tid).mkdir()
    db = SessionLocal()
    try:
        db.add(Tender(id=tid, title="t"))
        for i in range(n):
            f = tmp_path / tid / f"doc{i}.txt"
            f.write_text(f"Clause {i}: the contractor shall submit a performance bond TBD. " * 3, encoding="utf-8")
            db.add(TenderDocument(id=f"D-{tid}-{i}", tender_id=tid, title=f.name, doc_type="TXT",
                                  source_path=str(f), original_filename=f.name))
        db.commit()
    finally:
        db.close()
    return tid


# ------------------------------------------------------------ checkpoints
def test_retry_reuses_extraction_checkpoint(tmp_path, monkeypatch):
    from app import processing
    from app.database import SessionLocal
    from app.pipeline import file_extractors
    tid = _tender_with_files(tmp_path, monkeypatch)
    calls = []
    real = file_extractors.extract_any
    monkeypatch.setattr(file_extractors, "extract_any", lambda *a, **k: calls.append(a[1]) or real(*a, **k))
    db = SessionLocal()
    j1 = processing.create_processing_job(db, tid).id
    db.close()
    processing.process_tender(tid, j1)
    assert sorted(calls) == ["doc0.txt", "doc1.txt"]
    db = SessionLocal()
    j2 = processing.create_processing_job(db, tid).id
    db.close()
    processing.process_tender(tid, j2)
    assert sorted(calls) == ["doc0.txt", "doc1.txt"]  # second run read nothing again


def test_ai_cache_roundtrip_survives_torn_line(tmp_path, monkeypatch):
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    from app.pipeline.checkpoint import AiCache
    from app.pipeline.contracts import LLMNormalizationResult
    c = AiCache("T-AI", "m", "p")
    c.put("text one", LLMNormalizationResult(summary="s", category="COMMERCIAL", mandatory=True))
    with open(c.path, "a", encoding="utf-8") as fh:
        fh.write('{"k": "torn')  # crash mid-write
    c2 = AiCache("T-AI", "m", "p")
    assert c2.get("text one")["category"] == "COMMERCIAL" and len(c2) == 1
    assert AiCache("T-AI", "other-model", "p").get("text one") is None


def test_runner_skips_model_for_cached_candidates(monkeypatch, tmp_path):
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    from app.pipeline import intelligence_runner as ir
    from app.pipeline.checkpoint import AiCache
    from app.pipeline.contracts import SourceText
    src = [SourceText(source_document="a.txt", page_number=1,
                      text=("1. The Contractor shall submit a tender security of EGP 500,000 valid for 180 days. "
                            "2. The Bidder must provide audited financial statements for the last three years. "
                            "3. The Contractor shall have completed at least two similar 220 kV substations. ") * 3)]
    asked = []

    class R:
        def normalize(self, task, cand):
            asked.append(cand.candidate_id)
            from app.pipeline.contracts import LLMNormalizationResult
            return LLMNormalizationResult(summary="Tender security", category="COMMERCIAL", mandatory=True), "ok", 0.1, "{}"
    cache = AiCache("T-R", "m", "p")
    ir.run_intelligence("T-R", src, router=R(), ai_cache=cache)
    first = len(asked)
    assert first >= 1 and len(cache) >= 1
    intel, telem = ir.run_intelligence("T-R", src, router=R(), ai_cache=AiCache("T-R", "m", "p"))
    assert len(asked) == first and telem.ai_cache_hits == first and intel["requirements"]


def test_interrupted_job_is_resumed_automatically(tmp_path, monkeypatch):
    from app import processing
    from app.database import SessionLocal
    from app.models import ProcessingJob
    tid = _tender_with_files(tmp_path, monkeypatch, n=1)
    db = SessionLocal()
    job = processing.create_processing_job(db, tid)
    job.status = "PROCESSING"
    db.commit()
    old = job.id
    db.close()
    started = []
    monkeypatch.setenv("TENDERMIND_AUTO_RESUME", "1")
    monkeypatch.setattr(processing.threading, "Thread",
                        lambda target, args, **k: type("T", (), {"start": lambda s: started.append(args)})())
    new_ids = processing.resume_interrupted(reason="test")
    assert len(new_ids) == 1 and started == [(tid, new_ids[0])]
    db = SessionLocal()
    try:
        o = db.query(ProcessingJob).filter(ProcessingJob.id == old).first()
        assert o.status == "FAILED" and "resumed automatically" in o.last_error
    finally:
        db.close()
    # a job with a live worker is left alone
    processing.ACTIVE_JOBS.add(new_ids[0])
    try:
        db = SessionLocal()
        j = db.query(ProcessingJob).filter(ProcessingJob.id == new_ids[0]).first()
        j.status = "PROCESSING"; db.commit(); db.close()
        assert processing.resume_interrupted(reason="test") == []
    finally:
        processing.ACTIVE_JOBS.discard(new_ids[0])


def test_resume_gives_up_after_repeated_crashes(tmp_path, monkeypatch):
    from app import processing
    from app.database import SessionLocal
    from app.models import ProcessingJob
    tid = _tender_with_files(tmp_path, monkeypatch, n=1)
    monkeypatch.setenv("TENDERMIND_AUTO_RESUME", "1")
    monkeypatch.setattr(processing.threading, "Thread",
                        lambda target, args, **k: type("T", (), {"start": lambda s: None})())
    resumed = 0
    for _ in range(5):
        db = SessionLocal()
        j = db.query(ProcessingJob).filter(ProcessingJob.tender_id == tid,
                                           ProcessingJob.status.in_(["QUEUED", "PROCESSING"])).first()
        if j is None:
            j = processing.create_processing_job(db, tid)
        j.status = "PROCESSING"; db.commit(); db.close()
        new = processing.resume_interrupted(reason="test")
        db = SessionLocal()
        resumed += db.query(ProcessingJob).filter(ProcessingJob.id.in_(new), ProcessingJob.tender_id == tid).count()
        db.close()
    assert resumed == 3


# ------------------------------------------------------------ issues / Q&A / notifications
def _analysis(db, tid, **df):
    from app.models import TenderAnalysis
    db.add(TenderAnalysis(id=f"AN-{uuid.uuid4().hex[:8]}", tender_id=tid, analysis_version="t", status="COMPLETED",
                          tender={}, requirements=[{"requirement_id": "R1", "summary": "Something odd", "category": "UNKNOWN",
                                                    "mandatory": True, "source_document": "a.pdf", "page_number": 3,
                                                    "source_text": "Bond amount TBD"}],
                          evidence=[], documents=[{"filename": "b.rar", "extraction_status": "UNSUPPORTED"}],
                          deadlines=[], commercial=None, risks=[], derived_features=df))
    db.commit()


def test_issues_built_from_analysis_and_idempotent(tmp_path, monkeypatch):
    from app.database import SessionLocal
    from app.issues import sync_issues
    from app.models import TenderIssue
    tid = _tender_with_files(tmp_path, monkeypatch, n=0)
    db = SessionLocal()
    try:
        _analysis(db, tid,
                  gaps=[{"gap_id": "GAP-001", "kind": "referenced-form-absent",
                         "description": "ANNEX X referenced but no matching document in package",
                         "evidence": ["a.pdf#p2"]}],
                  ambiguities=[{"ambiguity_type": "missing-value", "description": "Bond amount TBD",
                                "source_document": "a.pdf", "pages": [4], "raw_signals": [{"requirement_id": "R1"}]}],
                  page_quality=[{"document": "a.pdf", "page": 7, "confidence": 0.3, "chars": 12},
                                {"document": "a.pdf", "page": 9, "confidence": 0.4, "chars": 40}])
        assert sync_issues(db, tid)["added"] == 5
        kinds = {(i.category, i.kind) for i in db.query(TenderIssue).filter(TenderIssue.tender_id == tid)}
        assert ("missing", "referenced-form-absent") in kinds and ("missing", "unsupported-type") in kinds
        assert ("question", "missing-value") in kinds and ("question", "unreadable-pages") in kinds
        assert ("question", "unclassified-requirement") in kinds
        i = db.query(TenderIssue).filter(TenderIssue.tender_id == tid, TenderIssue.kind == "missing-value").first()
        i.status = "RESOLVED"; db.commit()
        assert sync_issues(db, tid)["added"] == 0  # no duplicates, resolved stays resolved
        assert db.query(TenderIssue).filter(TenderIssue.id == i.id).first().status == "RESOLVED"
    finally:
        db.close()


def test_issue_api_answer_resolve_and_notifications(tmp_path, monkeypatch):
    from app.database import SessionLocal
    from app.main import app
    tid = _tender_with_files(tmp_path, monkeypatch, n=0)
    db = SessionLocal()
    _analysis(db, tid, gaps=[{"kind": "missing-file", "description": "x.pdf listed but not found",
                              "evidence": ["x.pdf"]}])
    db.close()
    c = TestClient(app)
    r = c.get(f"/api/tenders/{tid}/issues", params={"category": "question"}).json()
    assert r["count"] == 1 and r["issues"][0]["kind"] == "unclassified-requirement"
    qid = r["issues"][0]["id"]
    up = c.patch(f"/api/issues/{qid}", json={"answer": "Client confirmed: HSE requirement", "status": "RESOLVED"})
    assert up.status_code == 200 and up.json()["status"] == "RESOLVED" and up.json()["answer"].startswith("Client")
    assert c.patch(f"/api/issues/{qid}", json={"status": "DONE"}).status_code == 400
    notes = c.get("/api/notifications").json()
    mine = [n for n in notes["notifications"] if n["tender_id"] == tid]
    assert {n["kind"] for n in mine} == {"missing-file", "unsupported-type"}
    assert all(n["category"] == "missing" and n["status"] == "OPEN" for n in mine)


def test_other_account_cannot_touch_issues(tmp_path, monkeypatch):
    monkeypatch.setenv("TENDERMIND_AUTH_ENABLED", "1")
    from app.main import app
    from app.database import SessionLocal
    from app.models import Tender
    alice = TestClient(app, base_url="https://testserver"); bob = TestClient(app, base_url="https://testserver")
    for cl in (alice, bob):
        assert cl.post("/api/auth/signup", json={"email": f"u-{uuid.uuid4().hex[:6]}@t.test",
                                                 "password": "Tender2026"}).status_code == 200
    tid = f"ISS-{uuid.uuid4().hex[:6]}"
    assert alice.post("/api/tenders", json={"id": tid, "title": "p"}).status_code == 200
    db = SessionLocal()
    _analysis(db, tid)
    db.close()
    iid = alice.get(f"/api/tenders/{tid}/issues").json()["issues"][0]["id"]
    assert bob.get(f"/api/tenders/{tid}/issues").status_code == 404
    assert bob.patch(f"/api/issues/{iid}", json={"status": "RESOLVED"}).status_code == 404
    assert all(n["tender_id"] != tid for n in bob.get("/api/notifications").json()["notifications"])


# ------------------------------------------------------------ news
def test_world_bank_parsing_keeps_no_personal_data():
    from app import news

    class Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"procnotices": [{"id": "OP1", "notice_type": "Invitation for Bids", "noticedate": "24-Sep-2026",
                                     "submission_deadline_date": "2026-11-23T00:00:00Z",
                                     "project_ctry_name": "Egypt, Arab Republic of",
                                     "bid_description": "Supply of 220 kV GIS substation", "project_name": "Grid",
                                     "contact_email": "person@example.org", "contact_name": "A Person",
                                     "contact_organization": "EETC"}]}

    class S:
        def get(self, *a, **k): return Resp()
    items = news.fetch_world_bank(countries=["EG"], session=S())
    assert len(items) == 1 and items[0]["deadline_at"].year == 2026
    assert "person@example.org" not in json.dumps(items, default=str) and "A Person" not in json.dumps(items, default=str)


def test_rss_only_from_allowed_https_hosts(monkeypatch):
    from app import news
    monkeypatch.setenv("TENDERMIND_NEWS_ALLOWED_HOSTS", "trusted.gov.eg")
    fetched = []

    class S:
        def get(self, url, **k):
            fetched.append(url)
            raise RuntimeError("no network in tests")
    news.fetch_rss(["http://trusted.gov.eg/feed", "https://evil.example/feed", "https://trusted.gov.eg/feed"], session=S())
    assert fetched == ["https://trusted.gov.eg/feed"]


def test_news_store_dedupes_and_marks_relevance(tmp_path, monkeypatch):
    from app import news
    from app.database import SessionLocal, init_db
    from app.models import NewsItem
    init_db()
    ext = uuid.uuid4().hex[:8]
    base = {"source": "World Bank", "description": "", "country": "Egypt", "notice_type": "Invitation for Bids",
            "organization": None, "url": None, "published_at": None, "deadline_at": None}
    db = SessionLocal()
    try:
        r1 = news.store(db, [{**base, "external_id": ext, "title": "Construction of 132 kV substation"},
                             {**base, "external_id": ext + "b", "title": "Office furniture"}])
        r2 = news.store(db, [{**base, "external_id": ext, "title": "Construction of 132 kV substation"}])
        assert r1["added"] == 2 and r2 == {"added": 0, "updated": 1}
        rows = {n.external_id: n.relevant for n in db.query(NewsItem).filter(NewsItem.external_id.like(f"{ext}%"))}
        assert rows == {ext: True, ext + "b": False}
    finally:
        db.close()


def test_analysis_response_carries_open_review_counts(tmp_path, monkeypatch):
    from app.database import SessionLocal
    from app.main import app
    from app.models import ProcessingJob
    tid = _tender_with_files(tmp_path, monkeypatch, n=0)
    db = SessionLocal()
    _analysis(db, tid, gaps=[{"kind": "missing-file", "description": "y.pdf listed but not found", "evidence": ["y.pdf"]}])
    db.add(ProcessingJob(id=f"JOB-{uuid.uuid4().hex[:8]}", tender_id=tid, status="COMPLETED"))
    db.commit(); db.close()
    r = TestClient(app).get(f"/api/tenders/{tid}/analysis").json()
    assert r["review"] == {"missing_open": 2, "question_open": 1}


def test_escalation_runs_as_one_batch_after_the_primary(monkeypatch, tmp_path):
    """Candidate-by-candidate escalation swapped the two models on a 4 GB GPU for
    almost every call. The second model must run once, after the primary pass."""
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    from app.pipeline import intelligence_runner as ir
    from app.pipeline.ai_router import EscalatingProvider, QwenMinimalContractProvider, Router, AITask
    from app.pipeline.capability_tiers import WorkerConfig
    from app.pipeline.checkpoint import AiCache
    from app.pipeline.contracts import SourceText
    order = []

    def primary_transport(cand, **_k):
        order.append("P")
        cat = "UNKNOWN" if "financial" in cand["source_text"].lower() else "COMMERCIAL"
        return {"summary": "s", "category": cat, "mandatory": True}, "ok", 0.01, "{}"

    def escalation_transport(cand):
        order.append("E")
        return {"summary": "s2", "category": "FINANCIAL", "mandatory": True}, "ok", 0.01, "{}"

    prov = EscalatingProvider(QwenMinimalContractProvider(transport=primary_transport), "big",
                              transport=escalation_transport)
    router = Router({AITask.REQUIREMENT_NORMALIZATION.value: prov})
    src = [SourceText(source_document="a.txt", page_number=1, text=(
        "1. The Contractor shall submit a tender security of EGP 500,000 valid for 180 days. "
        "2. The Bidder must provide audited financial statements for the last three years. "
        "3. The Contractor shall have completed at least two similar 220 kV substations. ") * 3)]
    cache = AiCache("T-B", "m", "p")
    intel, _t = ir.run_intelligence("T-B", src, router=router, ai_cache=cache,
                                    workers=WorkerConfig(enabled=True, max_workers=2))
    assert "E" in order and order.index("E") > max(i for i, x in enumerate(order) if x == "P")
    cats = {r["category"] for r in intel["requirements"]}
    assert "FINANCIAL" in cats and "UNKNOWN" not in cats
    assert all(v["category"] != "UNKNOWN" for v in cache._data.values())  # escalated answer cached


def test_noisy_items_are_grouped(tmp_path, monkeypatch):
    """Turaif produced 96 'referenced document' alerts and 483 separate questions."""
    from app.database import SessionLocal
    from app.issues import sync_issues
    from app.models import TenderAnalysis, TenderIssue
    tid = _tender_with_files(tmp_path, monkeypatch, n=0)
    db = SessionLocal()
    try:
        db.add(TenderAnalysis(id=f"AN-{uuid.uuid4().hex[:8]}", tender_id=tid, analysis_version="t", status="COMPLETED",
                              tender={}, evidence=[], documents=[], deadlines=[], commercial=None, risks=[],
                              requirements=[{"requirement_id": f"R{i}", "summary": f"thing {i}", "category": "UNKNOWN",
                                             "mandatory": None, "source_document": "SOW.pdf", "page_number": i} for i in range(40)],
                              derived_features={"gaps": [{"kind": "referenced-form-absent",
                                                          "description": f"ANNEX {i} referenced but no matching document in package",
                                                          "evidence": ["SOW.pdf#p1"]} for i in range(96)]}))
        db.commit()
        sync_issues(db, tid)
        items = db.query(TenderIssue).filter(TenderIssue.tender_id == tid).all()
        assert len(items) == 2
        refs = next(i for i in items if i.kind == "referenced-form-absent")
        assert refs.title == "Referenced documents not found in the readable text" and refs.detail.startswith("SOW.pdf: ANNEX 0, ANNEX 1, ANNEX 2,") and refs.detail.endswith("ANNEX 29 (+66)")
        unk = next(i for i in items if i.kind == "unclassified-requirement")
        assert unk.title == "40 requirements could not be classified" and "and 10 more" in unk.detail
    finally:
        db.close()
