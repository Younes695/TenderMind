"""
Azure Document Intelligence Wrapper — TenderMind
- Reads credentials ONLY from environment variables (never prints/logs key)
- Small testable wrapper around DocumentIntelligenceClient.begin_analyze_document
- Preserves page-level provenance: source filename + source page number -> Azure pageNumber
- Handles scanned/empty/garbled routing (text-native pages bypass Azure)
- Frozen contract, schemas, thresholds, deterministic BID/REVIEW/NO_BID unchanged
"""
import os
import io
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

EXPECTED_ENDPOINT = "https://tendermind-docintel.cognitiveservices.azure.com/"

def _get_env(name: str) -> Optional[str]:
    return os.environ.get(name)

def get_azure_credentials() -> Tuple[Optional[str], Optional[str], str]:
    """
    Returns (endpoint, key, source). Never logs key value.
    Checks AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT / KEY and FORM_RECOGNIZER fallbacks.
    """
    endpoint = _get_env("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or _get_env("AZURE_FORM_RECOGNIZER_ENDPOINT") or _get_env("DOCUMENT_INTELLIGENCE_ENDPOINT")
    key = _get_env("AZURE_DOCUMENT_INTELLIGENCE_KEY") or _get_env("AZURE_FORM_RECOGNIZER_KEY") or _get_env("DOCUMENT_INTELLIGENCE_KEY")
    source = "AZURE_DOCUMENT_INTELLIGENCE_*"
    if not endpoint and _get_env("AZURE_FORM_RECOGNIZER_ENDPOINT"):
        source = "AZURE_FORM_RECOGNIZER_*"
    return endpoint, key, source

def check_credentials_present() -> Tuple[bool, str]:
    endpoint, key, _ = get_azure_credentials()
    if not endpoint:
        return False, "NOT FOUND — AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT not set"
    if not key:
        return False, "NOT FOUND — AZURE_DOCUMENT_INTELLIGENCE_KEY not set"
    # Do not log values, only lengths
    return True, f"OK — endpoint len {len(endpoint.strip())}, key len {len(key.strip())}"

def get_azure_client():
    """
    Returns DocumentIntelligenceClient or raises with safe message (no key logged).
    """
    endpoint, key, _ = get_azure_credentials()
    if not endpoint or not key:
        raise RuntimeError("Azure credentials not configured — set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and KEY in env (see docs)")
    # Normalize endpoint
    ep = endpoint.strip().rstrip("/") + "/"
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
    except Exception as e:
        raise RuntimeError(f"Azure SDK import failed: {e} — pip install azure-ai-documentintelligence==1.0.0") from e
    try:
        client = DocumentIntelligenceClient(endpoint=ep, credential=AzureKeyCredential(key.strip()))
        return client
    except Exception as e:
        # Do not log key
        raise RuntimeError(f"DocumentIntelligenceClient init failed: {type(e).__name__}: {e} — check endpoint format") from e

def analyze_pdf_bytes(pdf_bytes: bytes, source_filename: str, source_page_number: int = 1, locale: str = "ar") -> List[Dict[str, Any]]:
    """
    Small testable wrapper around:
        client.begin_analyze_document(model_id="prebuilt-layout", body=io.BytesIO(pdf_bytes), locale="ar")
    Preserves deterministic mapping: source filename + source page number -> Azure pageNumber
    Returns list of page dicts with text/lines/confidence/bbox/provenance.
    Never logs key.
    """
    if not pdf_bytes or len(pdf_bytes) < 100:
        raise ValueError("pdf_bytes too small for analyze")
    client = get_azure_client()
    try:
        poller = client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=io.BytesIO(pdf_bytes),
            locale=locale
        )
        result = poller.result(timeout=60)
    except Exception as e:
        # Handle auth without logging key (never log key value, only len)
        msg = str(e)
        if "401" in msg or "Unauthorized" in msg or "InvalidApiKey" in msg or "Access denied" in msg:
            raise RuntimeError(f"Azure authentication failed (401) — check AZURE_DOCUMENT_INTELLIGENCE_KEY for endpoint len {len((get_azure_credentials()[0] or ''))} — {type(e).__name__}: {msg[:200]}") from e
        if "404" in msg:
            raise RuntimeError(f"Azure endpoint not found (404) — check AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT — {type(e).__name__}: {msg[:200]}") from e
        raise

    # Map Azure result pages to provenance
    pages = []
    azure_pages = getattr(result, "pages", []) or []
    # Azure may return content and pages; we extract per page
    for idx, page in enumerate(azure_pages):
        # Azure pageNumber is 1-indexed per document (for single-page PDF, should be 1)
        azure_page_number = getattr(page, "page_number", idx + 1)
        # Extract text lines
        lines = []
        for line in getattr(page, "lines", []) or []:
            content = getattr(line, "content", "")
            polygon = getattr(line, "polygon", None)
            # polygon is list of points [x,y,...]
            lines.append({
                "content": content,
                "polygon": polygon,
                "confidence": getattr(line, "confidence", None)
            })
        # Also get page-level text via result.content or page spans
        # For simplicity, join lines
        page_text = "\n".join([l["content"] for l in lines])
        # Try to get page confidence if available
        # Azure SDK does not expose per-page confidence directly; use lines average
        confidences = [l["confidence"] for l in lines if l["confidence"] is not None]
        avg_conf = sum(confidences)/len(confidences) if confidences else None
        pages.append({
            "source_filename": source_filename,
            "source_page_number": source_page_number,  # Original PDF page number (deterministic)
            "azure_page_number": azure_page_number,
            "text": page_text,
            "lines": lines,
            "confidence": avg_conf,
            "polygon": getattr(page, "polygon", None),
            "width": getattr(page, "width", None),
            "height": getattr(page, "height", None),
            "unit": getattr(page, "unit", None),
            "method": "azure_prebuilt-layout_locale_ar",
            "ocr_applied": True,
            "locale": locale
        })
    # Fallback if Azure returned no pages but has content
    if not pages:
        # Try result.content
        content = getattr(result, "content", "")
        if content:
            pages.append({
                "source_filename": source_filename,
                "source_page_number": source_page_number,
                "azure_page_number": source_page_number,
                "text": content,
                "lines": [],
                "confidence": None,
                "method": "azure_content_fallback",
                "ocr_applied": True,
                "locale": locale
            })
    return pages

