"""Stage 7 — conflicts inside the tender package become clarification questions."""
from app.conflicts import find, words_to_int
from app.pipeline.contracts import SourceText


def S(doc, page, text):
    return SourceText(source_document=doc, page_number=page, text=text)


def test_words_to_int():
    assert words_to_int("twenty six") == 26 and words_to_int("Ten") == 10 and words_to_int("one hundred") == 100
    assert words_to_int("seventy-five") == 75 and words_to_int("many") is None


def test_words_vs_digits_mismatch_is_found_and_matching_ones_are_not():
    c = find([S("Sch C.doc", 1, "COMPANY shall recover the Advance Payment by deducting twenty six percent (13%) "
                                "from each invoice. Advance Payment shall be Ten percent (10%) of the price.")])
    assert len(c) == 1 and c[0]["fact"] == "words_vs_digits"
    assert c[0]["values"][0]["value"].startswith("twenty six") and c[0]["values"][1]["value"] == "13"


def test_same_fact_different_values_across_documents():
    c = find([S("ITB.pdf", 3, "Bids shall remain valid for 90 days from the closing date."),
              S("Bid Form.doc", 1, "This offer shall remain valid for 120 days."),
              S("Sch A.doc", 7, "The performance bond shall be 10% of the Contract Price."),
              S("Sch C.doc", 2, "Performance guarantee equal to 10% of the Contract Price.")])
    facts = {x["fact"]: x for x in c}
    assert set(facts) == {"bid_validity"}  # 10% vs 10% is not a conflict
    vals = [v["value"] for v in facts["bid_validity"]["values"]]
    assert vals == ["90 days", "120 days"]


def test_units_normalised_and_same_document_not_a_conflict():
    c = find([S("A.doc", 1, "The completion period is 12 months from the effective date."),
              S("B.doc", 4, "Contract duration of 360 days.")])
    assert c == []  # 12 months == 360 days
    c2 = find([S("A.doc", 1, "Retention of 5% applies."), S("A.doc", 9, "Retention of 10% for portion B.")])
    assert c2 == []  # all in one document (e.g. per-portion figures)


def test_conflict_becomes_a_high_question(monkeypatch):
    import uuid
    from app import conflicts
    from app.database import SessionLocal, init_db
    from app.issues import build_candidates
    from app.models import Tender
    init_db()
    monkeypatch.setattr(conflicts, "tender_conflicts", lambda tid: find([
        S("ITB.pdf", 3, "Bids shall remain valid for 90 days."), S("Form.doc", 1, "Offer valid for 120 days.")]))
    db = SessionLocal()
    tid = f"CF-{uuid.uuid4().hex[:6]}"
    try:
        db.add(Tender(id=tid, title="t")); db.commit()
        q = [c for c in build_candidates(db, tid) if c["kind"] == "conflict"]
        assert len(q) == 1 and q[0]["priority"] == "HIGH" and "Bid validity" in q[0]["title"]
        assert "90 days" in q[0]["detail"] and "Form.doc" in q[0]["detail"]
    finally:
        db.close()
