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

## Hash-chained audit log (2026-11-16)

- **Hash covers every field except `hash` itself, including `prev_hash`**: chaining
  `prev_hash` into the hash (rather than storing it alongside an independently-hashed
  row) is what makes the log a chain — deleting a row breaks the `prev_hash` link on the
  row after it, and editing a row changes its own hash, so both are detectable by
  `verify_chain` without needing a separate Merkle structure.
- **Canonical JSON (`sort_keys=True`, no whitespace) for the hash input**: hashing a
  Python dict's `repr()` or an unsorted `json.dumps()` would make the hash depend on
  incidental key order, so the same logical entry could hash differently depending on
  how it was constructed. Canonical JSON removes that ambiguity.
- **`GENESIS_HASH` (64 zeros) as the `prev_hash` of the first entry**: a fixed, known
  sentinel rather than `None`/empty string keeps `prev_hash` a plain fixed-length string
  across the whole table; it's simpler than a precomputed first row and keeps
  `verify_chain`'s loop uniform (every row, including the first, checks
  `prev_hash == expected_prev`).
- **`created_at` stored as naive UTC, not timezone-aware**: SQLite has no real datetime
  type — SQLAlchemy stores it as a string and drops tzinfo on reload. A tz-aware
  datetime's `isoformat()` therefore differs before and after a round trip through the
  database (e.g. missing the `+00:00` suffix), which broke hash verification for any
  entry re-fetched from storage. Stripping tzinfo before storing, and always treating
  the column as UTC, keeps the hashed string stable across reloads.
- **`append_entry` flushes before hashing, not after**: the row's own autoincrement `id`
  is part of the hashed payload, so the id must exist before the hash is computed. A
  `session.flush()` assigns it without committing, then the hash is set and the commit
  happens once.
- **Plain SQLAlchemy `Session` queries, no FastAPI `Depends` session dependency yet**: a
  `with SessionLocal() as session` per request is simpler while there's only one route
  that writes and two that read. Revisit once more endpoints need a shared session
  (e.g. the approval queue) or testing needs dependency overrides.

## Approval queue (2026-11-16)

- **A single shared `REVIEWER_TOKEN`, not per-agent API keys, guards `/v1/approvals/*`**:
  the agents calling `/v1/actions/evaluate` and the humans reviewing queued approvals are
  different trust boundaries, so they get separate auth even before per-agent API keys
  exist. Per-agent keys are a later feature (the demo agent); until then, nothing agents
  send should be able to approve or reject anything.
- **Lazy expiry on read, not a background sweep**: `_expire_if_due` checks `now >
  expires_at` whenever an approval is fetched (via `get_approval` or `list_approvals`)
  rather than running a periodic job. There's no task scheduler or worker process in this
  project yet, and correctness doesn't need one — an approval that's overdue is overdue
  whether or not anything has looked at it recently; it just needs to be caught before
  anyone acts on its status.
- **Expiry's effective decision is `block`, not `allow`**: fail closed, for the same
  reason the policy's own unmatched-action default is `needs_approval` rather than
  `allow` — if nobody reviewed it in time, the gateway shouldn't let it through.
- **A reviewer's approve/reject is written to the audit log as a second entry under the
  same `action_id`**, decision mapped to the existing `allow`/`block` vocabulary
  (`approve` → `allow`, `reject` → `block`) rather than inventing new decision values just
  for human review. `GET /v1/audit?action_id=` then shows the whole lifecycle of an
  action in order: the policy's original `needs_approval`, followed by the human's final
  call — without the `approvals` table needing to store its own history.
- **The `approvals` table holds one row per action, not a full history**: the audit log
  is already the append-only history; `approvals` only needs the current state (pending,
  approved, rejected, or expired) to answer "what's outstanding right now."

## Demo agent, per-agent API keys, and CLI (2026-11-16)

- **`agent_id` is removed from the `ActionRequest` body and taken from the API key
  instead**: once a real credential exists, trusting a client-supplied identity field
  defeats the point of having one — any agent could claim to be any other agent. The
  authenticated `agent_id` from `app.auth.require_agent_api_key` is now the only source
  of truth for who submitted an action.
