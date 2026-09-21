"""
Real Tender Runner — TenderMind — Phase 3C
- Generic, no Mobile/Sarai hardcoded business rules
- Tender directory -> Inventory -> Extraction -> Classification -> Deterministic -> LLM -> Validation -> Canonical -> Report
- Usage: python evaluation/run_real_tender.py --tender-dir <path> [--model qwen2.5:3b] [--output <path>] [--max-pages N] [--max-documents N] [--skip-ocr] [--dry-run]
"""
import argparse
import json
import time
import uuid
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.generic_extraction import ingest_tender, classify_documents, extract_voltage_levels, extract_mva_values, extract_deadlines_deterministic
from evaluation.llm_generic_extraction import chunk_documents, call_ollama_for_chunk, parse_llm_json, validate_requirement, validate_evidence, deduplicate_requirements, assign_canonical_ids, get_ollama_model, get_ollama_base_url, check_ollama_available

def parse_args():
    p = argparse.ArgumentParser(description="Real Tender Runner — Generic")
    p.add_argument("--tender-dir", required=True, help="Path to tender directory")
    p.add_argument("--model", default=None, help="Ollama model (default qwen2.5:3b)")
    p.add_argument("--output", default=None, help="Output JSON path")
    p.add_argument("--max-pages", type=int, default=None, help="Max pages to process (for controlled run)")
    p.add_argument("--max-documents", type=int, default=None, help="Max documents to process")
    p.add_argument("--skip-ocr", action="store_true", help="Skip OCR, mark OCR-needed docs as PARTIAL")
    p.add_argument("--dry-run", action="store_true", help="Inventory only, no extraction")
    return p.parse_args()

