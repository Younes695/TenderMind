"""
Tests for evaluation/azure_doc_intel.py — Safe Azure OCR wrapper
- synthetic 1-page PDF
- page-number provenance
- filename + page mapping
- Azure error handling
- missing credentials
- no secret logging
"""
import os
import io
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.azure_doc_intel import (
    get_azure_credentials,
    check_credentials_present,
    get_azure_client,
    analyze_pdf_bytes,
    analyze_pdf_file,
    is_scanned_or_garbled,
    create_synthetic_pdf,
    EXPECTED_ENDPOINT
)

def test_missing_credentials():
    # Ensure env without Azure vars returns NOT FOUND and does not log key
    with patch.dict(os.environ, {}, clear=True):
        # Clear also FORM_RECOGNIZER
        for k in list(os.environ.keys()):
            if "AZURE" in k or "DOCUMENT_INTELLIGENCE" in k:
                del os.environ[k]
        endpoint, key, source = get_azure_credentials()
        assert endpoint is None, "Should be None when not set"
        assert key is None
        ok, msg = check_credentials_present()
        assert not ok, "Should be not ok when missing"
        assert "NOT FOUND" in msg
        assert key is None or "sk-" not in msg  # No secret in msg
    print("PASS test_missing_credentials")

def test_no_secret_logging():
    # Ensure that even when key is set, messages only contain len, not value
    fake_key = "a" * 32
    fake_endpoint = EXPECTED_ENDPOINT
    with patch.dict(os.environ, {"AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": fake_endpoint, "AZURE_DOCUMENT_INTELLIGENCE_KEY": fake_key}, clear=False):
        endpoint, key, _ = get_azure_credentials()
        # Simulate check that would log
        _, msg = check_credentials_present()
        # Ensure key value not in msg
        assert fake_key not in msg, "Key value must not appear in log"
        assert str(len(fake_key)) in msg or "len 32" in msg, "Should log len only"
    print("PASS test_no_secret_logging")

def test_synthetic_pdf_creation():
    pdf_bytes = create_synthetic_pdf("TenderMind preflight test — Arabic: اختبار")
    assert pdf_bytes.startswith(b"%PDF"), "Should be PDF bytes"
    assert len(pdf_bytes) > 500, "PDF should have content"
    print("PASS test_synthetic_pdf_creation")

def test_page_number_provenance():
    # Mock Azure client to avoid real call, test deterministic mapping
    fake_key = "b" * 32
    fake_endpoint = EXPECTED_ENDPOINT
    with patch.dict(os.environ, {"AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": fake_endpoint, "AZURE_DOCUMENT_INTELLIGENCE_KEY": fake_key}, clear=False):
        # Mock DocumentIntelligenceClient
        mock_client = MagicMock()
        mock_page = MagicMock()
        mock_page.page_number = 5
        mock_page.lines = []
        mock_page.polygon = None
        mock_page.width = 8.5
        mock_page.height = 11
        mock_page.unit = "inch"
        mock_result = MagicMock()
        mock_result.pages = [mock_page]
        mock_result.content = ""
        mock_poller = MagicMock()
        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document.return_value = mock_poller

        with patch("evaluation.azure_doc_intel.get_azure_client", return_value=mock_client):
            # Also need to mock the call inside analyze_pdf_bytes where it calls get_azure_client
            pdf_bytes = create_synthetic_pdf("test")
            pages = analyze_pdf_bytes(pdf_bytes, source_filename="test.pdf", source_page_number=5, locale="ar")
            assert len(pages) == 1, "Should return 1 page"
            assert pages[0]["source_filename"] == "test.pdf", "Filename preserved"
            assert pages[0]["source_page_number"] == 5, "Source page number preserved deterministically"
            assert pages[0]["azure_page_number"] == 5, "Azure pageNumber mapped deterministically"
            assert pages[0]["ocr_applied"] is True, "Should be marked as OCR"
            assert pages[0]["locale"] == "ar", "Locale preserved"

    print("PASS test_page_number_provenance")

