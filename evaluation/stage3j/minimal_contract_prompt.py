"""
Stage 3J — Minimal output-contract prompt (evaluation-only).

Derived from Variant B's semantic intent with the output contract simplified
to a single requirement object. The ONLY experimental difference vs Variant B
is the simplification of the output contract and the removal of
metadata/evidence fields from the model response.

Kept from Variant B (intrinsic, unchanged wording):
- extractor role + grounding rule
- allowed category list + PRIMARY PURPOSE definitions
- UNKNOWN != FALSE rule

Not added: category examples, few-shot examples, "extract all requirements",
priorities, tender-specific terminology, gold IDs/summaries, recall
instructions, new categories.
"""
from evaluation.llm_generic_extraction import LLM_SYSTEM_PROMPT

MINIMAL_CONTRACT_SYSTEM = """You are a tender document extraction assistant. Extract ONLY information explicitly supported by the supplied text.

The supplied text contains exactly ONE requirement. Normalize that single requirement.

Return ONLY valid JSON in exactly this shape:
{"requirements": [{"summary": "...", "category": "...", "mandatory": null, "applicable_entity": null}]}

Rules:
- "requirements" must contain exactly one object.
- "category" must be one of: LEGAL, TECHNICAL, EXPERIENCE, EQUIPMENT, FINANCIAL, SCHEDULE, COMMERCIAL, HSE, QA_QC, PERSONNEL, SUBCONTRACTOR, SUBMISSION, UNKNOWN.
- "summary" must be a human-readable paraphrase grounded only in the supplied text.
- "mandatory" must remain null unless explicitly supported by the source text.
- "applicable_entity" must remain null unless explicitly supported.
- Do not invent facts.
- Do not generate IDs, evidence, source_document, page, provenance, or candidate linkage.
- Return ONLY the JSON object, no other text.

Category definitions (classify by PRIMARY PURPOSE, not keywords):
- TECHNICAL = equipment/specification/performance requirements
- EXPERIENCE = bidder/project experience requirements
- FINANCIAL = financial/commercial qualification requirements
- LEGAL = legal/documentary/legal-status requirements
- SCHEDULE = delivery/completion/time requirements
- HSE = health/safety/environment requirements
- QA_QC = quality assurance/control requirements
- COMMERCIAL = pricing/payment/commercial terms
Classify by PRIMARY PURPOSE, not keywords. Similar 220kV projects is EXPERIENCE even though it contains 220kV/GIS.
"""

PROMPT_VERSION_3J = "Variant B-minimal-contract"


def prompt_hash_3j(prompt: str) -> str:
    import hashlib
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def attach_provenance(requirement: dict, candidate: dict) -> dict:
    """Attach provenance deterministically from the candidate fixture.

    The model is never asked for provenance. Evidence is derived
    deterministically as a 1-to-1 association for this experiment.
    """
    out = dict(requirement)
    out["source_document"] = candidate["source_document"]
    out["page_number"] = candidate["page"]
    out["source_text"] = candidate["source_text"]
    out["candidate_id"] = candidate["candidate_id"]
    out["parent_chunk_id"] = candidate["parent_chunk_id"]
    out["provenance"] = {"quote_en": candidate["source_text"][:200]}
    return out


def derive_evidence(requirement: dict) -> dict:
    """Deterministic 1-to-1 evidence object for this experiment (not model-generated)."""
    return {
        "fact": requirement.get("summary", ""),
        "requirement_id": requirement.get("requirement_id"),
        "source_document": requirement.get("source_document"),
        "page_number": requirement.get("page_number"),
    }
