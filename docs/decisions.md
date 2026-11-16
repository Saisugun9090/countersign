# Decisions

## Project skeleton (2026-11-16)

- **src layout** (`src/countersign/`): keeps the installed package import path separate
  from the repo root, so tests import the installed package rather than accidentally
  picking up local files by coincidence of working directory.
- **Config via plain `os.environ`, not `pydantic-settings`**: Pydantic v2 moved
  `BaseSettings` into a separate `pydantic-settings` package. Adding it now would be an
  extra dependency for a single `DATABASE_URL` + `ENVIRONMENT` lookup. A small
  `functools.lru_cache`-backed `Settings` dataclass covers this; revisit if config grows
  (nested settings, `.env` parsing, validation) enough to justify the dependency.
- **`psycopg[binary]` for Postgres**: psycopg3 is the SQLAlchemy 2.0-recommended driver
  for Postgres 16. SQLite needs no extra driver (stdlib `sqlite3`), which is why it's not
  listed as a dependency even though it's used in tests.
- **`/health` does not touch the database**: it's a liveness check for the process, not
  a readiness check. A DB-aware readiness check can be added once the database layer
  exists.
