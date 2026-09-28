"""Test isolation: never touch the developer's real database or uploads.

Several older tests wipe whole tables (processing_jobs, tenders, ...) through
app.database.SessionLocal. Without this file they ran against the project's
tender.db and uploads/, deleting real local tenders on every test run.

This runs before any test module imports app.database (which reads
DATABASE_URL at import time), so the whole suite uses a throwaway copy.
Tests that set their own DATABASE_URL / TENDERMIND_STORAGE_ROOT still win.
"""
import atexit
import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="tm_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test.db').replace(os.sep, '/')}"
os.environ["TENDERMIND_STORAGE_ROOT"] = os.path.join(_TMP, "uploads")
os.environ["TENDERMIND_SKIP_DOTENV"] = "1"  # a developer .env must not leak into tests
# Background services stay off in tests (they are tested directly).
os.environ["TENDERMIND_AUTO_RESUME"] = "0"
os.environ["TENDERMIND_WATCHDOG"] = "0"
os.environ["TENDERMIND_NEWS_ENABLED"] = "0"
atexit.register(shutil.rmtree, _TMP, True)