- **Agents are registered in `agents.yaml` by key hash, like `policies/default.yaml`**:
  consistent with the project's existing pattern for small, human-editable config, and it
  means the raw key is never stored anywhere the server reads from — only its SHA-256
  hash. `AGENTS_PATH` overrides the file, mirroring `POLICY_PATH`.
- **No endpoint to self-register new agents yet**: out of scope for a demo with one
  agent. Adding a new one means generating a key, hashing it (`app.auth.hash_key`), and
  adding a line to `agents.yaml` by hand — revisit if/when there are enough agents for
  that to be tedious.
- **`GET /v1/actions/{action_id}` reads the latest audit log entry, not a separate
  "current status" table**: the audit log already records every state change
  (policy decision, then approve/reject/expiry), so its last entry for an action_id *is*
  the current decision. Also enforces that only the agent who submitted an action
  (`entries[0].agent_id`) can check its status, not just any authenticated agent.
- **The demo agent's dev key is a committed placeholder, not a real secret**: its SHA-256
  hash in `agents.yaml` corresponds to the value already in `.env.example`
  (`DEMO_AGENT_API_KEY=demo-agent-dev-key-change-me`), so the demo works immediately
  after `cp .env.example .env` with no setup step. It's clearly documented as
  local-development-only and must be rotated before registering a real agent.
- **`httpx` moved from dev-only to a runtime dependency**: it was already a dependency
  (used by FastAPI's `TestClient`); `demo/refund_agent.py` now also uses it at runtime
  to call the API, so it belongs in `[project.dependencies]` rather than only `dev`. No
  new dependency was added.

## CI, coverage, and README (2026-11-16)

- **`pytest-cov` added as a dev dependency**: the only new dependency added this
  weekend. Needed to measure and report line coverage in CI; it's the standard,
  lightweight way to do that with pytest, and the project otherwise has no coverage
  tooling to build on.
- **No coverage badge**: a real badge needs a hosted coverage service (e.g. Codecov)
  and its token, neither of which is set up. CI reports coverage in its logs and
  uploads `coverage.xml` as a build artifact either way, so adding a real badge later is
  just pointing a service at that output — but committing a static or hand-made badge
  image now would be exactly the "fake" badge the plan explicitly said not to add.
- **A separate `docker-build` CI job, not a step in the `test` job**: it doesn't need
  the Python environment the test job sets up, and keeping it separate means a Dockerfile
  break shows up as its own clearly-labeled failure rather than buried in the test job's
  log. It only builds the image (no push, no registry) — a smoke test that the
  Dockerfile still works, which is also the one thing about this project that hasn't
  been verified any other way (Docker Desktop hasn't been available in this development
  environment).
- **`GET /v1/audit` and `GET /v1/audit/verify` are left unauthenticated for now, and
  called out in the README's Limitations section rather than fixed in this feature**:
  real but out of scope for "finish weekend one with CI and docs" — flagging it clearly
  beats quietly leaving it for the user to discover, and the instruction for this feature
  was explicitly to report what's still rough, not to fix every rough edge found while
  writing that report.
- **Docker became available partway through this feature, so the stack was actually run
  end-to-end for the first time, and that surfaced two real bugs, both fixed**:
  1. The `Dockerfile` only copied `app/`, not `policies/` or `agents.yaml` — the
     container crashed on startup (`FileNotFoundError` from `load_policy`) because
     `app/policy.py` and `app/auth.py` resolve their default paths relative to the
     package root, which didn't exist in the image. Fixed by copying both.
  2. `docker-compose.yml`'s `api` service used a plain `depends_on: [db]`, which only
     waits for the `db` container to *start*, not for Postgres to be ready to accept
     connections — `api` consistently crashed trying to connect before `db` had
     finished initializing. Fixed with a `pg_isready` healthcheck on `db` and
     `depends_on: db: condition: service_healthy` on `api`.
  These were exactly the kind of gap the "Check it works" step was meant to catch, and
  would otherwise have shipped as a silent limitation; worth remembering that Docker's
  unavailability earlier in this project was masking real bugs, not just blocking a
  verification step.
