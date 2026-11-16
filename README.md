# countersign

An open-source approval and audit gateway for AI agents. Agents send every tool call
to Countersign before executing it; Countersign checks it against a YAML policy
(allow / block / needs_approval), holds approvals in a queue, and writes an
append-only, hash-chained audit log of every request and decision.

## Status

Early scaffolding. Currently just a FastAPI skeleton with a `/health` endpoint —
the policy engine, approval queue, and audit log are not built yet.

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

Locally, against SQLite (default `DATABASE_URL` in `config.py`):

```bash
uvicorn countersign.main:app --reload
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
