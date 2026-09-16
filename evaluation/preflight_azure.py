"""
Safe Azure Document Intelligence Preflight — TenderMind
Checks endpoint + key WITHOUT printing or logging the secret.
Frozen contract, schemas, thresholds, deterministic BID/REVIEW/NO_BID logic are NOT changed.
"""
import os
import sys

# Load .env if present (optional, never required to contain secrets in repo)
try:
    from dotenv import load_dotenv
    # Load from TenderMind/.env if exists, and from parent
    load_dotenv()
    # Also try explicit path
    from pathlib import Path
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except Exception:
    pass

EXPECTED_ENDPOINT = "https://tendermind-docintel.cognitiveservices.azure.com/"

def get_env(name):
    return os.environ.get(name)

def check_endpoint(endpoint):
    if not endpoint:
        return False, "NOT FOUND — AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT not set in env"
    # Normalize trailing slash
    norm = endpoint.strip()
    # Basic format check
    if not norm.startswith("https://"):
        return False, f"FAIL — endpoint must start with https:// (found length {len(norm)})"
    if "cognitiveservices.azure.com" not in norm:
        return False, f"FAIL — endpoint must contain cognitiveservices.azure.com (found length {len(norm)})"
    # Check expected resource (warning if different, not fail)
    if norm.rstrip("/") + "/" != EXPECTED_ENDPOINT and norm != EXPECTED_ENDPOINT.rstrip("/"):
        # Allow but warn
        return True, f"OK — endpoint found (len {len(norm)}), but differs from expected {EXPECTED_ENDPOINT} — will still test connectivity"
    return True, f"OK — endpoint found (len {len(norm)}), matches expected"

def check_key(key):
    if not key:
        return False, "NOT FOUND — AZURE_DOCUMENT_INTELLIGENCE_KEY not set in env"
    k = key.strip()
    # Azure Document Intelligence keys are typically 32 or 44 chars (hex/base64), never log value
    if len(k) < 16:
        return False, f"FAIL — key too short (len {len(k)})"
    # Common lengths 32 or 44, but accept 32-64
    if len(k) not in (32, 44) and not (32 <= len(k) <= 64):
        return True, f"OK — key found (len {len(k)}) — unusual length but will test connectivity (expected 32 or 44)"
    return True, f"OK — key found (len {len(k)}) — not printed"

def check_sdk():
    try:
        import azure.ai.documentintelligence
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        return True, f"OK — azure-ai-documentintelligence installed (import succeeded)"
    except Exception as e:
        return False, f"FAIL — azure-ai-documentintelligence not installed or import failed: {e} — run pip install -r requirements.txt"

