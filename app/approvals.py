"""The human approval queue.

An action the policy marked `needs_approval` waits here as a "pending" row
until a reviewer approves or rejects it, or its TTL passes and it expires.
Every state change is also written to the audit log (app/audit.py) under the
same action_id, so the full history of an action lives there.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.audit import append_entry
from app.db import Base

DEFAULT_APPROVAL_TTL_SECONDS = 3600


class ApprovalNotFoundError(Exception):
    """Raised when no approval exists for the given action_id."""


class ApprovalNotPendingError(Exception):
    """Raised when trying to decide an approval that is no longer pending."""

    def __init__(self, status: str) -> None:
        self.status = status
        super().__init__(f"approval is already {status}")


class Approval(Base):
    """One action awaiting, or past, human review."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    agent_id: Mapped[str] = mapped_column(String)
    tool: Mapped[str] = mapped_column(String)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON)
    context: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String)
    matched_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String, nullable=True)


def _now() -> datetime:
    # Naive UTC to match app/audit.py's created_at convention.
    return datetime.now(UTC).replace(tzinfo=None)


def _ttl_seconds() -> int:
    return int(os.environ.get("APPROVAL_TTL_SECONDS", DEFAULT_APPROVAL_TTL_SECONDS))


def enqueue(
    session: Session,
    *,
    action_id: str,
    agent_id: str,
    tool: str,
    arguments: dict[str, Any],
    context: str | None,
    reason: str,
    matched_rule: str | None,
) -> Approval:
    """Add an action to the approval queue with status "pending"."""
    now = _now()
    approval = Approval(
        action_id=action_id,
        agent_id=agent_id,
        tool=tool,
        arguments=arguments,
        context=context,
        reason=reason,
        matched_rule=matched_rule,
        status="pending",
        created_at=now,
        expires_at=now + timedelta(seconds=_ttl_seconds()),
    )
    session.add(approval)
    session.commit()
    return approval


def _expire_if_due(approval: Approval, session: Session) -> Approval:
    """Flip a pending approval whose TTL has passed to "expired".

    An expiry is a decision too (fail closed: nobody approved in time), so it
    is written to the audit log like any other. `append_entry` commits the
    session, which also persists the status change made just above it.
    """
    if approval.status == "pending" and _now() > approval.expires_at:
        approval.status = "expired"
        approval.decided_at = _now()
        append_entry(
            session,
            action_id=approval.action_id,
            agent_id="system",
            tool=approval.tool,
            arguments=approval.arguments,
            context=approval.context,
            decision="block",
            reason="Approval expired without a reviewer decision.",
            matched_rule=None,
        )
    return approval


def get_approval(session: Session, action_id: str) -> Approval:
    """Fetch one approval by action_id, applying lazy expiry first."""
    approval = session.query(Approval).filter(Approval.action_id == action_id).one_or_none()
    if approval is None:
        raise ApprovalNotFoundError(action_id)
    return _expire_if_due(approval, session)


def list_approvals(session: Session, status: str | None = None) -> list[Approval]:
    """List approvals, optionally filtered by status, applying lazy expiry first."""
    approvals = session.query(Approval).order_by(Approval.id).all()
    approvals = [_expire_if_due(approval, session) for approval in approvals]
    if status is not None:
        approvals = [approval for approval in approvals if approval.status == status]
    return approvals


def decide(
    session: Session, action_id: str, *, approve: bool, reviewer: str, reason: str
) -> Approval:
    """Approve or reject a pending approval. Raises if it is no longer pending."""
    approval = get_approval(session, action_id)
    if approval.status != "pending":
        raise ApprovalNotPendingError(approval.status)
    approval.status = "approved" if approve else "rejected"
    approval.decided_at = _now()
    approval.decided_by = reviewer
    approval.decision_reason = reason
    append_entry(
        session,
        action_id=approval.action_id,
        agent_id=reviewer,
        tool=approval.tool,
        arguments=approval.arguments,
        context=approval.context,
        decision="allow" if approve else "block",
        reason=reason,
        matched_rule=None,
    )
    return approval
