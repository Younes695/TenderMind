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

# A file read with failures is read again on the next run, in case the error was
# passing. After this many reads failing with the same readers installed, the
# stored read is reused: one page Tesseract always crashes on made every retry
# OCR a 1,530-page volume again in full.
FAILED_READS_BEFORE_REUSE = 2


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
    """A file with a failed document or an unreadable page is read again, so a
    passing OCR or conversion error is not kept for good - until the same failure
    came back FAILED_READS_BEFORE_REUSE times with the same readers installed. A
    file with a failure or an unsupported part is also read again when the readers
    changed (Tesseract, LibreOffice, 7-Zip or ODA installed, or the reader rules)."""
    from app.pipeline.file_extractors import extraction_tools
    try:
        p = _extraction_path(tender_id, file_digest(path))
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("filename") != filename:
            return None
        entries = [(e["name"], e["result"]) for e in data["entries"]]
        failures, unsupported = _shortfalls(entries)
        if (failures or unsupported) and data.get("tools") != extraction_tools():
            return None
        if failures and data.get("failed_reads", 0) < FAILED_READS_BEFORE_REUSE:
            return None
        return entries
    except Exception:
        return None


def _shortfalls(entries: List[Tuple[str, Dict[str, Any]]]) -> Tuple[List[Any], bool]:
    """(what failed: [name, failed pages or 'FAILED'] per entry, any UNSUPPORTED part)."""
    from app.pipeline.file_extractors import entry_has_failures
    failures = [[n, r.get("failed_pages") or str(r.get("status"))]
                for n, r in entries if entry_has_failures(r)]
    return failures, any(str(r.get("status")) == "UNSUPPORTED" for _n, r in entries)


def save_extraction(tender_id: str, path: Path, filename: str,
                    entries: List[Tuple[str, Dict[str, Any]]]) -> None:
    """Every extraction is written, failures included: this file is also the
    text store that sections, materials, certifications, conflicts and RFQs read
    (an archive with one broken file kept none of its other files' text).
    A read with a failure or an unsupported part also records the readers it had;
    one with failures records what failed and how many reads in a row failed the
    same way with them, which load_extraction uses to stop retrying."""
    from app.pipeline.file_extractors import extraction_tools
    try:
        d = cache_dir(tender_id)
        d.mkdir(parents=True, exist_ok=True)
        p = _extraction_path(tender_id, file_digest(path))
        record: Dict[str, Any] = {"filename": filename,
                                  "entries": [{"name": n, "result": r} for n, r in entries]}
        failures, unsupported = _shortfalls(entries)
        if failures or unsupported:
            record["tools"] = extraction_tools()
        if failures:
            try:
                prev = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
            except Exception:
                prev = {}
            # A different failure (another page lost to a passing error) starts again at 1.
            same = (prev.get("filename") == filename and prev.get("tools") == record["tools"]
                    and prev.get("failed") == failures)
            record["failed"] = failures
            record["failed_reads"] = (int(prev.get("failed_reads") or 0) if same else 0) + 1
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, default=str), encoding="utf-8")
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
