"""SQLAlchemy engine and session setup.

Tables for the policy engine and audit log are added in later features; this
module only wires up the engine so every feature shares one connection setup.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./countersign.db")

# SQLite needs same-thread checks disabled for use with FastAPI's threaded test client.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
