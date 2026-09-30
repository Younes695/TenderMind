"""Stage 5H — regression: the Turaif run (1,580 pages, 15 min of extraction) was
thrown away at persistence because classify_documents returned "SCHEDULE", a
value the analysis schemas did not allow. Every class the classifier can emit
must be accepted by both schemas."""
import inspect
import json
import re
from pathlib import Path

from evaluation import generic_extraction as ge

ROOT = Path(__file__).resolve().parents[1]


def _emitted_classes():
    src = inspect.getsource(ge.classify_documents)
    return set(re.findall(r'classification\[fname\]\s*=\s*"([A-Z_]+)"', src))


def test_every_document_class_is_allowed_by_both_schemas():
    classes = _emitted_classes()
    assert "SCHEDULE" in classes and len(classes) >= 8
    for name in ("tender_agnostic_schema.json", "tender_agnostic_schema_2stage.json"):
        text = (ROOT / "schemas" / name).read_text(encoding="utf-8")
        schema = json.loads(text)
        enums = re.findall(r'"document_type"\s*:\s*\{[^}]*?"enum"\s*:\s*\[([^\]]*)\]', text, re.S)
        assert enums, name
        allowed = set(re.findall(r'"([A-Z_]+)"', enums[0]))
        assert classes <= allowed, (name, classes - allowed)


def test_schedule_document_passes_validation(tmp_path):
    doc_results = {"Signature Document.DOC": {"pages": [{"page_number": 1,
        "text": "SCHEDULE C - PAYMENT. The schedule of payments shall follow project portions.", "method": "doc"}],
        "page_count": 1, "total_text_chars": 80, "status": "COMPLETE"}}
    out = ge.build_generic_extraction(tmp_path, tender_id="T-SCHED", doc_results=doc_results)
    assert out["documents"][0]["document_type"] == "SCHEDULE"
    ok, msg = ge.validate_against_schema(out, ROOT / "schemas" / "tender_agnostic_schema.json")
    assert ok, msg
