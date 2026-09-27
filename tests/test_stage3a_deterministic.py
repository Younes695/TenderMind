"""
Stage 3A — Deterministic Extraction Hardening — Regression Tests
Tests for the 5 fixes directly observed in Stage 3:
1. .txt consistency
2. FINANCIAL pattern
3. PERSONNEL pattern
4. Deadline context hardening
5. Commercial extraction
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tempfile
import fitz

def test_txt_normal_english():
    # Normal English TXT should be extracted, not unsupported
    import evaluation.run_real_benchmark as rb
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    txt = tmp / "test.txt"
    txt.write_text("This is English tender text with 220 kV GIS and financial capacity.", encoding='utf-8')
    # Simulate inventory for this file
    orig_root = rb.ROOT
    rb.ROOT = tmp
    try:
        inv = rb.file_inventory()
        assert any(f["filename"] == "test.txt" for f in inv), f"Inventory missing test.txt: {inv}"
        # Check that inventory marks it as TXT, not unsupported
        entry = next(f for f in inv if f["filename"] == "test.txt")
        assert "TXT" in entry["extraction_method"], f"Expected TXT method, got {entry['extraction_method']}"
        assert entry["ocr_needed"] == "NO"
        # Run document intelligence
        doc_results, _ = rb.run_document_intelligence(inv)
        assert "test.txt" in doc_results
        pages = doc_results["test.txt"]["pages"]
        assert len(pages) == 1
        assert "English tender text" in pages[0]["text"]
        assert pages[0]["method"] == "txt"
        assert doc_results["test.txt"]["total_text_chars"] > 50
        print("PASS txt_normal_english")
    finally:
        rb.ROOT = orig_root

def test_txt_utf8_arabic_mixed():
    import evaluation.run_real_benchmark as rb
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    txt = tmp / "arabic.txt"
    txt.write_text("Tender Price Schedule- التوسعات الشمالية and 220 kV GIS", encoding='utf-8')
    orig_root = rb.ROOT
    rb.ROOT = tmp
    try:
        inv = rb.file_inventory()
        entry = next(f for f in inv if f["filename"] == "arabic.txt")
        assert "TXT" in entry["extraction_method"]
        doc_results, _ = rb.run_document_intelligence(inv)
        pages = doc_results["arabic.txt"]["pages"]
        assert "التوسعات" in pages[0]["text"]
        assert "220 kV GIS" in pages[0]["text"]
        print("PASS txt_utf8_arabic_mixed")
    finally:
        rb.ROOT = orig_root

def test_txt_empty():
    import evaluation.run_real_benchmark as rb
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    txt = tmp / "empty.txt"
    txt.write_text("", encoding='utf-8')
    orig_root = rb.ROOT
    rb.ROOT = tmp
    try:
        inv = rb.file_inventory()
        doc_results, _ = rb.run_document_intelligence(inv)
        pages = doc_results["empty.txt"]["pages"]
        assert pages[0]["text"] == ""
        assert pages[0]["extraction_confidence"] == 0.5 or pages[0]["extraction_confidence"] == 0.0
        print("PASS txt_empty")
    finally:
        rb.ROOT = orig_root

def test_txt_unsupported_remains():
    import evaluation.run_real_benchmark as rb
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    # Create a truly unsupported file
    dwg = tmp / "test.dwg"
    dwg.write_bytes(b"dummy dwg content")
    orig_root = rb.ROOT
    rb.ROOT = tmp
    try:
        inv = rb.file_inventory()
        entry = next(f for f in inv if f["filename"] == "test.dwg")
        assert "Unknown" in entry["extraction_method"] or "unsupported" in entry["extraction_method"].lower()
        doc_results, _ = rb.run_document_intelligence(inv)
        assert doc_results["test.dwg"]["pages"][0]["method"] == "unsupported"
        print("PASS txt_unsupported_remains")
    finally:
        rb.ROOT = orig_root

def test_txt_via_generic_extraction():
    # Test via build_generic_extraction that .txt is not FAILED
    from evaluation.generic_extraction import build_generic_extraction
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    (tmp / "test.txt").write_text("Financial capacity: audited turnover 100M EGP and experience with 220kV GIS", encoding='utf-8')
    res = build_generic_extraction(tmp, tender_id="TEST-TXT-001", use_llm=False)
    # Find the txt document
    docs = res["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "test.txt"
    # Should be COMPLETE or PARTIAL, not FAILED (since it has text)
    assert docs[0]["extraction_status"] in ("COMPLETE", "PARTIAL")
    assert docs[0]["text_length"] > 50
    print("PASS txt_via_generic_extraction")

def test_financial_generic_example():
    from evaluation.generic_extraction import build_generic_extraction
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Financial capacity: audited annual turnover shall be at least 100M EGP", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="TEST-FIN-001", use_llm=False)
    cats = [r["category"] for r in res["requirements"]]
    assert "FINANCIAL" in cats, f"Expected FINANCIAL in {cats}"
    print("PASS financial_generic_example")

def test_financial_variant():
    from evaluation.generic_extraction import build_generic_extraction
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Minimum annual turnover shall be 50M USD for the last 3 years", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="TEST-FIN-002", use_llm=False)
    cats = [r["category"] for r in res["requirements"]]
    assert "FINANCIAL" in cats, f"Expected FINANCIAL variant, got {cats}"
    print("PASS financial_variant")

def test_personnel_generic_example_1():
    from evaluation.generic_extraction import build_generic_extraction
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "The bidder shall provide a qualified project manager.", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="TEST-PER-001", use_llm=False)
    cats = [r["category"] for r in res["requirements"]]
    assert "PERSONNEL" in cats, f"Expected PERSONNEL, got {cats}"
    print("PASS personnel_generic_example_1")

def test_personnel_generic_example_2():
    from evaluation.generic_extraction import build_generic_extraction
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Key personnel shall have relevant experience.", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="TEST-PER-002", use_llm=False)
    cats = [r["category"] for r in res["requirements"]]
    assert "PERSONNEL" in cats, f"Expected PERSONNEL, got {cats}"
    print("PASS personnel_generic_example_2")

def test_deadline_valid_submission():
    from evaluation.generic_extraction import extract_deadlines_deterministic
    text = "Bid submission deadline: 15 of March, 2024 at 2pm. The tender will be opened on 20 of March, 2024."
    dates = extract_deadlines_deterministic(text)
    assert any("15 of March, 2024" in d["date"] for d in dates), f"Expected submission deadline, got {dates}"
    print("PASS deadline_valid_submission")

def test_deadline_valid_clarification():
    from evaluation.generic_extraction import extract_deadlines_deterministic
    text = "Clarification deadline is 10 of March, 2024. Please submit queries before that."
    dates = extract_deadlines_deterministic(text)
    assert any("10 of March, 2024" in d["date"] for d in dates), f"Expected clarification deadline, got {dates}"
    print("PASS deadline_valid_clarification")

def test_deadline_valid_completion():
    from evaluation.generic_extraction import extract_deadlines_deterministic
    text = "Completion date: 15/06/2025. Delivery date is 10/06/2025."
    dates = extract_deadlines_deterministic(text)
    assert any(d["date"] == "15/06/2025" for d in dates), f"Expected completion date, got {dates}"
    print("PASS deadline_valid_completion")

def test_deadline_220_22_22_not_deadline():
    from evaluation.generic_extraction import extract_deadlines_deterministic
    text = "Supply and installation of 220/22/22 kV GIS for 6 October Northern Extensions. The voltage is 220/22/22 kV."
    dates = extract_deadlines_deterministic(text)
    assert len(dates) == 0, f"220/22/22 kV should NOT be deadline, got {dates}"
    print("PASS deadline_220_22_22_not_deadline")

def test_deadline_qd_not_deadline():
    from evaluation.generic_extraction import extract_deadlines_deterministic
    text = "QD 400-800/1/1/18 and OD 400-800/1/1/1/1/18 are technical codes, not dates."
    dates = extract_deadlines_deterministic(text)
    assert len(dates) == 0, f"QD 400-800/1/1/18 should NOT be deadline, got {dates}"
    print("PASS deadline_qd_not_deadline")

def test_deadline_unrelated_technical_numbers():
    from evaluation.generic_extraction import extract_deadlines_deterministic
    text = "The transformer is 60 MVA, 175 MVA, 220 kV, 22 kV, not a deadline. The price is 500,000 EGP."
    dates = extract_deadlines_deterministic(text)
    assert len(dates) == 0, f"Unrelated technical numbers should NOT be deadlines, got {dates}"
    print("PASS deadline_unrelated_technical_numbers")

def test_deadline_ambiguous_no_context():
    from evaluation.generic_extraction import extract_deadlines_deterministic
    text = "The document mentions 15/06/2025 but without any context, just a random date."
    dates = extract_deadlines_deterministic(text)
    # This has no deadline context term, so should be 0
    assert len(dates) == 0, f"Ambiguous date without context should NOT be deadline, got {dates}"
    print("PASS deadline_ambiguous_no_context")

def test_commercial_currency():
    from evaluation.generic_extraction import extract_commercial_terms_deterministic
    text = "Tender security is EGP 500,000. Payment in EGP."
    res = extract_commercial_terms_deterministic(text)
    assert res is not None
    assert res.get("currency") == "EGP"
    print("PASS commercial_currency")

def test_commercial_payment():
    from evaluation.generic_extraction import extract_commercial_terms_deterministic
    text = "Payment terms: 10% advance payment, 80% on delivery, 10% retention."
    res = extract_commercial_terms_deterministic(text)
    assert res is not None
    assert res.get("payment") is not None
    assert "advance" in res.get("payment").lower() or "payment" in res.get("payment").lower()
    print("PASS commercial_payment")

def test_commercial_tender_security():
    from evaluation.generic_extraction import extract_commercial_terms_deterministic
    text = "Bid security: EGP 500,000 valid for 180 days. Tender security shall be submitted as bank guarantee."
    res = extract_commercial_terms_deterministic(text)
    assert res is not None
    assert res.get("price_schedules") is not None
    assert "tender security" in res.get("price_schedules").lower() or "bid security" in res.get("price_schedules").lower() or "bid bond" in res.get("price_schedules").lower()
    print("PASS commercial_tender_security")

def test_commercial_validity():
    from evaluation.generic_extraction import extract_commercial_terms_deterministic
    text = "Bid validity is 180 days. Offer validity period is 180 days from submission."
    res = extract_commercial_terms_deterministic(text)
    assert res is not None
    # Validity may be in price_schedules or payment
    assert res.get("price_schedules") is not None or res.get("payment") is not None
    print("PASS commercial_validity")

def test_commercial_null_when_missing():
    from evaluation.generic_extraction import extract_commercial_terms_deterministic
    text = "This is just a technical spec with no commercial terms, only GIS and transformer."
    res = extract_commercial_terms_deterministic(text)
    assert res is None
    print("PASS commercial_null_when_missing")

def test_commercial_no_invented_currency():
    from evaluation.generic_extraction import extract_commercial_terms_deterministic
    text = "The project is in Saudi Arabia, client is NUCA. No currency mentioned."
    res = extract_commercial_terms_deterministic(text)
    # Should be None, not invent SAR from location/client
    assert res is None or res.get("currency") is None
    print("PASS commercial_no_invented_currency")

if __name__ == "__main__":
    test_txt_normal_english()
    test_txt_utf8_arabic_mixed()
    test_txt_empty()
    test_txt_unsupported_remains()
    test_txt_via_generic_extraction()
    test_financial_generic_example()
    test_financial_variant()
    test_personnel_generic_example_1()
    test_personnel_generic_example_2()
    test_deadline_valid_submission()
    test_deadline_valid_clarification()
    test_deadline_valid_completion()
    test_deadline_220_22_22_not_deadline()
    test_deadline_qd_not_deadline()
    test_deadline_unrelated_technical_numbers()
    test_deadline_ambiguous_no_context()
    test_commercial_currency()
    test_commercial_payment()
    test_commercial_tender_security()
    test_commercial_validity()
    test_commercial_null_when_missing()
    test_commercial_no_invented_currency()
    print("\nAll 22 Stage 3A deterministic tests passed")
