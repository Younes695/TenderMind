"""Stage 5K — deterministic fallback for requirements the model left UNKNOWN.

Runs ONLY when the model answered UNKNOWN; a model category is never
overridden. Each rule is a strong, unambiguous cue from the same taxonomy the
prompt defines (app/pipeline/prompts.py), checked in order from the most
specific (contract clauses, money, safety, time) to the broadest (technical
equipment words). No cue -> stays UNKNOWN, so nothing is guessed.
The requirement is marked extraction_method "two-stage+rule" so the UI and
audits can tell it apart from a model answer.
"""
from __future__ import annotations

import re
from typing import Optional

_W = lambda p: re.compile(p, re.IGNORECASE)

RULES = [
    # contract definitions ("Services" means ...) and contract termination clauses
    ("LEGAL", _W(r"[\"\u201c][A-Za-z ]{2,40}[\"\u201d] means\b|\btermination (at|for) (company|owner|the )?\s?convenience|\b(date|notice|effect|consequences?) of termination|\btermination under paragraph|\bterminated works?\b")),
    ("SUBMISSION", _W(r"\b(bid|tender|proposal|offer)s?\b.{0,40}\b(submi(t|ssion)|envelope|opening|copies)\b|"
                      r"\bsealed envelope|\bbid opening\b|\btechnical (and|&) commercial (proposal|offer)s?\b")),
        ("HSE", _W(r"\b(safety|health|environmental (protection|impact|management|requirements?)|hse|ppe|hazard(ous)?|accident|"
               r"first aid|permit to work|waste disposal|danger)\b")),
    ("QA_QC", _W(r"\b(quality (assurance|control|plan|management)|qa/?qc|iso 9001|inspection and test plan|itp)\b")),
    ("COMMERCIAL", _W(r"\b(liquidated damages|payment|invoice|price|pricing|prices|priced|cost of|registration cost|"
                      r"currency|customs dut(y|ies)|saudi riyal|sar\b|retention|bond|guarantee|letter of credit|penalt(y|ies)|"
                      r"\btax(es)?\b|vat\b|local content|lc scorecard|in-kingdom|advance payment|bill of quantities)")),
    ("LEGAL", _W(r"\b(terminat(e|ion) (of|for) (the |this )?(contract|agreement|work)|termination (for|at) (the )?(convenience|default)|terminate (this|the) (contract|agreement)|force majeure|indemn(ity|ify)|liabilit(y|ies)|dispute|arbitration|"
                 r"governing law|claims?\b|change order|variation|constitute a change|breach|"
                 r"assignment of|intellectual property|confidential(ity)?|warrant(y|ies)|insurance|"
                 r"power of attorney|joint venture|consortium|excusable delay|suspension of)\b")),
    ("SUBCONTRACTOR", _W(r"\b(subcontract(ing|ed)? (of |the )?(works?|limit)|approv\w* (of |the )?subcontractors?|subcontractors? (approval|qualifications?|list)|subcontract more than|percentage .{0,30}subcontract)")),
    ("PERSONNEL", _W(r"\b(project manager|site engineer|key personnel|curriculum vitae|cvs?\b|"
                     r"staff qualifications?|resident engineer|saudi(zation| nationals))\b")),
    ("SCHEDULE", _W(r"\b(completion (date|period|time)|delivery (period|time|date)|milestones?|"
                    r"time schedule|project schedule|programme of works|level-?\d schedule|"
                    r"within \d+ (days|weeks|months)|critical path|primavera|baseline schedule)\b")),
    ("TECHNICAL", _W(r"\b(\d+(\.\d+)?\s?kv|kva|mva|gis|ais|switchgear|transformers?|substation|busbar|"
                     r"breaker|disconnector|relay|protection|scada|rtu|telecom|fiber|fibre|cable|conductor|"
                     r"earthing|grounding|insulator|bay|feeder|capacitor|reactor|battery|charger|"
                     r"ct|cts|vt|vts|pt|metering|voltage|current|reactive power|undervoltage|overvoltage|"
                     r"harmonic|frequency|panel|cubicle|foundation|steel|concrete|civil|drawing|layout|"
                     r"data schedule|technical data|tmss|sec standard|specification|iec|ieee|ansi|"
                     r"type test|factory test|commissioning|installation|hvac|lighting|fire alarm|"
                     r"trench|duct|road|fence|building|terminations?|splice|osp)s?\b")),
]


def rule_category(source_text: str, summary: str = "") -> Optional[str]:
    """The document's own words first; the model's paraphrase only as a fallback
    (it sometimes adds words that are not in the source, e.g. 'payment')."""
    for t in (source_text or "", summary or ""):
        for cat, rx in RULES:
            if rx.search(t):
                return cat
    return None


def apply_to_stored_analysis(db, tender_id: str) -> int:
    """Apply the fallback to an analysis stored before Stage 5K (no re-run), then
    refresh the requirement rows and review items. Returns rows reclassified."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.models import TenderAnalysis
    a = (db.query(TenderAnalysis).filter(TenderAnalysis.tender_id == tender_id)
         .order_by(TenderAnalysis.created_at.desc()).first())
    if a is None:
        return 0
    reqs, changed = list(a.requirements or []), 0
    for r in reqs:
        if (r.get("category") or "").upper() == "UNKNOWN":
            cat = rule_category(r.get("source_text") or "", r.get("summary") or "")
            if cat:
                r["category"], r["extraction_method"] = cat, "two-stage+rule"
                changed += 1
    if changed:
        a.requirements = reqs
        flag_modified(a, "requirements")
        db.commit()
        from app.engines.tender_bridge import sync_requirements
        from app.issues import sync_issues
        sync_requirements(db, tender_id)
        sync_issues(db, tender_id)
    return changed