def main():
    args = parse_args()
    run_id = str(uuid.uuid4())[:8]
    start_wall = time.time()
    print(f"RUN_ID {run_id} tender-dir {args.tender_dir} model {args.model or get_ollama_model()}")

    tender_path = Path(args.tender_dir)
    if not tender_path.exists():
        print(f"ERROR: tender-dir not found: {tender_path}")
        sys.exit(1)

    # Inventory
    print("\n=== Inventory ===")
    import evaluation.run_real_benchmark as rb
    orig_root = rb.ROOT
    rb.ROOT = tender_path
    try:
        inventory = rb.file_inventory()
    finally:
        rb.ROOT = orig_root
    print(f"Documents total: {len(inventory)}")
    # Apply max-documents
    if args.max_documents:
        inventory = inventory[:args.max_documents]
        print(f"  Limited to max-documents {args.max_documents}: {len(inventory)}")
    # Classify
    supported_exts = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".log"}
    supported = 0
    unsupported = 0
    for f in inventory:
        ext = f["extension"]
        if ext in supported_exts:
            supported += 1
        else:
            unsupported += 1
    print(f"Supported: {supported} Unsupported: {unsupported} (DWG, BAK, RAR, JPG, ZIP)")

    if args.dry_run:
        print("Dry-run: inventory only, no extraction")
        print(f"Documents: {len(inventory)} Supported: {supported} Unsupported: {unsupported}")
        return

    # Extraction
    print("\n=== Extraction ===")
    ocr_start = time.time()
    # For each file, call appropriate extraction with failure isolation
    doc_results = {}
    docs_processed = 0
    docs_failed = 0
    docs_partial = 0
    docs_unsupported = 0
    ocr_documents = 0
    ocr_pages = 0
    text_pages = 0
    total_pages = 0
    for f in inventory:
        ext = f["extension"]
        fpath = Path(f["full_path"])
        # Unsupported check
        if ext in [".dwg", ".bak", ".rar", ".zip", ".jpg"]:
            docs_unsupported += 1
            doc_results[f["filename"]] = {"pages": [], "page_count": 0, "total_text_chars": 0, "extraction_method": "UNSUPPORTED", "status": "UNSUPPORTED"}
            continue
        # Max-documents already handled, max-pages will be handled per document
        try:
            # Check skip-ocr
            if args.skip_ocr and "ocr_needed" in f["ocr_needed"].lower() and "yes" in f["ocr_needed"].lower():
                # Mark as PARTIAL, not processed
                docs_partial += 1
                # Still need to create a placeholder
                doc_results[f["filename"]] = {"pages": [{"page_number": 1, "text": "", "method": "skip-ocr", "ocr_applied": False}], "page_count": 1, "total_text_chars": 0, "extraction_method": "skip-ocr", "status": "PARTIAL"}
                continue
            # Call appropriate extraction
            pages = []
            if ext == ".pdf":
                from evaluation.run_real_benchmark import extract_pdf_text
                # Pass ocr_needed_hint based on inventory
                hint = True if "yes" in f["ocr_needed"].lower() else False if "no" in f["ocr_needed"].lower() else None
                if args.skip_ocr:
                    hint = False
                # Apply max-pages
                # For this, we need to handle max-pages at document level
                # If max-pages is set, we will limit pages per document
                pages = extract_pdf_text(fpath, ocr_needed_hint=hint)
                if args.max_pages and len(pages) > args.max_pages:
                    pages = pages[:args.max_pages]
                    docs_partial += 1
                else:
                    docs_processed += 1
                # Count OCR pages
                ocr_pages += sum(1 for p in pages if p.get("ocr_applied"))
                text_pages += sum(1 for p in pages if not p.get("ocr_applied") and len(p.get("text","").strip()) > 50)
            elif ext in [".doc", ".docx"]:
                from evaluation.run_real_benchmark import extract_docx_text
                pages = extract_docx_text(str(fpath))
                docs_processed += 1
            elif ext in [".xls", ".xlsx"]:
                from evaluation.run_real_benchmark import extract_xls_text
                pages = extract_xls_text(str(fpath))
                docs_processed += 1
            elif ext in [".txt", ".log"]:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
                pages = [{"page_number": 1, "text": text, "method": "txt", "ocr_applied": False}]
                docs_processed += 1
            else:
                docs_unsupported += 1
                pages = []
            doc_results[f["filename"]] = {"pages": pages, "page_count": len(pages), "total_text_chars": sum(len(p.get("text","")) for p in pages), "extraction_method": pages[0].get("method", "unknown") if pages else "unknown", "status": "COMPLETE" if pages and any(len(p.get("text","").strip())>50 for p in pages) else "PARTIAL"}
            total_pages += len(pages)
        except Exception as e:
            print(f"  Failed {f['filename']}: {e}")
            docs_failed += 1
            doc_results[f["filename"]] = {"pages": [], "page_count": 0, "total_text_chars": 0, "extraction_method": "FAILED", "status": "FAILED", "error": str(e)[:200]}

    ocr_seconds = time.time() - ocr_start
    print(f"Documents processed: {docs_processed} failed: {docs_failed} partial: {docs_partial} unsupported: {docs_unsupported}")
    print(f"Total pages: {total_pages} OCR pages: {ocr_pages} Text pages: {text_pages}")

    # Classification
    print("\n=== Classification ===")
    classification = {}
    for fname, data in doc_results.items():
        low = fname.lower()
        sample = ""
        for pg in data.get("pages", [])[:1]:
            sample += (pg.get("text","") or "")[:500].lower()
        if any(k in low for k in ["price", "schedule", "boq"]):
            classification[fname] = "BOQ"
        elif any(k in low for k in ["technical", "specification"]) or any(k in sample for k in ["gis", "transformer"]):
            classification[fname] = "TECHNICAL"
        elif "consortium" in low:
            classification[fname] = "LEGAL"
        elif "clarification" in low:
            classification[fname] = "CLARIFICATION"
        elif "addendum" in low:
            classification[fname] = "ADDENDUM"
        elif "drawing" in low or low.endswith(".dwg"):
            classification[fname] = "DRAWING"
        else:
            classification[fname] = "OTHER"
    print(f"Classification: {classification}")

    # Chunking
    print("\n=== Chunking ===")
    chunks = []
    for fname, data in doc_results.items():
        for pg in data.get("pages", []):
            text = pg.get("text","") or ""
            if not text.strip() or len(text.strip()) < 20:
                continue
            # Skip unsupported/failed
            if data.get("status") in ["FAILED", "UNSUPPORTED"]:
                continue
            # Use same chunking as llm_generic_extraction
            # For this runner, create one chunk per page (conservative)
            chunks.append({
                "chunk_id": f"chunk-{len(chunks):04d}",
                "source_document": fname,
                "page_number": pg.get("page_number", 1),
                "text": text[:3000]
            })
    print(f"Chunks total: {len(chunks)}")
    # Apply max-pages already, but also limit chunks for LLM
    # For this runner, limit to 5 chunks for demo to avoid 16*47s
    chunks_for_llm = [c for c in chunks if len(c["text"].strip()) > 50]
    # Skip empty/low-value chunks
    empty_chunks = [c for c in chunks if len(c["text"].strip()) < 50]
    print(f"Chunks skipped empty: {len(chunks) - len(chunks_for_llm)}")
    print(f"Chunks sent to LLM: {len(chunks_for_llm)}")

    # Deterministic extraction
    print("\n=== Deterministic Extraction ===")
    from evaluation.generic_extraction import extract_voltage_levels, extract_mva_values, extract_deadlines_deterministic
    combined_text = "\n".join(c["text"] for c in chunks)
    voltages = extract_voltage_levels(combined_text)
    mvas = extract_mva_values(combined_text)
    deadlines = extract_deadlines_deterministic(combined_text)
    print(f"Voltages: {voltages}")
    print(f"MVA: {mvas}")
    try:
        print(f"Deadlines: {deadlines[:2]}")
    except UnicodeEncodeError:
        print(f"Deadlines: {len(deadlines)} found")

    # Semantic extraction (LLM)
    print("\n=== Semantic Extraction (LLM) ===")
    ok, msg = check_ollama_available()
    print(f"Ollama: {msg}")
    llm_reqs = []
    llm_evs = []
    if ok:
        for chunk in chunks_for_llm[:5]:  # Limit to 5 for demo
            from evaluation.llm_generic_extraction import call_ollama_for_chunk, parse_llm_json, validate_requirement
            result = call_ollama_for_chunk(chunk)
            if not result:
                print(f"  {chunk['chunk_id']}: no response")
                continue
            parsed, status = parse_llm_json(result["raw"])
            print(f"  {chunk['chunk_id']}: parse {status}")
            if parsed and "requirements" in parsed:
                for req in parsed["requirements"]:
                    if "candidate_id" in req and "requirement_id" not in req:
                        req["requirement_id"] = req["candidate_id"]
                    # Add provenance from chunk
                    if not req.get("source_document"):
                        req["source_document"] = chunk["source_document"]
                    if not req.get("page_number"):
                        req["page_number"] = chunk["page_number"]
                    req["prediction_source_chunk_id"] = chunk["chunk_id"]
                    ok_v, _ = validate_requirement(req, chunk)
                    if ok_v:
                        llm_reqs.append(req)
        print(f"LLM requirements: {len(llm_reqs)}")
    else:
        print("LLM unavailable, skipping semantic extraction")

    # Validation
    print("\n=== Validation ===")
    # Check canonical IDs
    from evaluation.llm_generic_extraction import deduplicate_requirements, assign_canonical_ids
    if llm_reqs:
        deduped, _ = assign_canonical_ids(llm_reqs, [])
        print(f"Deduped: {len(llm_reqs)} -> {len(deduped)}")
        # Check unique
        req_ids = [r["requirement_id"] for r in deduped]
        print(f"Canonical IDs unique: {len(req_ids) == len(set(req_ids))}")
    else:
        print("No LLM requirements to validate")

    # Report
    print("\n=== Run Report ===")
    report = {
        "run_id": run_id,
        "tender_path": str(tender_path),
        "documents_total": len(inventory),
        "supported": len([f for f in inventory if f["extension"] in [".pdf",".doc",".docx",".xls",".xlsx",".txt",".log"]]),
        "unsupported": unsupported,
        "documents_processed": docs_processed,
        "documents_failed": docs_failed,
        "documents_partial": docs_partial,
        "total_pages": total_pages,
        "ocr_pages": ocr_pages,
        "text_pages": text_pages,
        "chunks_total": len(chunks),
        "chunks_sent_to_llm": len(chunks_for_llm[:5]),
        "chunks_skipped_empty": len(chunks) - len(chunks_for_llm),
        "llm_requirements": len(llm_reqs) if 'llm_reqs' in locals() else 0,
        "wall_clock_seconds": time.time() - start_wall,
    }
    print(json.dumps(report, indent=2))
    # Save report
    out_path = Path(args.output) if args.output else Path(f"evaluation/runs/{run_id}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()
