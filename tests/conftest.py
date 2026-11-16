"""Test-wide setup: point the app at throwaway SQLite and agent-registry files.

Must run before `app.db` / `app.main` are first imported, since they read
these environment variables at import time. pytest imports conftest.py
before any test module in this directory, so setting them here is early
enough.
"""

import hashlib
import os
import tempfile
from pathlib import Path

import yaml

TEST_AGENT_ID = "test-agent"
TEST_AGENT_API_KEY = "test-agent-api-key"

_TEST_DB_PATH = Path(tempfile.gettempdir()) / f"countersign_test_{os.getpid()}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["REVIEWER_TOKEN"] = "test-reviewer-token"
os.environ["APPROVAL_TTL_SECONDS"] = "3600"

_TEST_AGENTS_PATH = Path(tempfile.gettempdir()) / f"countersign_test_agents_{os.getpid()}.yaml"
_TEST_AGENTS_PATH.write_text(
    yaml.dump(
        {
            "agents": [
                {
                    "agent_id": TEST_AGENT_ID,
                    "key_hash": hashlib.sha256(TEST_AGENT_API_KEY.encode("utf-8")).hexdigest(),
                }
            ]
        }
    )
)
os.environ["AGENTS_PATH"] = str(_TEST_AGENTS_PATH)


def pytest_sessionfinish() -> None:
    """Dispose the engine's connections, then remove the throwaway test files."""
    from app.db import engine

    engine.dispose()
    _TEST_DB_PATH.unlink(missing_ok=True)
    _TEST_AGENTS_PATH.unlink(missing_ok=True)
