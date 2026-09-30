"""Live progress from deep inside extraction / AI loops to the processing job.

The page loops (evaluation/run_real_benchmark.py, evaluation/tesseract_local_ocr.py)
and the AI loop (app/pipeline/intelligence_runner.py) call `report()`; the job
runner installs a listener for the current thread with `listen()`. With no
listener installed `report()` does nothing, so standalone scripts are unaffected.
"""
import threading
from contextlib import contextmanager
from typing import Callable, Optional

_local = threading.local()


def report(phase: str, done: int, total: int) -> None:
    fn: Optional[Callable[[str, int, int], None]] = getattr(_local, "fn", None)
    if fn is None:
        return
    try:
        fn(phase, done, total)
    except Exception:
        pass  # progress must never break processing


@contextmanager
def listen(fn: Callable[[str, int, int], None]):
    prev = getattr(_local, "fn", None)
    _local.fn = fn
    try:
        yield
    finally:
        _local.fn = prev
