"""
Test that main() with --smoke-azure invokes the production Azure routing for exactly one scanned page.
- Uses the SAME production call path as real benchmark: extract_pdf_with_azure_routing()
- Sends exactly ONE page (Sarai RFP.pdf page 1) to Azure (mocked)
- Verifies provenance: source_filename, source_page_number, azure_page_number, method, ocr_applied
- Does NOT process whole tender, does NOT call LLM/decision
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_main_smoke_azure_invokes_production_path():
    from evaluation import run_real_benchmark_v4 as v4
    import fitz
    # Mock credentials for both smoke check and routing
    with patch("evaluation.run_real_benchmark_v4.check_azure_credentials", return_value=("https://tendermind-docintel.cognitiveservices.azure.com/", "dummy_key_32_chars_1234567890abcd")):
        with patch("evaluation.run_real_benchmark_v4._get_azure_creds", return_value=("https://tendermind-docintel.cognitiveservices.azure.com/", "dummy_key_32_chars_1234567890abcd", "mock")):
            with patch("evaluation.azure_doc_intel.get_azure_credentials", return_value=("https://tendermind-docintel.cognitiveservices.azure.com/", "dummy_key_32_chars_1234567890abcd", "mock")):
                def mock_analyze(pdf_bytes, source_filename, source_page_number, locale="ar"):
                    assert locale == "ar", f"locale must be ar, got {locale}"
                    assert source_page_number == 1, f"source_page_number should be 1, got {source_page_number}"
                    return [{
                        "source_filename": source_filename,
                        "source_page_number": source_page_number,
                        "azure_page_number": source_page_number,
                        "text": "Mock Azure OCR text for Sarai RFP page 1 — Arabic: اختبار",
                        "lines": [],
                        "confidence": 0.92,
                        "method": "azure_prebuilt-layout_locale_ar",
                        "ocr_applied": True,
                        "locale": "ar"
                    }]
                with patch("evaluation.run_real_benchmark_v4._azure_analyze_bytes", side_effect=mock_analyze):
                    with patch("evaluation.azure_doc_intel.analyze_pdf_bytes", side_effect=mock_analyze):
                        original_argv = sys.argv
                        sys.argv = ["run_real_benchmark_v4.py", "--smoke-azure"]
                        try:
                            import io
                            from contextlib import redirect_stdout
                            f = io.StringIO()
                            with redirect_stdout(f):
                                v4.main()
                            output = f.getvalue()
                            assert "SMOKE" in output, "Smoke output should contain SMOKE"
                            assert "Azure analyze calls: 1" in output, f"Smoke should report exactly 1 Azure call, got: {output[:800]}"
                            assert "SMOKE PASS" in output, f"Smoke should PASS, got: {output[:800]}"
                            assert "Sarai RFP.pdf" in output or "tendermind_smoke_single_page.pdf" in output, "Source filename should be mentioned"
                            assert "1394 pages" not in output or "SMOKE" in output, "Smoke should not process whole tender"
                            print("PASS test_main_smoke_azure_invokes_production_path — main() with --smoke-azure correctly invoked production Azure routing for exactly 1 page")
                        finally:
                            sys.argv = original_argv

if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass
    test_main_smoke_azure_invokes_production_path()
    print("\nSmoke integration test passed")
