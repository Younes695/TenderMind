"""Stage 4E tests (fast: registry, lanes, structured normalization, workers)."""
import io
import json
from pathlib import Path

import pytest

from app.pipeline import capability_tiers as CT
from app.pipeline import structured_data as SD
from app.pipeline.contracts import StructuredTable

P = Path(__file__).resolve().parents[1]
E = P / "evaluation" / "stage4e"


def test_capability_inventory_complete_and_classified():
    inv = json.loads((E / "capability_inventory.json").read_text(encoding="utf-8"))["inventory"]
    assert len(inv) >= 40
    required = {"capability_name", "ai_required", "recommended_implementation", "input",
                "output", "provenance_source", "current_status", "evidence",
                "future_model_requirement", "parallelizable", "expected_workload_frequency",
                "unresolved"}
    for c in inv:
        assert required <= set(c), c["capability_name"]
        assert c["ai_required"] in ("YES", "NO", "OPTIONAL", "HYBRID")
    # no invented severity/impact assignments (the out-of-scope entry names the
    # concept only to permanently refuse it — that naming is required honesty)
    blob = json.dumps(inv)
    assert '"severity": "high"' not in blob
    assert '"severity": "medium"' not in blob
    assert '"severity": "low"' not in blob
    assert '"business_impact":' not in blob


def test_no_arbitrary_scores():
    blob = (E / "capability_inventory.json").read_text(encoding="utf-8").lower()
    assert '"score"' not in blob and '"rating"' not in blob


def test_tier_mapping_abstract_no_hardcoded_models():
    for cap in ("REQUIREMENT_NORMALIZATION", "RECONCILIATION", "SYNTHESIS"):
        a = CT.tier_assignment(cap)
        assert a["tier"] in ("FAST_LOCAL", "STRONG_LOCAL", "API_FUTURE")
    assert CT.tier_assignment("NOPE")["status"] == "NOT_CONFIGURED"
    src = Path(CT.__file__).read_text(encoding="utf-8")
    # concrete names live ONLY in the env-overridable default table, never in
    # mapping logic
    logic = "\n".join(l for l in src.splitlines()
                      if "TIER_DEFAULTS" not in l and "TIER_ENV" not in l)
    for model in ("qwen2.5:3b", "gemma3", "phi4", "qwen3", "gemini"):
        assert model not in logic
    assert CT.tier_model(CT.CapabilityTier.FAST_LOCAL) == "qwen2.5:3b"


def test_tier_env_override():
    assert CT.tier_model(CT.CapabilityTier.STRONG_LOCAL) == ""
    import os
    os.environ["TENDERMIND_TIER_STRONG_MODEL"] = "future-x"
    try:
        assert CT.tier_model(CT.CapabilityTier.STRONG_LOCAL) == "future-x"
    finally:
        del os.environ["TENDERMIND_TIER_STRONG_MODEL"]


def test_lane_contracts_stable():
    assert set(CT.LANES) == {"LANE_A_REQUIREMENT_INTELLIGENCE", "LANE_B_COMMERCIAL_SCHEDULE",
                             "LANE_C_COMPLIANCE_GAP_AMBIGUITY",
                             "LANE_D_CROSS_DOCUMENT_RECONCILIATION",
                             "LANE_E_SYNTHESIS_MANAGEMENT"}
    m = CT.lane_manifest()
    assert m["LANE_E_SYNTHESIS_MANAGEMENT"]["output"].startswith("cited")
    assert "NEVER" in CT.LANES["LANE_E_SYNTHESIS_MANAGEMENT"].output_contract
    file_manifest = json.loads((E / "lane_manifest.json").read_text(encoding="utf-8"))
    assert set(file_manifest) == set(CT.LANES)


def test_worker_config_bounded_conservative():
    w = CT.load_worker_config({})
    assert (w.max_workers, w.enabled) == (2, False)
    assert CT.load_worker_config({"TENDERMIND_MAX_AI_WORKERS": "99"}).max_workers == 8
    assert CT.load_worker_config({"TENDERMIND_MAX_AI_WORKERS": "0"}).max_workers == 1
    assert CT.load_worker_config({"TENDERMIND_WORKERS_ENABLED": "1"}).enabled is True


def test_boq_normalizer_generic_bilingual():
    table = StructuredTable(
        source_document="sched.xlsx", sheet="Price",
        columns=["Item ", "Description\nالوصف ", "Unite\nالوحدة ", "Quantity\nالكمية ",
                 "Material unit price (LE)\nسعر الوحدة", "Total material price (LE)\nالاجمالى"],
        rows=[{"Item ": "1A", "Description\nالوصف ": "Three phase breaker",
               "Unite\nالوحدة ": "Nos.", "Quantity\nالكمية ": "6",
               "Material unit price (LE)\nسعر الوحدة": "", "Total material price (LE)\nالاجمالى": ""},
              {"Item ": "", "Description\nالوصف ": "", "Unite\nالوحدة ": "",
               "Quantity\nالكمية ": "", "Material unit price (LE)\nسعر الوحدة": "",
               "Total material price (LE)\nالاجمالى": ""}],
        row_count=2)
    items = SD.normalize_boq_table(table)
    assert len(items) == 1
    it = items[0]
    assert (it.item, it.description, it.unit, it.quantity) == ("1A", "Three phase breaker", "Nos.", "6")
    assert it.location == "Price!R2" and it.source_document == "sched.xlsx"


