"""Append-only, hash-chained audit log of every action request and decision.

Each entry stores the SHA-256 hash of the previous entry's hash plus its own
fields, so editing or deleting any row breaks the chain for every row after
it. `verify_chain` walks the log and recomputes every hash to detect that.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db import Base

GENESIS_HASH = "0" * 64


class AuditLogEntry(Base):
    """One row of the audit log: a request plus the policy decision made on it."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_id: Mapped[str] = mapped_column(String, index=True)
    agent_id: Mapped[str] = mapped_column(String)
    tool: Mapped[str] = mapped_column(String)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON)
    context: Mapped[str | None] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String)
    matched_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class ChainVerificationResult(BaseModel):
    """The outcome of walking the audit log and recomputing every hash."""

    valid: bool
    entries_checked: int
    error: str | None = None


def _canonical_hash(payload: dict[str, Any]) -> str:
    """SHA-256 of the payload as canonical JSON: sorted keys, no extra whitespace."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _entry_payload(entry: AuditLogEntry) -> dict[str, Any]:
    """Every field of an entry except `hash` itself, including `prev_hash`."""
    return {
        "id": entry.id,
        "action_id": entry.action_id,
        "agent_id": entry.agent_id,
        "tool": entry.tool,
        "arguments": entry.arguments,
        "context": entry.context,
        "decision": entry.decision,
        "reason": entry.reason,
        "matched_rule": entry.matched_rule,
        "prev_hash": entry.prev_hash,
        "created_at": entry.created_at.isoformat(),
    }


def _latest_hash(session: Session) -> str:
    latest = session.query(AuditLogEntry).order_by(AuditLogEntry.id.desc()).first()
    return latest.hash if latest is not None else GENESIS_HASH


def append_entry(
    session: Session,
    *,
    action_id: str,
    agent_id: str,
    tool: str,
    arguments: dict[str, Any],
    context: str | None,
    decision: str,
    reason: str,
    matched_rule: str | None,
) -> AuditLogEntry:
    """Append one entry to the audit log, chained to the current latest hash."""
    entry = AuditLogEntry(
        action_id=action_id,
        agent_id=agent_id,
        tool=tool,
        arguments=arguments,
        context=context,
        decision=decision,
        reason=reason,
        matched_rule=matched_rule,
        prev_hash=_latest_hash(session),
        # Naive UTC: SQLite drops tzinfo on reload, which would otherwise make
        # created_at.isoformat() differ before and after a round trip and
        # break hash verification for entries re-fetched from the database.
        created_at=datetime.now(UTC).replace(tzinfo=None),
        hash="",
    )
    session.add(entry)
    session.flush()  # assigns entry.id, needed before hashing
    entry.hash = _canonical_hash(_entry_payload(entry))
    session.commit()
    return entry


def get_entries_for_action(session: Session, action_id: str) -> list[AuditLogEntry]:
    """Return all audit log entries recorded for a given action_id, in order."""
    return (
        session.query(AuditLogEntry)
        .filter(AuditLogEntry.action_id == action_id)
        .order_by(AuditLogEntry.id)
        .all()
    )


def verify_chain(session: Session) -> ChainVerificationResult:
    """Walk the whole audit log and recompute every hash and link.

    Detects any edit or deletion: an edited row's recomputed hash won't match
    its stored hash, and a deleted row breaks the next row's prev_hash link.
    """
    entries = session.query(AuditLogEntry).order_by(AuditLogEntry.id).all()
    expected_prev = GENESIS_HASH
    for entry in entries:
        if entry.prev_hash != expected_prev:
            return ChainVerificationResult(
                valid=False,
                entries_checked=len(entries),
                error=f"entry {entry.id}: prev_hash does not match the preceding entry's hash",
            )
        if _canonical_hash(_entry_payload(entry)) != entry.hash:
            return ChainVerificationResult(
                valid=False,
                entries_checked=len(entries),
                error=f"entry {entry.id}: stored hash does not match its contents",
            )
        expected_prev = entry.hash
    return ChainVerificationResult(valid=True, entries_checked=len(entries))
