# Decisions

## Project skeleton (2026-11-16)

- **Flat `app/` package, not a `src/` layout**: matches the folder structure the
  project was planned around (see the Countersign Build Kit doc), so later features
  (`app/policy.py`, `app/audit.py`, `policies/default.yaml`, `demo/`) land exactly
  where the plan expects them.
- **Config via plain `os.environ`, not `pydantic-settings`**: Pydantic v2 moved
  `BaseSettings` into a separate `pydantic-settings` package. Adding it now would be an
  extra dependency for a single `DATABASE_URL` lookup. `app/db.py` reads it directly;
  revisit if config grows (nested settings, `.env` parsing, validation) enough to
  justify the dependency.
- **`psycopg[binary]` for Postgres**: psycopg3 is the SQLAlchemy 2.0-recommended driver
  for Postgres 16. SQLite needs no extra driver (stdlib `sqlite3`), which is why it's not
  listed as a dependency even though it's used in tests.
- **`DeclarativeBase` in `app/db.py`**: SQLAlchemy 2.0's typed declarative base; the
  policy engine and audit log features will subclass it for their tables.
- **`/health` does not touch the database**: it's a liveness check for the process, not
  a readiness check. A DB-aware readiness check can be added once the database layer
  exists.
