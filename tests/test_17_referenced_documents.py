"""Referenced documents (APPENDIX / ANNEX / EXHIBIT / FORM): a reference only counts as
missing when it is found neither as a file nor as its own section inside the text we
could read. All pages below are synthetic; they copy the shapes seen in real packages
(cover pages, contents pages, 'not applicable' entries, dashed ids, sheet headers)."""
import uuid

from app.pipeline import gaps as GP
from app.pipeline.contracts import DocumentArtifact, SourceText


def _doc(name, pages=1, status="COMPLETE"):
    ext = "." + name.rsplit(".", 1)[-1].lower()
    return DocumentArtifact(name, "", ext, status=status, page_count=pages, total_text_chars=1000)


def _absent(docs, sources):
    return {g.description.split(" referenced")[0]: g
            for g in GP.analyze_package_gaps(docs, sources) if g.kind == "referenced-form-absent"}


SOW = "Main SOW.pdf"
COVER = "APPENDIX - VII\n\nCIVIL AND STRUCTURAL DESIGN CRITERIA\nPage 1 of 3\nThe works shall comply with this appendix."
MENTION = SourceText(SOW, 3, "The CONTRACTOR shall follow Appendix VII for civil works and drainage design.")


def test_appendix_with_its_own_cover_page_inside_the_pdf_is_not_missing():
    docs = [_doc(SOW, pages=40)]
    assert "APPENDIX VII" not in _absent(docs, [MENTION, SourceText(SOW, 40, COVER)])


def test_cover_page_without_text_is_reported_as_not_found_with_the_unread_pages():
    # The cover is a scan that produced no text: the body pages carry no label.
    docs = [_doc(SOW, pages=40)]
    body = SourceText(SOW, 40, "1. Loads\nDead loads shall be computed from the unit weights below.")
    gap = _absent(docs, [MENTION, body])["APPENDIX VII"]
    assert gap.description == "APPENDIX VII referenced but not found in the readable text of the package"
    assert gap.note == "38 page(s) of the package have no readable text"
    assert gap.evidence == [f"{SOW}#p3"]


def test_contents_page_is_not_evidence_that_the_appendix_is_there():
    toc = SourceText(SOW, 2, "TABLE OF CONTENTS\nAPPENDIX I - DRAWING CONTROL SHEETS\n"
                             "APPENDIX II - MATERIAL DATA SCHEDULES\nAPPENDIX III - TECHNICAL DATA MANUALS\n")
    absent = _absent([_doc(SOW, pages=2)], [toc])
    assert {"APPENDIX I", "APPENDIX II", "APPENDIX III"} <= set(absent)


def test_contents_page_listing_a_section_split_over_lines_is_still_a_contents_page():
    toc = SourceText(SOW, 2, "TABLE OF CONTENTS\nAPPENDIX \nI \n- DRAWINGS\nAPPENDIX \n \nII \n- MATERIALS\n"
                             "APPENDIX \nIII \n- MANUALS\n")
    assert {"APPENDIX I", "APPENDIX II", "APPENDIX III"} <= set(_absent([_doc(SOW, pages=2)], [toc]))


def test_entries_marked_not_applicable_are_not_reported():
    toc = SourceText(SOW, 2, "APPENDIX IV - OPERATIONAL SPARE PARTS\n(NOT APPLICABLE)\n"
                             "APPENDIX V - NOT APPLICABLE\nAPPENDIX VI - TRAINING REQUIREMENTS\n")
    absent = _absent([_doc(SOW, pages=2)], [toc])
    assert "APPENDIX IV" not in absent and "APPENDIX V" not in absent
    assert "APPENDIX VI" in absent


def test_file_names_match_whole_identifiers_not_substrings():
    docs = [_doc("Appendix II - Safety Requirements.doc"), _doc("Volume 1.pdf")]
    absent = _absent(docs, [SourceText("Volume 1.pdf", 1, "Appendix I and Appendix II apply to all works.")])
    assert "APPENDIX I" in absent and "APPENDIX II" not in absent


