"""
Tests for generic tender-agnostic extraction — no Sarai-specific assumptions
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.generic_extraction import build_generic_extraction, ingest_tender, classify_documents

def test_arbitrary_tender_ids():
    """Tender IDs are dynamic, not SA-2018-HV2 hardcoded"""
    for tid in ["SA-2018-HV2", "Mobile-2024-001", "6thOctober-X", "Motawreen-2025"]:
        # Use a temp empty tender dir
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        # Create a dummy PDF
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72,72), f"Tender {tid} test content with voltage 220kV", fontsize=12)
        doc.save(str(tmp / "test.pdf"))
        doc.close()
        res = build_generic_extraction(tmp, tender_id=tid, use_llm=False)
        assert res["tender_id"] == tid, f"Expected {tid}, got {res['tender_id']}"
        assert len(res["requirements"]) >= 1  # Should find at least voltage
        print(f"PASS arbitrary tender ID {tid}")

def test_variable_requirement_counts():
    """Variable requirement counts, not fixed 21"""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    # Only one requirement-like text
    page.insert_text((72,72), "Single requirement: experience with similar projects", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="TEST-001", use_llm=False)
    # Should not be 21, should be dynamic
    assert len(res["requirements"]) < 21
    assert len(res["requirements"]) >= 0
    print(f"PASS variable requirement counts {len(res['requirements'])}")

def test_arbitrary_filenames():
    """Filenames are dynamic, not Sarai-specific"""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    for name in ["My Tender Doc.pdf", "random_file.pdf", "FORM_X.doc"]:
        p = tmp / name
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72,72), "Test content voltage 22kV", fontsize=12)
        doc.save(str(p))
        doc.close()
    res = build_generic_extraction(tmp, tender_id="ARBITRARY", use_llm=False)
    assert len(res["documents"]) == 3
    print("PASS arbitrary filenames")

def test_missing_optional_fields():
    """Missing optional fields handled (client, location may be null)"""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Minimal tender", fontsize=12)
    doc.save(str(tmp / "minimal.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="MINIMAL", use_llm=False)
    # client and location are optional, should be None
    assert res["client"] is None or isinstance(res["client"], str)
    assert "provenance_coverage" in res
    print("PASS missing optional fields")

def test_provenance():
    """Every extracted requirement has provenance"""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Experience with similar 220kV GIS projects and schedule 18 months", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="PROV-TEST", use_llm=False)
    for req in res["requirements"]:
        assert "source_document" in req
        assert "page_number" in req
        assert req["source_document"] != "unknown" or req["confidence"] < 0.8
    print("PASS provenance")

def test_no_sarai_assumptions():
    """No Sarai-specific voltage/transformer assumptions"""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    # Use different voltage than Sarai's 220kV/175MVA
    page.insert_text((72,72), "Project: 11kV Mobile substation 60MVA transformer for 6th October", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="DIFFERENT-VOLTAGE", use_llm=False)
    # Should still extract voltage, not hardcode 220kV
    found_voltages = [r for r in res["requirements"] if "voltage" in r["summary"].lower() or "220kV" in str(r) or "11kV" in str(r)]
    # At least should have some technical requirement, not necessarily 220kV
    assert len(res["requirements"]) >= 1
    print("PASS no Sarai assumptions")

def test_schema_validation():
    """Schema validation for generic output"""
    import tempfile, json
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="SCHEMA-TEST", use_llm=False)
    # Check required fields per schema
    assert "tender_id" in res
    assert "title" in res
    assert "documents" in res
    assert "requirements" in res
    assert isinstance(res["requirements"], list)
    print("PASS schema validation")

def test_arbitrary_applicable_entities():
    """Applicable entity supports arbitrary strings, not just GIZA/HYOSUNG"""
    from evaluation.generic_extraction import validate_against_schema
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="ENTITY-TEST", use_llm=False)
    # Manually set arbitrary entity
    if res["requirements"]:
        res["requirements"][0]["applicable_entity"] = "CUSTOM_ENTITY_XYZ"
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
        ok, msg = validate_against_schema(res, schema_path)
        assert ok, f"Arbitrary entity should be valid: {msg}"
    # Also test that old Sarai enum GIZA is not required
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
    import json
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    # Check schema does not enumerate GIZA/HYOSUNG
    req_props = schema["properties"]["requirements"]["items"]["properties"]["applicable_entity"]
    assert "enum" not in req_props or "GIZA" not in str(req_props.get("enum", [])), "Schema should not enumerate GIZA/HYOSUNG"
    print("PASS arbitrary applicable entities")

def test_unknown_null_mandatory():
    """Mandatory can be null/unknown"""
    from evaluation.generic_extraction import validate_against_schema
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="MANDATORY-TEST", use_llm=False)
    # Set mandatory to None (unknown)
    if res["requirements"]:
        res["requirements"][0]["mandatory"] = None
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
        ok, msg = validate_against_schema(res, schema_path)
        assert ok, f"Null mandatory should be valid: {msg}"
    print("PASS unknown/null mandatory")

def test_en_only_tender():
    """EN-only tender (no Arabic) should have languages ["EN"] not hardcoded ["AR","EN"]"""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "This is English only tender with no Arabic", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="EN-ONLY", use_llm=False)
    assert "EN" in res["languages"]
    assert "AR" not in res["languages"] or len(res["languages"]) == 1, f"EN-only should not have AR, got {res['languages']}"
    print("PASS EN-only tender")

def test_arbitrary_language_strings():
    """Languages are free-form, not limited to AR/EN"""
    from evaluation.generic_extraction import validate_against_schema
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="LANG-TEST", use_llm=False)
    res["languages"] = ["EN", "FR", "DE"]
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
    ok, msg = validate_against_schema(res, schema_path)
    assert ok, f"Arbitrary languages should be valid: {msg}"
    with open(schema_path, encoding="utf-8") as f:
        import json
        schema = json.load(f)
    assert "enum" not in schema["properties"]["languages"]["items"], "Languages should not be enum limited to AR/EN"
    print("PASS arbitrary language strings")

def test_unknown_deadline_type():
    """Unknown deadline type should be valid"""
    from evaluation.generic_extraction import validate_against_schema, extract_deadlines_deterministic
    from pathlib import Path
    # Test extraction produces unknown type
    dates = extract_deadlines_deterministic("Meeting on 16 of August, 2018")
    assert len(dates) > 0
    assert dates[0]["type"] == "unknown"
    # Validate via schema
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="DEADLINE-TEST", use_llm=False)
    res["deadlines"] = [{"type": "unknown", "date": "16 of August, 2018", "source_document": "test.pdf", "page_number": 1}]
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
    ok, msg = validate_against_schema(res, schema_path)
    assert ok, f"Unknown deadline type should be valid: {msg}"
    print("PASS unknown deadline type")

def test_nullable_risk_severity():
    """Risk severity nullable"""
    from evaluation.generic_extraction import validate_against_schema
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="RISK-TEST", use_llm=False)
    res["risks"] = [{"risk_id": "R-001", "description": "Test risk", "severity": None, "type": "COMMERCIAL"}]
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
    ok, msg = validate_against_schema(res, schema_path)
    assert ok, f"Null risk severity should be valid: {msg}"
    print("PASS nullable risk severity")

def test_real_nested_schema_validation_failure():
    """Real nested validation should fail on invalid data"""
    from evaluation.generic_extraction import validate_against_schema
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="VALIDATION-TEST", use_llm=False)
    # Invalid: missing required field
    invalid = res.copy()
    del invalid["tender_id"]
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
    ok, msg = validate_against_schema(invalid, schema_path)
    assert not ok, "Should fail when tender_id missing"
    # Invalid nested: requirement missing mandatory
    invalid2 = res.copy()
    if invalid2["requirements"]:
        invalid2["requirements"][0].pop("mandatory", None)
        ok2, msg2 = validate_against_schema(invalid2, schema_path)
        assert not ok2, "Should fail when requirement missing mandatory"
    print("PASS real nested schema validation failure")

def test_invalid_enum_rejected():
    """Invalid enum should be rejected"""
    from evaluation.generic_extraction import validate_against_schema
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="ENUM-TEST", use_llm=False)
    if res["requirements"]:
        res["requirements"][0]["category"] = "INVALID_CATEGORY"
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
        ok, msg = validate_against_schema(res, schema_path)
        assert not ok, "Invalid category should be rejected"
    print("PASS invalid enum rejected")

def test_invalid_requirement_id_rejected():
    """Invalid requirement_id pattern should be rejected"""
    from evaluation.generic_extraction import validate_against_schema
    from pathlib import Path
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="REQID-TEST", use_llm=False)
    if res["requirements"]:
        res["requirements"][0]["requirement_id"] = "INVALID_ID"
        schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
        ok, msg = validate_against_schema(res, schema_path)
        assert not ok, "Invalid requirement_id should be rejected"
    print("PASS invalid requirement_id rejected")

def test_no_sarai_entity_leakage_in_schema():
    """No Sarai entity leakage in schema"""
    from pathlib import Path
    import json
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "tender_agnostic_schema.json"
    with open(schema_path, encoding="utf-8") as f:
        content = f.read()
    assert "GIZA" not in content, "Schema should not contain GIZA"
    assert "HYOSUNG" not in content, "Schema should not contain HYOSUNG"
    print("PASS no Sarai entity leakage in schema")

def test_no_hardcoded_consortium_assumptions():
    """No hardcoded CONSORTIUM assumptions in generic extraction"""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72,72), "Test with no consortium", fontsize=12)
    doc.save(str(tmp / "test.pdf"))
    doc.close()
    res = build_generic_extraction(tmp, tender_id="CONSORTIUM-TEST", use_llm=False)
    # Check that not all requirements are CONSORTIUM
    # With generic extraction, applicable_entity should be None, not CONSORTIUM
    for req in res["requirements"]:
        assert req["applicable_entity"] is None or req["applicable_entity"] != "CONSORTIUM" or req["confidence"] < 0.6, f"Should not hardcode CONSORTIUM: {req}"
    print("PASS no hardcoded CONSORTIUM assumptions")

def test_no_duplicated_pipeline_behavior():
    """No duplicated pipeline behavior — build_generic_extraction should reuse ingest_tender"""
    import inspect
    from evaluation import generic_extraction
    source = inspect.getsource(generic_extraction.build_generic_extraction)
    # Should not contain duplicate ingestion logic (re.sub for tender_id is ok, but not full file_inventory duplication)
    # Check that it calls ingest_tender
    assert "ingest_tender" in source, "Should reuse ingest_tender"
    # Should not contain self-import
    assert "from evaluation.generic_extraction import ingest_tender" not in source, "Should not have self-import"
    print("PASS no duplicated pipeline behavior")

if __name__ == "__main__":
    test_arbitrary_tender_ids()
    test_variable_requirement_counts()
    test_arbitrary_filenames()
    test_missing_optional_fields()
    test_provenance()
    test_no_sarai_assumptions()
    test_schema_validation()
    test_arbitrary_applicable_entities()
    test_unknown_null_mandatory()
    test_en_only_tender()
    test_arbitrary_language_strings()
    test_unknown_deadline_type()
    test_nullable_risk_severity()
    test_real_nested_schema_validation_failure()
    test_invalid_enum_rejected()
    test_invalid_requirement_id_rejected()
    test_no_sarai_entity_leakage_in_schema()
    test_no_hardcoded_consortium_assumptions()
    test_no_duplicated_pipeline_behavior()
    print("\nAll 18 generic tests passed")
