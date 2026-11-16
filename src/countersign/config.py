"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    """Runtime configuration. See .env.example for the full list of variables."""

    database_url: str
    environment: str


@lru_cache
def get_settings() -> Settings:
    """Return cached settings built from the current environment."""
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL", "sqlite:///./countersign.db"
        ),
        environment=os.environ.get("ENVIRONMENT", "development"),
    )