def test_file_names_with_underscores_are_read():
    docs = [_doc("ITB_Annexure_II.xlsx"), _doc("Appendix_B.pdf"), _doc("02_APPENDIX VI.pdf"), _doc("ITB.doc")]
    src = [SourceText("ITB.doc", 1, "Submit Annexure II, Appendix B and Appendix VI with the offer.")]
    assert not {"ANNEXURE II", "APPENDIX B", "APPENDIX VI"} & set(_absent(docs, src))


def test_sub_numbered_ids_are_kept_whole():
    docs = [_doc("Annexure I-1.xlsx"), _doc("ITB.doc")]
    src = [SourceText("ITB.doc", 1, "Fill in ANNEXURE I-1 and ANNEXURE I-2. See APPENDIX C-1.")]
    absent = _absent(docs, src)
    assert "ANNEXURE I-1" not in absent
    assert {"ANNEXURE I-2", "APPENDIX C-1"} <= set(absent)


def test_annex_and_annexure_name_the_same_document():
    docs = [_doc("5- Annex-XVI- Transformer Losses.xlsx"), _doc("ITB.doc")]
    src = [SourceText("ITB.doc", 1, "Guaranteed losses (use the format of Annexure XVI).")]
    assert "ANNEXURE XVI" not in _absent(docs, src)


def test_dashed_references_are_read():
    src = [SourceText("ITB.doc", 1, "Submit the schedule using ANNEXURE-II.\nRefer to Appendix – XIII for the SAS.")]
    absent = _absent([_doc("ITB.doc")], src)
    assert {"ANNEXURE II", "APPENDIX XIII"} <= set(absent)


def test_the_word_form_in_ordinary_prose_is_not_a_reference():
    src = [SourceText(SOW, 7, "All impedances must be in rectangular form R+jX.\n"
                              "Provide type and rating details in a tabular form\nx) Calculation for bus bar sizing\n"
                              "Utilizing COMPANY Standard Form 15109 (11/83). Blank copies will be provided.")]
    absent = _absent([_doc(SOW, pages=7)], src)
    assert "FORM R" not in absent and "FORM X" not in absent
    assert "FORM 15109" in absent


def test_a_sheet_that_starts_with_the_annexure_heading_counts():
    docs = [_doc("Technical Annexes.xlsx", pages=2), _doc("ITB.doc")]
    src = [SourceText("ITB.doc", 1, "Propose the personnel indicated in Annexure I."),
           SourceText("Technical Annexes.xlsx", 1, "TECHNICAL PROPOSAL |  | ANNEXURE - I | \n"
                                                   "RFx NO. 000: Construction of a substation |  | \nKey personnel | Name"),
           SourceText("Technical Annexes.xlsx", 1, " | Appendix B: Template Administration |  | \n | 0 | ")]
    absent = _absent(docs, src + [SourceText("ITB.doc", 1, "Fill in Appendix B of the template.")])
    assert "ANNEXURE I" not in absent and "APPENDIX B" not in absent


def test_a_cover_block_naming_the_appendix_to_the_main_document_counts():
    page = SourceText(SOW, 90, "REVISIONS\nTHIS DOCUMENT IS NOT TO BE USED FOR CONSTRUCTION\nREFER TO\nMAIN SOW/TS\n"
                               "1\nOF\n12\n\nDESCRIPTION\n\n\nAPPENDIX-X\nTO MAIN SOW/TS\n\nMECHANICAL DESIGN CRITERIA\n")
    mention = SourceText(SOW, 4, "For HVAC documentation refer to Appendix X and Section 6.10.")
    assert "APPENDIX X" not in _absent([_doc(SOW, pages=90)], [mention, page])