def analyze_pdf_file(pdf_path: str | Path, locale: str = "ar") -> List[Dict[str, Any]]:
    """
    For a given PDF file, returns per-page Azure results with provenance.
    This is the full-file wrapper — caller should use scanned-page routing to avoid sending native pages.
    """
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(f"PDF not found: {p}")
    # Read file and send whole document to Azure (Azure handles multi-page)
    # But for page-level provenance with deterministic mapping, we need to handle per-page routing outside.
    # This function sends the whole file as one request (more efficient, preserves page numbers via Azure's page_number)
    data = p.read_bytes()
    # Use wrapper per page? For efficiency, send whole file and then map.
    # However to keep deterministic source_page_number -> Azure pageNumber mapping, we send whole file and then map by index
    client = get_azure_client()
    try:
        poller = client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=io.BytesIO(data),
            locale=locale
        )
        result = poller.result(timeout=120)
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Unauthorized" in msg or "InvalidApiKey" in msg or "Access denied" in msg:
            raise RuntimeError(f"Azure auth failed (401) — check AZURE_DOCUMENT_INTELLIGENCE_KEY for endpoint len {len((get_azure_credentials()[0] or ''))} — {type(e).__name__}: {msg[:200]}") from e
        if "404" in msg:
            raise RuntimeError(f"Azure endpoint not found (404) — check AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT — {type(e).__name__}: {msg[:200]}") from e
        raise

    pages = []
    azure_pages = getattr(result, "pages", []) or []
    # If Azure returns no pages, fallback to content
    if not azure_pages:
        content = getattr(result, "content", "")
        if content:
            # Split content by page markers if available — for now treat as single page
            pages.append({
                "source_filename": str(p),
                "source_page_number": 1,
                "azure_page_number": 1,
                "text": content,
                "lines": [],
                "confidence": None,
                "method": "azure_content_fallback",
                "ocr_applied": True,
                "locale": locale
            })
        return pages

    for idx, page in enumerate(azure_pages):
        azure_page_number = getattr(page, "page_number", idx + 1)
        # Deterministic mapping: Azure pageNumber should equal source_page_number (1-indexed)
        # For whole file, source_page_number == azure_page_number
        source_page_number = azure_page_number
        lines = []
        for line in getattr(page, "lines", []) or []:
            lines.append({
                "content": getattr(line, "content", ""),
                "polygon": getattr(line, "polygon", None),
                "confidence": getattr(line, "confidence", None)
            })
        page_text = "\n".join([l["content"] for l in lines])
        confidences = [l["confidence"] for l in lines if l["confidence"] is not None]
        avg_conf = sum(confidences)/len(confidences) if confidences else None
        pages.append({
            "source_filename": str(p),
            "source_page_number": source_page_number,
            "azure_page_number": azure_page_number,
            "text": page_text,
            "lines": lines,
            "confidence": avg_conf,
            "polygon": getattr(page, "polygon", None),
            "width": getattr(page, "width", None),
            "height": getattr(page, "height", None),
            "unit": getattr(page, "unit", None),
            "method": "azure_prebuilt-layout_locale_ar",
            "ocr_applied": True,
            "locale": locale
        })
    return pages

def is_scanned_or_garbled(page_text: str, garbled_ratio: float) -> bool:
    """
    Determines if a page should be routed to Azure.
    Mirrors logic in run_real_benchmark: len<100 or garbled>0.3
    """
    l = len((page_text or "").strip())
    return l < 100 or garbled_ratio > 0.3

# For testing: create minimal synthetic PDF
def create_synthetic_pdf(text: str = "TenderMind preflight test — Arabic: اختبار") -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), text, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data
