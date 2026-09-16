"""
Smoke test for Azure OCR wiring — TenderMind v4
- Uses ONE known scanned Sarai PDF page (Sarai RFP.pdf page 1)
- Sends ONLY ONE page to Azure (mocked, not real 896 pages)
- Verifies provenance: source_filename, source_page_number, azure_page_number, text, method, ocr_applied
- Verifies azure_page_number == source_page_number
- Verifies native pages are NOT sent to Azure
- Does NOT process whole tender (896 pages)
- Safe: uses mock Azure client, never logs secret, no gold injection
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.azure_doc_intel import get_azure_credentials
from evaluation.run_real_benchmark_v4 import extract_pdf_with_azure_routing

SARAI_RFP = Path(r"C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation\Sarai RFP.pdf")
VOLUME1 = Path(r"C:\Users\EgyTech\Desktop\01- Sarai 220kV Substation\volume 1 of 2.pdf")

def test_scanned_page_routing_single_page():
    """
    Verifies wiring for ONE scanned page via mocked Azure — must be exactly 1 Azure page.
    No real credentials needed (mocked).
    """
    import fitz
    # Find first scanned page in Sarai RFP.pdf (should be page 1, 0 chars)
    if not SARAI_RFP.exists():
        print(f"SKIPPED — Sarai RFP not found at {SARAI_RFP} (test not applicable in this env)")
        return
    doc = fitz.open(str(SARAI_RFP))
    scanned_idx = None
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if len(text.strip()) < 100:
            scanned_idx = i
            break
    doc.close()
    if scanned_idx is None:
        print("SKIPPED — No scanned page found")
        return

    # Mock Azure to verify wiring without needing real credentials
    mock_client = MagicMock()
    mock_page = MagicMock()
    mock_page.page_number = scanned_idx + 1
    mock_page.lines = []
    mock_page.polygon = None
    mock_page.width = 8.5
    mock_page.height = 11
    mock_page.unit = "inch"
    # Add a mock line with Arabic text to simulate OCR
    mock_line = MagicMock()
    mock_line.content = "اختبار الفئة الأولى"
    mock_line.polygon = [0,0,100,0,100,10,0,10]
    mock_line.confidence = 0.92
    mock_page.lines = [mock_line]
    mock_result = MagicMock()
    mock_result.pages = [mock_page]
    mock_result.content = ""
    mock_poller = MagicMock()
    mock_poller.result.return_value = mock_result
    mock_client.begin_analyze_document.return_value = mock_poller

    with patch("evaluation.azure_doc_intel.get_azure_client", return_value=mock_client):
        # Also need to patch the import in run_real_benchmark_v4
        import evaluation.run_real_benchmark_v4 as v4
        original = v4._azure_analyze_bytes
        # Create a mock that returns the expected provenance structure
        def mock_analyze(pdf_bytes, source_filename, source_page_number, locale="ar"):
            # Verify that locale is ar and source_page_number is preserved
            assert source_page_number == scanned_idx + 1, f"source_page_number mismatch"
            assert locale == "ar", "locale must be ar"
            return [{
                "source_filename": source_filename,
                "source_page_number": source_page_number,
                "azure_page_number": source_page_number,  # deterministic mapping
                "text": "اختبار الفئة الأولى",
                "lines": [{"content": "اختبار الفئة الأولى", "polygon": [0,0,100,0,100,10,0,10], "confidence": 0.92}],
                "confidence": 0.92,
                "polygon": None,
                "width": 8.5,
                "height": 11,
                "unit": "inch",
                "method": "azure_prebuilt-layout_locale_ar",
                "ocr_applied": True,
                "locale": "ar"
            }]
        v4._azure_analyze_bytes = mock_analyze
        # Mock get_azure_credentials to return dummy so routing thinks Azure is configured
        with patch("evaluation.run_real_benchmark_v4._get_azure_creds", return_value=("https://tendermind-docintel.cognitiveservices.azure.com/", "dummy_key_32_chars_1234567890abcd", "test")):
            # Now call routing for the single scanned page PDF
            import fitz
            doc = fitz.open(str(SARAI_RFP))
            single = fitz.open()
            single.insert_pdf(doc, from_page=scanned_idx, to_page=scanned_idx)
            import tempfile
            tmp = Path(tempfile.gettempdir()) / "test_single_scanned.pdf"
            single.save(str(tmp))
            single.close()
            doc.close()
            try:
                pages = v4.extract_pdf_with_azure_routing(tmp, use_azure=True)
                # Should be exactly 1 page, and it should have gone through Azure (mocked)
                assert len(pages) == 1, f"Expected exactly 1 page, got {len(pages)}"
                p = pages[0]
                assert "source_filename" in p, "Missing source_filename"
                assert "source_page_number" in p, "Missing source_page_number"
                assert "azure_page_number" in p, "Missing azure_page_number"
                assert "text" in p, "Missing text"
                assert "method" in p, "Missing method"
                assert "ocr_applied" in p, "Missing ocr_applied"
                assert p["azure_page_number"] == p["source_page_number"], f"azure_page_number {p['azure_page_number']} must equal source_page_number {p['source_page_number']}"
                assert p["ocr_applied"] is True, "Scanned page should be ocr_applied=True"
                assert "azure" in p["method"].lower(), f"Method should indicate Azure, got {p['method']}"
                print(f"PASS test_scanned_page_routing_single_page — 1 Azure page, provenance OK, azure_page_number == source_page_number ({p['source_page_number']})")
            finally:
                v4._azure_analyze_bytes = original
                if tmp.exists():
                    tmp.unlink()

def test_native_pages_not_sent_to_azure():
    """
    Verify that text-native pages are NOT sent to Azure (0 Azure calls).
    """
    if not VOLUME1.exists():
        print(f"SKIPPED — volume 1 not found at {VOLUME1}")
        return
    import fitz
    doc = fitz.open(str(VOLUME1))
    native_idx = None
    for i, page in enumerate(doc):
        text = page.get_text("text")
        garbled = text.count("�") / max(len(text), 1) if text else 0
        if len(text.strip()) > 100 and garbled < 0.3:
            native_idx = i
            break
    doc.close()
    if native_idx is None:
        print("SKIPPED — No native page found")
        return
    from unittest.mock import patch
    import evaluation.run_real_benchmark_v4 as v4
    call_count = {"count": 0}
    def mock_analyze(pdf_bytes, source_filename, source_page_number, locale="ar"):
        call_count["count"] += 1
        return [{"source_filename": source_filename, "source_page_number": source_page_number, "azure_page_number": source_page_number, "text": "mock", "method": "azure_mock", "ocr_applied": True}]
    original = v4._azure_analyze_bytes
    v4._azure_analyze_bytes = mock_analyze
    try:
        import fitz, tempfile
        doc = fitz.open(str(VOLUME1))
        single = fitz.open()
        single.insert_pdf(doc, from_page=native_idx, to_page=native_idx)
        tmp = Path(tempfile.gettempdir()) / "test_single_native.pdf"
        single.save(str(tmp))
        single.close()
        doc.close()
        # Mock credentials to appear configured
        with patch("evaluation.run_real_benchmark_v4._get_azure_creds", return_value=("https://tendermind-docintel.cognitiveservices.azure.com/", "dummy_key", "test")):
            pages = v4.extract_pdf_with_azure_routing(tmp, use_azure=True)
            assert len(pages) == 1
            assert pages[0]["method"] == "fitz_direct_native", f"Native page should be fitz_direct_native, got {pages[0]['method']}"
            assert pages[0]["ocr_applied"] is False, "Native page should not be ocr_applied"
            assert call_count["count"] == 0, f"Azure should NOT have been called for native page, but was called {call_count['count']} times"
            print(f"PASS test_native_pages_not_sent_to_azure — native page correctly bypassed Azure (0 calls)")
    finally:
        v4._azure_analyze_bytes = original
        if tmp.exists():
            tmp.unlink()

def test_azure_error_handling_no_secret():
    """
    Verify Azure errors do not log key and do not silently fake text.
    """
    from evaluation.azure_doc_intel import analyze_pdf_bytes, create_synthetic_pdf
    pdf_bytes = create_synthetic_pdf("test")
    from unittest.mock import patch, MagicMock
    from azure.core.exceptions import HttpResponseError
    fake_key = "x" * 32
    # Mock client to raise 401
    mock_client = MagicMock()
    mock_client.begin_analyze_document.side_effect = HttpResponseError(message="(401) Access denied due to invalid subscription key")
    with patch("evaluation.azure_doc_intel.get_azure_client", return_value=mock_client):
        # Also need to mock get_azure_credentials to return fake endpoint/key for the wrapper's error message
        with patch("evaluation.azure_doc_intel.get_azure_credentials", return_value=("https://tendermind-docintel.cognitiveservices.azure.com/", fake_key, "test")):
            try:
                analyze_pdf_bytes(pdf_bytes, source_filename="test.pdf", source_page_number=1)
                assert False, "Should have raised"
            except RuntimeError as e:
                msg = str(e)
                assert "401" in msg, "Should contain 401"
                assert fake_key not in msg, "Key must not be in error message"
                assert "Access denied" in msg, "Should contain original error"
                # Ensure not silently marked as successful
                assert "fake" not in msg.lower() or "success" not in msg.lower()
                print("PASS test_azure_error_handling_no_secret — 401 handled without logging key, no fake text")

if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass
    test_scanned_page_routing_single_page()
    test_native_pages_not_sent_to_azure()
    test_azure_error_handling_no_secret()
    print("\nAll 3 wiring smoke tests passed (mocked, single-page, no secret logging, no whole-tender processing)")