def test_mentions_in_running_text_never_count_as_the_appendix():
    pages = [SourceText(SOW, 1, "Appendix-VII for details. After completion the board shall be removed."),
             SourceText(SOW, 2, "Additional drawings as specified in\nAppendix VI\n"),
             SourceText(SOW, 3, "ALL WORKS TO BE PERFORMED AT REMOTE END SUBSTATIONS PER\nAPPENDIX X PART 1 OF PTS-1\n"),
             SourceText(SOW, 4, "The SAS shall conform to\nAppendix-XIII.  The control system shall be integrated.")]
    absent = _absent([_doc(SOW, pages=4)], pages)
    assert {"APPENDIX VI", "APPENDIX VII", "APPENDIX X", "APPENDIX XIII"} <= set(absent)


def test_drawing_title_blocks_alone_do_not_prove_the_appendix_is_there():
    # Title blocks repeat a label on every sheet, and the label can name another appendix.
    block = "REVISIONS\nDRAWING CONTROL SHEET\nNO.\n1\nACME GRID CO\nAPPENDIX-VI\nPART-1\nTO\nPTS-1\nTELECOM"
    pages = [SourceText(SOW, n, block + f"\nSheet {n}") for n in (50, 51, 52, 53)]
    assert "APPENDIX VI" in _absent([_doc(SOW, pages=53)], pages + [SourceText(SOW, 5, "See Appendix VI.")])


def test_a_list_of_attachments_in_a_word_file_is_not_the_attachments():
    src = [SourceText("ITB.doc", 1, "ATTACHMENTS\nANNEXURE-I  KEY PERSONNEL\nANNEXURE-II  DELIVERY SCHEDULE\n"
                                    "ANNEXURE-III  SUBCONTRACTING PLAN\nPREPARATION OF THE PROPOSAL\n")]
    assert {"ANNEXURE I", "ANNEXURE II", "ANNEXURE III"} <= set(_absent([_doc("ITB.doc")], src))


def test_identifiers_are_case_sensitive_and_words_are_not_ids():
    src = [SourceText(SOW, 1, "Appendix shall be read with the Annexure to the contract. The bids exhibit a "
                              "wide spread. Annex a list of the equipment to the offer. Samples shall exhibit "
                              "A-grade finish. Results are given in tabular form X. See EXHIBIT C.")]
    assert set(_absent([_doc(SOW)], src)) == {"EXHIBIT C"}


def test_old_spellings_still_normalize():
    assert GP.normalize_form_ref("Appendix\nV") == "APPENDIX V"
    assert GP.normalize_form_ref("ANNEXURE-II") == "ANNEXURE II"
    assert GP.normalize_form_ref("Annexure to") is None


def test_grouped_issue_says_not_found_and_how_many_pages_were_unread(tmp_path, monkeypatch):
    monkeypatch.setenv("TENDERMIND_STORAGE_ROOT", str(tmp_path))
    from app.database import SessionLocal, init_db
    from app.issues import build_candidates
    from app.models import Tender, TenderAnalysis
    init_db()
    tid = f"T17-{uuid.uuid4().hex[:6]}"
    note = "12 page(s) of the package have no readable text"
    db = SessionLocal()
    try:
        db.add(Tender(id=tid, title="t"))
        db.add(TenderAnalysis(id=f"AN-{uuid.uuid4().hex[:8]}", tender_id=tid, analysis_version="t", status="COMPLETED",
                              tender={}, evidence=[], documents=[], deadlines=[], commercial=None, risks=[],
                              requirements=[],
                              derived_features={"gaps": [
                                  {"kind": "referenced-form-absent", "evidence": ["SOW.pdf#p3"], "note": note,
                                   "description": "APPENDIX IX referenced but not found in the readable text of the package"},
                                  {"kind": "referenced-form-absent", "evidence": ["SOW.pdf#p9"], "note": note,
                                   "description": "ANNEXURE XIV referenced but not found in the readable text of the package"}]}))
        db.commit()
        items = [c for c in build_candidates(db, tid) if c["kind"] == "referenced-form-absent"]
        assert len(items) == 1
        assert items[0]["title"] == "Referenced documents not found in the readable text (12 pages unread)"
        assert items[0]["detail"] == "SOW.pdf: ANNEXURE XIV, APPENDIX IX"
    finally:
        db.close()
