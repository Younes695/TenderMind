"""Stage 5H — checkpoints so an interrupted or retried job resumes instead of
starting from zero.

- Extraction: one JSON file per uploaded file, keyed by the file's content hash.
  A retried job reuses it, so a 1,530-page PDF is not OCR'd again.
- AI: one JSONL file per tender + model + prompt version; each successful
  normalization is appended as it arrives. A resumed job only calls the model
  for candidates not answered yet.

Everything lives under <storage_root>/<tender_id>/.cache/ and is best effort:
a missing, stale or unreadable cache simply means "do the work again".
"""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CACHE_VERSION = 1


def cache_dir(tender_id: str) -> Path:
    from app.database import get_storage_root
    return get_storage_root() / tender_id / ".cache"


def file_digest(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _extraction_path(tender_id: str, digest: str) -> Path:
    return cache_dir(tender_id) / f"extract-v{CACHE_VERSION}-{digest}.json"


def load_extraction(tender_id: str, path: Path, filename: str) -> Optional[List[Tuple[str, Dict[str, Any]]]]:
    try:
        p = _extraction_path(tender_id, file_digest(path))
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("filename") != filename:
            return None
        return [(e["name"], e["result"]) for e in data["entries"]]
    except Exception:
        return None


def save_extraction(tender_id: str, path: Path, filename: str,
                    entries: List[Tuple[str, Dict[str, Any]]]) -> None:
    """Only complete extractions are kept; a FAILED file is retried next time."""
    try:
        if any(str(r.get("status")) == "FAILED" for _n, r in entries):
            return
        d = cache_dir(tender_id)
        d.mkdir(parents=True, exist_ok=True)
        p = _extraction_path(tender_id, file_digest(path))
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({"filename": filename,
                                   "entries": [{"name": n, "result": r} for n, r in entries]},
                                  ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(p)  # atomic: a crash mid-write never leaves a half file
    except Exception:
        pass


class AiCache:
    """Append-only cache of successful normalizations for one tender/model/prompt."""

    def __init__(self, tender_id: str, model_name: str, prompt_version: str):
        tag = hashlib.sha1(f"{model_name}|{prompt_version}".encode()).hexdigest()[:12]
        self.path = cache_dir(tender_id) / f"ai-v{CACHE_VERSION}-{tag}.jsonl"
        self._lock = threading.Lock()
        self._data: Dict[str, Dict[str, Any]] = {}
        try:
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        row = json.loads(line)
                        self._data[row["k"]] = row["v"]
                    except (ValueError, KeyError):
                        continue  # a torn last line after a crash is ignored
        except OSError:
            pass

    @staticmethod
    def key(text: str) -> str:
        return hashlib.sha1((text or "").encode("utf-8")).hexdigest()

    def __len__(self) -> int:
        return len(self._data)

    def get(self, text: str) -> Optional[Dict[str, Any]]:
        return self._data.get(self.key(text))

    def put(self, text: str, result: Any) -> None:
        try:
            value = asdict(result) if hasattr(result, "__dataclass_fields__") else dict(result)
            k = self.key(text)
            with self._lock:
                self._data[k] = value
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"k": k, "v": value}, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass
