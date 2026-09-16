# Recommended AI Pipeline Architecture — v1 (Evaluation Phase)

**Evidence-driven, deterministic decision — LLM assists extraction, not decision.**

```
[1] Intake
    PDF/Doc/ZIP → Validation → Malware scan → Language detect (AR/EN)

[2] Document Intelligence (Arabic + Page Provenance)
    ├── Native text: PyMuPDF (bbox + font)
    ├── Scanned: Azure AI Document Intelligence / AWS Textract (Arabic OCR, confidence per block)
    ├── Layout: Heading/table detection (Microsoft Table Transformer)
    └── Output: schemas/document_extraction_schema.json + page_number + bbox + checksums

[3] Requirement Extraction (Arabic LLM + Rules)
    ├── Input: Page JSON + section headings (Arabic procurement lexicon: كراسة الشروط، تصنيف المقاولين، خطاب الضمان)
    ├── Model: Arabic-capable LLM (Jais 30B / GPT-4o Arabic) with constrained JSON output (requirement_schema.json)
    ├── Rules: category enum, mandatory detection (يجب/إلزامي), HARD_GATE vs EXPERIENCE, applicable_entity inference
    ├── Output: Requirement objects + confidence + source_spans (Arabic quote + bbox)
    └── Gate: Human review diff vs gold (21 requirements)

[4] Company KB Ingestion → Evidence Extraction
    ├── Chunk: page/section, keep doc+page+valid_until
    ├── Embed: Arabic-capable (Jais embeddings / Arctic)
    ├── Extract: Evidence objects with applicable_entity + valid_until + reusable + provenance
    └── Store: Evidence + CompanyDocument (chunked with page/section)

[5] Evidence Matching (Hybrid Retrieval + Deterministic Engine)
    ├── Retrieve: Hybrid keyword (Arabic normalization) + semantic (embeddings) + filter (entity/validity/reusable)
    ├── Rerank: Cross-encoder
    ├── Match: Explicit EvidenceMatch table (no implicit OEM→type-test)
    └── Evaluate: app/engines/status.py → PASS/FAIL/MISSING/REVIEW + conflicts[] + expired + applicability_mismatch

[6] Risk Engine (Rule-based)
    ├── Input: Commercial/Schedule clauses → 7 Sarai risks (fixed-price, FX, LD, guarantee...)
    └── Output: Risk objects, always REVIEW

[7] Decision Engine (Deterministic — NOT LLM)
    ├── Input: statuses + risks → hierarchy §6
    └── Output: Decision + build_explanation() (§6 + explanation_schema.json)

[8] Explainability
    ├── Build: DecisionExplanation (decision/confidence/summary/hard_failures/missing/risks/supporting/conflicts/rules/provenance_chain)
    ├── Export: GET /export + GET /explanation + GET /audit
    └── UI: Tender → Requirements → Evidence → Decision → Missing Checklist → Audit (Requirement→Evidence→Source→Page→Rule→Decision)

[9] Evaluation Harness
    ├── Gold: evaluation/sarai_gold_dataset.json (21 REQ + 4 E + 7 Risks + 13 adversarial)
    ├── Run: status.py + decision.py + explanation.py same engines
    └── Metrics: §7 — F1s, provenance completeness, conflict F1, decision accuracy
```

**Key Principles:**
- **Arabic preservation:** Always keep `text_ar` + normalized + translation; provenance requires Arabic quote + bbox.
- **Deterministic decision:** LLM never decides BID/NO_BID — `decision.py` hierarchy does.
- **Same engines for eval & prod:** No separate AI path — ensures measured accuracy is deployed accuracy.
- **Human-in-loop:** Review gate after requirement extraction + before submission (Etimad remains human-approved).

**Tech Choices (v1 recommendation):**
- OCR: Azure AI Document Intelligence (best Arabic table) — fallback AWS Textract.
- LLM: Jais for Arabic + GPT-4o for bilingual (constrained JSON via function calling).
- Embeddings: Jais / Arctic Arabic.
- Vector: pgvector (when scaling beyond SQLite) — tenant-isolated.
- Orchestration: FastAPI + Celery/Redis for async doc processing (future).

**What NOT to build yet:** Agent swarm, multi-country connectors, proposal generation — vertical slice only.
