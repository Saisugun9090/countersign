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

## YAML policy engine (2026-11-16)

- **First-match-wins rule ordering, not "most specific wins" or priority scores**: it's
  the simplest model to reason about and to explain in an audit: read the YAML top to
  bottom, the first matching rule is the decision. More specific rules (e.g. the refund
  amount tiers) are just placed before their catch-alls in the file.
- **Default decision is `needs_approval`, not `allow`**: an unmatched action is one the
  policy author didn't think of. Failing open (`allow`) would let novel/unexpected tool
  calls through unchecked, which defeats the point of a gateway built for oversight
  evidence. Failing to `needs_approval` means a human sees it at least once.
- **`send_email` external-vs-internal is expressed as rule order, not a `not_contains`
  operator**: the condition op set (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`,
  `contains`) has no negated string-contains op. Instead, "internal" (contains
  `@our-company.com`) is listed first with `allow`; everything else falls through to an
  unconditional `send_email` rule with `needs_approval`. Avoids adding an operator for one
  rule.
- **Pydantic validates the policy file on load, not ad hoc checks**: a malformed
  `policies/*.yaml` (missing `default`, an invalid `decision` value, etc.) raises a
  `pydantic.ValidationError` at startup instead of silently falling back to some default,
  so a bad policy file is caught immediately rather than in production.
- **`fnmatch.fnmatchcase` for tool-name globs**: case-sensitive by default, which matches
  how tool names are expected to be written consistently (e.g. `delete_*`, `read_*`), and
  avoids platform-dependent case folding that plain `fnmatch.fnmatch` has on Windows.
