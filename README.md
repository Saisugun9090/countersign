# countersign

An open-source approval and audit gateway for AI agents. Agents send every tool call
to Countersign before executing it; Countersign checks it against a YAML policy
(allow / block / needs_approval), holds approvals in a queue, and writes an
append-only, hash-chained audit log of every request and decision.

## Status

Early scaffolding. `/health` and a YAML policy engine (`POST /v1/actions/evaluate`)
are in place — the approval queue and audit log are not built yet.

## Policy engine

`policies/default.yaml` holds an ordered list of rules; the first rule whose tool-name
glob and argument conditions match wins. If no rule matches, the policy's `default`
decision applies. See [docs/decisions.md](docs/decisions.md) for why it's ordered this
way. Override the file with the `POLICY_PATH` environment variable.

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