def test_connectivity(endpoint, key):
    """
    Lightweight connectivity test WITHOUT processing a large tender PDF.
    Tries to instantiate DocumentIntelligenceClient and does a minimal analyze call
    with a 1-page in-memory PDF. Handles 401/403 without logging secret.
    Returns (ok, message)
    """
    try:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential
        from azure.core.exceptions import HttpResponseError, ServiceRequestError
    except Exception as e:
        return False, f"SDK import failed: {e}"

    # Normalize endpoint
    ep = endpoint.strip().rstrip("/") + "/"
    try:
        client = DocumentIntelligenceClient(endpoint=ep, credential=AzureKeyCredential(key.strip()))
    except Exception as e:
        return False, f"FAIL — DocumentIntelligenceClient init failed: {type(e).__name__}: {e} — check endpoint format"

    # Create minimal 1-page PDF in memory for test (no tender content, no gold)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), "TenderMind preflight test — Arabic: اختبار", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()
    except Exception as e:
        # Fallback minimal PDF bytes
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    try:
        # Use prebuilt-layout (supports Arabic) with a tiny synthetic PDF (not Sarai)
        import io
        poller = client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=io.BytesIO(pdf_bytes),
            locale="ar"
        )
        # Wait briefly for result (with timeout)
        result = poller.result(timeout=30)
        # If we get here, auth succeeded and model ran
        # Check that result has pages
        pages = len(getattr(result, "pages", []) or [])
        return True, f"OK — Azure authentication succeeded, DocumentIntelligenceClient initialized, test analyze returned {pages} page(s) — Arabic layout supported"
    except Exception as e:
        # Handle auth errors without logging key
        msg = str(e)
        # Check for HTTP status in message
        if "401" in msg or "Unauthorized" in msg or "InvalidApiKey" in msg or "Access denied" in msg:
            return False, f"FAIL — Azure authentication failed (401/403) — key invalid or not for this endpoint (endpoint len {len(ep)}, key len {len(key.strip())}) — error: {type(e).__name__}: {msg[:200]}"
        if "404" in msg or "Resource not found" in msg or "NotFound" in msg:
            return False, f"FAIL — Endpoint not found (404) — check AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is {EXPECTED_ENDPOINT} — error: {type(e).__name__}: {msg[:200]}"
        if "403" in msg:
            return False, f"FAIL — Forbidden (403) — check key is KEY 1 for this resource — error: {type(e).__name__}: {msg[:200]}"
        # Network or other
        if "ServiceRequestError" in type(e).__name__ or "Connection" in msg:
            return False, f"FAIL — Network/Service error — check endpoint and internet: {type(e).__name__}: {msg[:200]}"
        # Other error but still indicates SDK works
        return False, f"FAIL — Test analyze failed: {type(e).__name__}: {msg[:300]} — SDK import OK but analyze failed (may still be auth issue)"

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except: pass
    print("=== TenderMind Azure Document Intelligence — Safe Preflight ===")
    print("Frozen: AI Evaluation Contract v1, schemas, thresholds, deterministic BID/REVIEW/NO_BID — NOT changed")
    print(f"Expected endpoint: {EXPECTED_ENDPOINT}")
    print("Secrets: endpoint and key are read from env, key length is printed, key value is NEVER printed or logged")
    print()

    # 1. Endpoint
    endpoint = get_env("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT") or get_env("AZURE_FORM_RECOGNIZER_ENDPOINT") or get_env("DOCUMENT_INTELLIGENCE_ENDPOINT")
    ok_ep, msg_ep = check_endpoint(endpoint)
    print(f"[1/4] ENDPOINT: {msg_ep}")
    if endpoint:
        print(f"      Endpoint len: {len(endpoint.strip())} — value NOT printed")
    else:
        print(f"      Fix: Set $env:AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=\"{EXPECTED_ENDPOINT}\" (PowerShell) or add to TenderMind/.env")

    # 2. Key
    key = get_env("AZURE_DOCUMENT_INTELLIGENCE_KEY") or get_env("AZURE_FORM_RECOGNIZER_KEY") or get_env("DOCUMENT_INTELLIGENCE_KEY")
    ok_key, msg_key = check_key(key)
    print(f"[2/4] KEY: {msg_key}")
    if key:
        print(f"      Key len: {len(key.strip())} — value NOT printed")
    else:
        print(f"      Fix: Set $env:AZURE_DOCUMENT_INTELLIGENCE_KEY=\"<KEY 1>\" (PowerShell, do NOT paste in chat) or add to TenderMind/.env (git-ignored)")

    # 3. SDK
    ok_sdk, msg_sdk = check_sdk()
    print(f"[3/4] SDK: {msg_sdk}")
    if not ok_sdk:
        print(f"      Fix: pip install -r requirements.txt  (requires azure-ai-documentintelligence==1.0.0)")

    # 4. Connectivity (only if endpoint+key present and SDK ok)
    if ok_ep and ok_key and ok_sdk:
        print(f"[4/4] CONNECTIVITY: Testing DocumentIntelligenceClient with endpoint + key (lightweight 1-page PDF, locale ar)…")
        # Also check that key is not the invalid sk-svcacct-* (which is OpenAI, not Azure)
        if key.strip().startswith("sk-"):
            print(f"      WARNING: Key starts with sk- — this looks like an OpenAI key, not Azure Document Intelligence key (Azure keys are 32/44 hex). Check you used KEY 1 from Azure portal, not OpenAI.")
        ok_conn, msg_conn = test_connectivity(endpoint, key)
        print(f"[4/4] CONNECTIVITY: {msg_conn}")
        if ok_conn:
            print()
            print("Preflight: PASS — Azure Document Intelligence is ready for scanned PDFs, Arabic OCR, and page-level provenance (prebuilt-layout).")
            print("Next: Run full benchmark ONLY after this preflight PASS: python evaluation/run_real_benchmark_v4.py")
        else:
            print()
            print("Preflight: FAIL — fix endpoint/key per message above, then rerun this preflight. Do NOT run full benchmark until PASS.")
    else:
        print(f"[4/4] CONNECTIVITY: SKIPPED — endpoint/key/SDK not all OK — fix above, then rerun")
        print()
        print("Preflight: BLOCKED — configure missing endpoint/key/SDK, then rerun. Do NOT run full benchmark until PASS.")

    # Also warn about OpenAI key still being sk-svcacct
    openai_key = get_env("OPENAI_API_KEY")
    if openai_key and openai_key.strip().startswith("sk-svcacct-"):
        print()
        print("Note: OPENAI_API_KEY is still sk-svcacct-* (invalid for OpenAI per v4). For semantic matching, configure a valid sk-proj-... or Azure OpenAI per docs/AI_Evaluation_Run_Sarai_Real_v4.md — but this preflight does NOT test LLM.")

    print()
    print("Secrets: No key values were printed. Endpoint and key lengths only.")

if __name__ == "__main__":
    main()
