# Countersign
An open-source approval and audit gateway for AI agents. Agents send every action they want to take (a "tool call", e.g. issue_refund, send_email, delete_record) to Countersign BEFORE executing it. Countersign:
1. Checks the action against a YAML policy and returns one decision: allow, block, or needs_approval.
2. Holds needs_approval actions in a queue until a human approves or rejects them, with a reason.
3. Writes every request and decision to an append-only, hash-chained audit log (each entry stores the SHA-256 of the previous entry, so any edit or deletion is detectable).
Long-term goal: evidence for human oversight and record-keeping (EU AI Act Articles 12, 14, 26) for small companies running agents.

## Stack
Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, PostgreSQL 16 (SQLite in tests), PyYAML, pytest, httpx, ruff. Docker Compose for local runs. GitHub Actions CI. React dashboard comes in week 2, not now.

## Rules for you (Claude Code)
- Small steps. One prompt = one feature. Show me the plan before large changes.
- Every feature ships with pytest tests. Run tests and ruff before saying a step is done.
- Type hints everywhere. Clear names. No clever one-liners. Short docstrings on public functions.
- Never commit secrets. Config via environment variables with a .env.example file.
- Keep the README updated when behaviour changes.
- Explain non-obvious decisions in a short comment or in docs/decisions.md, so I can defend them in interviews.
- Do not add dependencies without telling me why.
