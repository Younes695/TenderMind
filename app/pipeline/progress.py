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


SCALE = 1_000_000


@contextmanager
def share(start: float, span: float):
    """Report a sub-task (one file inside an archive) as the slice
    [start, start + span] of the current task: its "pages"/"fraction" reports
    reach the listener as ("fraction", done, SCALE). Before this, every inner
    PDF reported its own pages against the archive's estimate of 1 page, so a
    zip showed 99% from its first PDF on."""
    outer: Optional[Callable[[str, int, int], None]] = getattr(_local, "fn", None)
    if outer is None:
        yield
        return

    def inner(phase: str, done: int, total: int) -> None:
        if phase in ("pages", "fraction") and total:
            outer("fraction", round((start + span * min(done, total) / total) * SCALE), SCALE)
        else:
            outer(phase, done, total)

    _local.fn = inner
    try:
        yield
    finally:
        _local.fn = outer
