"""Test-wide setup: point the app at a throwaway SQLite file, not the dev database.

Must run before `app.db` is first imported, since it reads `DATABASE_URL` at
import time. pytest imports conftest.py before any test module in this
directory, so setting the environment variable here is early enough.
"""

import os
import tempfile
from pathlib import Path

_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"countersign_test_{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["REVIEWER_TOKEN"] = "test-reviewer-token"
os.environ["APPROVAL_TTL_SECONDS"] = "3600"


def pytest_sessionfinish() -> None:
    """Dispose the engine's connections, then remove the throwaway SQLite file."""
    from app.db import engine

    engine.dispose()
    _TEST_DB_PATH.unlink(missing_ok=True)
