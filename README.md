# countersign

An open-source approval and audit gateway for AI agents. Agents send every tool call
to Countersign before executing it; Countersign checks it against a YAML policy
(allow / block / needs_approval), holds approvals in a queue, and writes an
append-only, hash-chained audit log of every request and decision.

## Status

Early scaffolding. `/health`, a YAML policy engine (`POST /v1/actions/evaluate`), a
hash-chained audit log (`GET /v1/audit`, `GET /v1/audit/verify`), and a human approval
queue (`/v1/approvals/*`) are in place.

## Policy engine

`policies/default.yaml` holds an ordered list of rules; the first rule whose tool-name
glob and argument conditions match wins. If no rule matches, the policy's `default`
decision applies. See [docs/decisions.md](docs/decisions.md) for why it's ordered this
way. Override the file with the `POLICY_PATH` environment variable.

## Audit log

Every call to `POST /v1/actions/evaluate` writes an entry to an append-only,
hash-chained audit log: each row's hash covers all of its own fields plus the previous
row's hash, so editing or deleting a row is detectable.

- `GET /v1/audit?action_id=<id>` — the audit entries recorded for one action.
- `GET /v1/audit/verify` — walks the whole log and recomputes every hash, reporting
  whether the chain is intact.

## Approval queue

An action the policy marks `needs_approval` is also added to a queue a human reviewer
works from. Every endpoint under `/v1/approvals` requires an
`Authorization: Bearer <REVIEWER_TOKEN>` header (set `REVIEWER_TOKEN` in `.env`).

- `GET /v1/approvals` — list queued approvals; `?status=pending` filters by status.
- `GET /v1/approvals/{action_id}` — fetch one approval.
- `POST /v1/approvals/{action_id}/approve` — body `{"reviewer": "...", "reason": "..."}`.
- `POST /v1/approvals/{action_id}/reject` — same body shape.

An approval left pending past `APPROVAL_TTL_SECONDS` (default one hour) expires and is
treated as blocked. Every approve/reject/expiry is also written to the audit log under
the same `action_id`, so `GET /v1/audit?action_id=` shows an action's full history.

## Requirements

- Python 3.12
- Docker (for local Postgres via Docker Compose); SQLite is used in tests, no DB needed to run tests.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
```

## Running the API

Locally, against SQLite (default `DATABASE_URL` in `app/db.py`):

```bash
uvicorn app.main:app --reload
```

With Docker Compose (Postgres 16 + API):

```bash
docker compose up --build
```

## Tests and linting

```bash
pytest
ruff check .
```

## Decisions log

Non-obvious choices are explained in [docs/decisions.md](docs/decisions.md).
