"""
Test that run_ollama_benchmark uses matcher-configured timeout (90s default) via TENDERMIND_OLLAMA_TIMEOUT,
and does not hardcode 30s. Offline, no network, $0.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
from unittest.mock import patch


def test_benchmark_respects_env_timeout():
    # Verify benchmark reads TENDERMIND_OLLAMA_TIMEOUT via get_ollama_timeout and passes to OllamaMatcher
    from app.matchers.ollama_matcher import get_ollama_timeout
    # Default should be 90 (not 30)
    with patch.dict(os.environ, {}, clear=False):
        # Remove override if present
        os.environ.pop("TENDERMIND_OLLAMA_TIMEOUT", None)
        # Need to reload? get_ollama_timeout reads env each call
        assert get_ollama_timeout() == 90, f"default timeout must be 90, got {get_ollama_timeout()}"
    # Custom value respected
    with patch.dict(os.environ, {"TENDERMIND_OLLAMA_TIMEOUT": "120"}):
        assert get_ollama_timeout() == 120, "must respect TENDERMIND_OLLAMA_TIMEOUT=120"
    # Invalid falls back to 90
    with patch.dict(os.environ, {"TENDERMIND_OLLAMA_TIMEOUT": "invalid"}):
        assert get_ollama_timeout() == 90
    print("PASS test_benchmark_respects_env_timeout")


def test_benchmark_no_hardcoded_30s():
    # Ensure run_ollama_benchmark.py does not hardcode 30s for inference
    src = Path(__file__).resolve().parents[1] / "evaluation" / "run_ollama_benchmark.py"
    text = src.read_text(encoding="utf-8")
    # The old hardcoded string was "timeout 30s per request" — must be gone
    assert "timeout 30s per request" not in text, "benchmark must not hardcode 'timeout 30s per request'"
    # Must use get_ollama_timeout and pass timeout to OllamaMatcher
    assert "get_ollama_timeout" in text, "benchmark must use get_ollama_timeout()"
    assert "OllamaMatcher(model=model, timeout=timeout)" in text or "timeout=timeout" in text, \
        "benchmark must pass matcher-configured timeout to OllamaMatcher"
    print("PASS test_benchmark_no_hardcoded_30s")


def test_matcher_default_timeout_is_90():
    from app.matchers.ollama_matcher import OllamaMatcher, TIMEOUT_PER_REQUEST
    assert TIMEOUT_PER_REQUEST == 90, f"TIMEOUT_PER_REQUEST must be 90, got {TIMEOUT_PER_REQUEST}"
    m = OllamaMatcher()
    assert m.timeout == 90, f"OllamaMatcher default timeout must be 90, got {m.timeout}"
    print("PASS test_matcher_default_timeout_is_90")


if __name__ == "__main__":
    test_benchmark_respects_env_timeout()
    test_benchmark_no_hardcoded_30s()
    test_matcher_default_timeout_is_90()
    print("All benchmark timeout tests passed — no network, $0")
