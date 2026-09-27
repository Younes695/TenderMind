"""
Stage 3D — Tiny-input guard tests (no Ollama required).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.stage3d.tiny_guard import tiny_guard_status, TINY_THRESHOLD, SKIPPED_TINY_INPUT


def test_tiny_input_skipped():
    chunk = {"chunk_id": "chunk-0000", "source_document": "a.txt", "page_number": 1, "text": "x" * 217}
    assert tiny_guard_status(chunk) == SKIPPED_TINY_INPUT
    print("PASS tiny input skipped")


def test_normal_input_ok():
    chunk = {"chunk_id": "chunk-0001", "source_document": "a.pdf", "page_number": 1, "text": "y" * 2976}
    assert tiny_guard_status(chunk) == "OK"
    print("PASS normal input ok")


def test_empty_input():
    assert tiny_guard_status({"chunk_id": "c", "source_document": "a", "page_number": 1, "text": ""}) == "EMPTY_INPUT"
    assert tiny_guard_status({"chunk_id": "c", "source_document": "a", "page_number": 1}) == "EMPTY_INPUT"
    assert tiny_guard_status(None) == "EMPTY_INPUT"
    print("PASS empty input")


def test_whitespace_only_input():
    chunk = {"chunk_id": "c", "source_document": "a", "page_number": 1, "text": "   \n\t  "}
    assert tiny_guard_status(chunk) == "WHITESPACE_ONLY"
    print("PASS whitespace-only input")


def test_explicit_skipped_status():
    assert SKIPPED_TINY_INPUT == "SKIPPED_TINY_INPUT"
    assert TINY_THRESHOLD == 300
    print("PASS explicit skipped status")


def test_no_fake_llm_success():
    # Guard must never return OK for tiny inputs (which would allow fake success claims)
    for n in (0, 1, 100, 217, 299):
        chunk = {"chunk_id": "c", "source_document": "a", "page_number": 1, "text": "z" * n}
        status = tiny_guard_status(chunk)
        assert status != "OK", f"len {n} must not be OK"
    # Boundary: exactly 300 is OK
    assert tiny_guard_status({"chunk_id": "c", "source_document": "a", "page_number": 1, "text": "z" * 300}) == "OK"
    print("PASS no fake LLM success")


if __name__ == "__main__":
    test_tiny_input_skipped()
    test_normal_input_ok()
    test_empty_input()
    test_whitespace_only_input()
    test_explicit_skipped_status()
    test_no_fake_llm_success()
    print("\nAll 6 Stage 3D tiny-guard tests passed")