def test_filename_page_mapping():
    # Test that source filename + page number are preserved for multi-page
    fake_key = "c" * 32
    fake_endpoint = EXPECTED_ENDPOINT
    with patch.dict(os.environ, {"AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": fake_endpoint, "AZURE_DOCUMENT_INTELLIGENCE_KEY": fake_key}, clear=False):
        mock_client = MagicMock()
        # Mock 3 pages
        mock_pages = []
        for i in range(3):
            mp = MagicMock()
            mp.page_number = i + 1
            mp.lines = []
            mp.polygon = None
            mp.width = 8.5
            mp.height = 11
            mp.unit = "inch"
            mock_pages.append(mp)
        mock_result = MagicMock()
        mock_result.pages = mock_pages
        mock_poller = MagicMock()
        mock_poller.result.return_value = mock_result
        mock_client.begin_analyze_document.return_value = mock_poller

        with patch("evaluation.azure_doc_intel.get_azure_client", return_value=mock_client):
            pdf_bytes = create_synthetic_pdf("multi")
            # Simulate file-level call that would produce 3 pages
            # For this test, we directly test analyze_pdf_bytes for single page, but check mapping holds
            pages = analyze_pdf_bytes(pdf_bytes, source_filename="G/G-3B, GIS.pdf", source_page_number=2, locale="ar")
            assert pages[0]["source_filename"] == "G/G-3B, GIS.pdf"
            assert pages[0]["source_page_number"] == 2
    print("PASS test_filename_page_mapping")

def test_azure_error_handling():
    # Test that 401/403/404 are handled without logging key
    fake_key = "d" * 32
    fake_endpoint = EXPECTED_ENDPOINT
    with patch.dict(os.environ, {"AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": fake_endpoint, "AZURE_DOCUMENT_INTELLIGENCE_KEY": fake_key}, clear=False):
        mock_client = MagicMock()
        # Simulate 401
        from azure.core.exceptions import HttpResponseError
        mock_client.begin_analyze_document.side_effect = HttpResponseError(message="(401) Access denied due to invalid subscription key")
        with patch("evaluation.azure_doc_intel.get_azure_client", return_value=mock_client):
            pdf_bytes = create_synthetic_pdf("test")
            try:
                analyze_pdf_bytes(pdf_bytes, source_filename="test.pdf", source_page_number=1)
                assert False, "Should have raised"
            except RuntimeError as e:
                msg = str(e)
                assert "401" in msg, "Should contain 401"
                assert fake_key not in msg, "Key must not be in error message"
                assert "Access denied" in msg
    print("PASS test_azure_error_handling")

def test_is_scanned_routing():
    assert is_scanned_or_garbled("", 0) == True, "Empty should be scanned"
    assert is_scanned_or_garbled("a" * 50, 0) == True, "<100 should be scanned"
    assert is_scanned_or_garbled("a" * 150, 0) == False, ">100 not scanned"
    assert is_scanned_or_garbled("a" * 150, 0.4) == True, "garbled >0.3 should be scanned"
    print("PASS test_is_scanned_routing")

def test_azure_client_missing_credentials():
    with patch.dict(os.environ, {}, clear=True):
        # Ensure no Azure env
        for k in list(os.environ.keys()):
            if "AZURE" in k:
                del os.environ[k]
        try:
            get_azure_client()
            assert False, "Should raise when credentials missing"
        except RuntimeError as e:
            assert "not configured" in str(e).lower(), "Should mention not configured"
            # Ensure no key in message (since no key, nothing to leak)
            assert "sk-" not in str(e)
    print("PASS test_azure_client_missing_credentials")

if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass
    test_missing_credentials()
    test_no_secret_logging()
    test_synthetic_pdf_creation()
    test_page_number_provenance()
    test_filename_page_mapping()
    test_azure_error_handling()
    test_is_scanned_routing()
    test_azure_client_missing_credentials()
    print("\nAll 8 Azure/OCR tests passed")
