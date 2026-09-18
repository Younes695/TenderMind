"""
Focused tests for PDF OCR routing fix — Task 9 Phase A
- Verifies ocr_needed_hint=False does NOT invoke Tesseract
- Verifies ocr_needed_hint=True still routes via Tesseract
- Verifies native vs scanned handling, provenance, confidence, fallback
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from unittest.mock import patch, MagicMock
import fitz

from evaluation.run_real_benchmark import extract_pdf_text

def _create_pdf_with_text(text: str) -> Path:
    import tempfile
    tmp = Path(tempfile.gettempdir()) / f"test_routing_{hash(text) % 10000}.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(str(tmp))
    doc.close()
    return tmp

def _create_scanned_pdf() -> Path:
    """Create a PDF with no extractable text (image-only) — will be detected as scanned (len<50)"""
    import tempfile
    from PIL import Image
    import io
    tmp = Path(tempfile.gettempdir()) / "test_scanned_routing.pdf"
    # Create a blank image and embed as PDF page (no text)
    img = Image.new("RGB", (600, 800), color="white")
    # Add some visual noise so Tesseract would have something if it ran, but fitz get_text will be empty
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    # Create PDF with image
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Insert image (so page has no text)
    doc.save(str(tmp))
    doc.close()
    return tmp

def test_ocr_needed_false_does_not_invoke_tesseract():
    """1. ocr_needed=False: Tesseract NOT invoked"""
    pdf = _create_pdf_with_text("This is a readable native PDF with sufficient text length to be considered native and not scanned. " * 5)
    with patch("evaluation.run_real_benchmark._call_tesseract_routing") as mock_tess:
        pages = extract_pdf_text(pdf, ocr_needed_hint=False)
        mock_tess.assert_not_called()
        assert len(pages) >= 1
        assert pages[0].get("ocr_applied") is False
        print("PASS test_ocr_needed_false_does_not_invoke_tesseract")

def test_ocr_needed_true_routing_available():
    """2. ocr_needed=True: OCR routing remains available"""
    # Use a scanned PDF (empty text)
    pdf = _create_scanned_pdf()
    # Mock Tesseract to return a fake OCR result without actually running OCR
    fake_pages = [{"page_number": 1, "text": "Fake OCR text", "method": "tesseract_5.4.0_ara+eng_psm6_dpi300", "ocr_applied": True, "extraction_confidence": 0.85, "confidence": 0.85}]
    with patch("evaluation.run_real_benchmark._call_tesseract_routing", return_value=fake_pages) as mock_tess:
        pages = extract_pdf_text(pdf, ocr_needed_hint=True)
        mock_tess.assert_called_once()
        assert pages[0].get("ocr_applied") is True
        print("PASS test_ocr_needed_true_routing_available")

def test_readable_native_page_remains_native():
    """3. readable native page remains native (no OCR)"""
    pdf = _create_pdf_with_text("Native PDF with sufficient text for direct extraction. " * 10)
    pages = extract_pdf_text(pdf, ocr_needed_hint=False)
    assert pages[0].get("ocr_applied") is False
    assert "fitz" in pages[0].get("method", "")
    assert len(pages[0].get("text","").strip()) > 50
    print("PASS test_readable_native_page_remains_native")

def test_scanned_page_gets_ocr():
    """4. scanned page gets OCR when hint True"""
    pdf = _create_scanned_pdf()
    fake_pages = [{"page_number": 1, "text": "Scanned OCR result", "method": "tesseract_5.4.0_ara+eng_psm6_dpi300", "ocr_applied": True, "extraction_confidence": 0.85}]
    with patch("evaluation.run_real_benchmark._call_tesseract_routing", return_value=fake_pages):
        pages = extract_pdf_text(pdf, ocr_needed_hint=True)
        assert pages[0].get("ocr_applied") is True
        assert "tesseract" in pages[0].get("method", "")
        print("PASS test_scanned_page_gets_ocr")

def test_provenance_source_page_number_correct():
    """5. provenance: source page number remains correct"""
    pdf = _create_pdf_with_text("Provenance test content. " * 10)
    pages = extract_pdf_text(pdf, ocr_needed_hint=False)
    assert pages[0].get("page_number") == 1
    # For multi-page, test with 2 pages
    import tempfile
    tmp = Path(tempfile.gettempdir()) / "test_provenance.pdf"
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i+1} content " * 5)
    doc.save(str(tmp))
    doc.close()
    pages2 = extract_pdf_text(tmp, ocr_needed_hint=False)
    assert len(pages2) == 2
    assert pages2[0].get("page_number") == 1
    assert pages2[1].get("page_number") == 2
    print("PASS test_provenance_source_page_number_correct")

def test_confidence_method_available():
    """6. confidence/method remain available where currently supported"""
    pdf = _create_pdf_with_text("Confidence test " * 10)
    pages = extract_pdf_text(pdf, ocr_needed_hint=False)
    assert "extraction_confidence" in pages[0]
    assert "method" in pages[0]
    assert isinstance(pages[0].get("extraction_confidence"), (int, float))
    print("PASS test_confidence_method_available")

def test_existing_fallback_remains_intact():
    """7. existing fallback behavior remains intact (None hint preserves safe behavior)"""
    pdf = _create_pdf_with_text("Fallback test " * 10)
    # With None hint, should still try Tesseract first but fallback to fitz if Tesseract fails
    # Mock Tesseract to raise exception
    with patch("evaluation.run_real_benchmark._call_tesseract_routing", side_effect=Exception("mock failure")):
        pages = extract_pdf_text(pdf, ocr_needed_hint=None)
        # Should fallback to fitz and still return pages
        assert len(pages) >= 1
        assert len(pages[0].get("text","").strip()) > 0
        print("PASS test_existing_fallback_remains_intact")

if __name__ == "__main__":
    test_ocr_needed_false_does_not_invoke_tesseract()
    test_ocr_needed_true_routing_available()
    test_readable_native_page_remains_native()
    test_scanned_page_gets_ocr()
    test_provenance_source_page_number_correct()
    test_confidence_method_available()
    test_existing_fallback_remains_intact()
    print("\nAll 7 PDF OCR routing tests passed")