def test_boq_refuses_non_table():
    table = StructuredTable(source_document="f.xlsx", sheet="Cover",
                            columns=["Title", "Date"], rows=[{"Title": "x", "Date": "y"}], row_count=1)
    assert SD.normalize_boq_table(table) == []


def test_mobile_boq_end_to_end():
    buf = io.BytesIO()
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Item ", "Description", "Unite", "Quantity", "Material unit price (LE)", "Total material price (LE)"])
    ws.append(["1A", "Three (3) single phase circuit breakers", "Nos.", "6", "", ""])
    wb.save(buf)
    buf.name = "mobile.xlsx"
    buf.seek(0)
    tables = SD.read_structured(buf)
    assert len(tables) == 1
    items = SD.normalize_boq_table(tables[0])
    assert len(items) == 1 and items[0].quantity == "6" and items[0].location == "Sheet1!R2"


def test_structured_provenance_lineage():
    table = StructuredTable(source_document="d.xlsx", sheet="S", columns=["Description", "Quantity"],
                            rows=[{"Description": "Cable", "Quantity": "10"}], row_count=1)
    (it,) = SD.normalize_boq_table(table)
    assert it.source_document == "d.xlsx" and it.location == "S!R2"


def test_no_tender_specific_production_rules():
    src = Path(SD.__file__).read_text(encoding="utf-8")
    for token in ("Mobile", "Motawreen", "Sarai", "October", "FORM D", "6th"):
        assert token not in src


def test_telemetry_additive_fields_default():
    from app.pipeline.jobs import JobTelemetry
    t = JobTelemetry()
    d = t.to_dict()
    assert (d["lane"], d["capability_tier"], d["max_workers"]) == ("", "", 1)
    assert (d["structured_tables"], d["structured_line_items"]) == (0, 0)


def test_no_production_auto_routing():
    import app.processing as proc
    assert proc.LLM_MODEL == "qwen2.5:3b"
    w = CT.load_worker_config({})
    assert w.enabled is False  # workers (and any routing use) default OFF


def test_bilingual_split_generic():
    en, ar = SD.split_bilingual("Three phase breaker قاطع ثلاثي")
    assert en == "Three phase breaker" and ar == "قاطع ثلاثي"
    en, ar = SD.split_bilingual("Plain english only")
    assert (en, ar) == ("Plain english only", "")
    en, ar = SD.split_bilingual("")
    assert (en, ar) == ("", "")


def test_boq_populates_arabic_segment():
    table = StructuredTable(
        source_document="sched.xlsx", sheet="S1",
        columns=["Description", "Quantity"],
        rows=[{"Description": "Supply of GIS switchgear توريد مفاتيح", "Quantity": "2"}],
        row_count=1)
    (it,) = SD.normalize_boq_table(table)
    assert it.description == "Supply of GIS switchgear توريد مفاتيح"
    assert it.description_ar == "توريد مفاتيح"


def test_package_record_shapes():
    from app.pipeline.contracts import (
        AddendumRecord, ClarificationRecord, EquipmentRecord, ProjectExperienceRecord)
    # Sarai FORM-D1 documented slots -> EquipmentRecord (caller-mapped, generic fields only)
    eq = EquipmentRecord(source_document="FORM D.xls", location="D1_220kv GIS!R12",
                         form_id="D1", equipment_type="220kV GIS", voltage="220kV",
                         quantity="6", test_status="YES", delivery_date="2026-01-01",
                         subcontractor_name="Acme", origin_country="Egypt")
    assert eq.voltage == "220kV" and eq.test_status == "YES"
    # Sarai D8 documented slots -> ProjectExperienceRecord
    pr = ProjectExperienceRecord(source_document="FORM D.xls", location="D8!R20",
                                 project="North Cairo", employer="EETC", country="Egypt",
                                 scope="Installation", award_date="2024-05-01",
                                 completion_date="2025-05-01", total_value="12M")
    assert pr.employer == "EETC" and pr.total_value == "12M"
    # Project 3 clarification/addendum shapes
    cl = ClarificationRecord(source_document="Clarification 1.pdf", location="p1",
                             reference="Q3", question="DAP delivery?",
                             response="DAP site per owner.")
    assert cl.question and cl.response
    ad = AddendumRecord(source_document="Addendum No. 1.pdf", location="p2",
                        amendment="Addendum No. 1", affected_section="7B")
    assert ad.affected_section == "7B"


def test_ganna_audit_no_invented_fields():
    audit = json.loads((E / "ganna_reference_audit.json").read_text(encoding="utf-8"))
    assert audit["ground_truth_policy"].startswith("reference/extraction artifacts ONLY")
    assert "Mobile_Substations_Extracted_Full.xlsx" in json.dumps(audit)
    assert "C:\\Users\\Admin" not in json.dumps(audit)  # paths never inherited
    assert audit["package"]["status"].startswith("reference material")
