"""Stage 4A — centralized configuration.

Single place for every environment knob the pipeline reads. No hardcoded
developer-machine paths: storage and database default to portable
project-relative locations; absolute paths only ever come from explicit env.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

TWO_STAGE_FLAG = "TENDERMIND_TWO_STAGE_LLM"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_storage_root() -> str:
    return str(_project_root() / "uploads")


def _default_database_url() -> str:
    return f"sqlite:///{_project_root() / 'tender.db'}"


@dataclass(frozen=True)
class PipelineConfig:
    database_url: str = ""
    storage_root: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    llm_timeout_s: int = 90
    two_stage_enabled: bool = False
    tender_sarai_path: str = ""  # evaluation-only fallback, empty in production


def load_config(env: dict | None = None) -> PipelineConfig:
    e = env if env is not None else os.environ
    get = (lambda k, d="": str(e.get(k, d)))
    try:
        timeout = int(e.get("LLM_TIMEOUT", e.get("TENDERMIND_LLM_TIMEOUT", 90)))
    except (TypeError, ValueError):
        timeout = 90
    model = (e.get("OLLAMA_MODEL") or e.get("TENDERMIND_OLLAMA_MODEL") or "qwen2.5:3b")
    base = (e.get("OLLAMA_BASE_URL") or e.get("TENDERMIND_OLLAMA_ENDPOINT")
            or "http://localhost:11434")
    return PipelineConfig(
        database_url=get("DATABASE_URL", _default_database_url()),
        storage_root=get("TENDERMIND_STORAGE_ROOT", _default_storage_root()),
        ollama_base_url=base,
        ollama_model=model,
        llm_timeout_s=timeout,
        two_stage_enabled=e.get(TWO_STAGE_FLAG) == "1",
        tender_sarai_path=get("TENDER_SARAI_PATH", ""),
    )


def is_two_stage_enabled() -> bool:
    """Flag gate. Default/off preserves existing behavior; never switch silently."""
    return os.environ.get(TWO_STAGE_FLAG) == "1"
