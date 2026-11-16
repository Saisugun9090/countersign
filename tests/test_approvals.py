"""Unit tests for the approval queue, against an isolated in-memory SQLite database."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.approvals import (
    Approval,
    ApprovalNotFoundError,
    ApprovalNotPendingError,
    decide,
    enqueue,
    get_approval,
    list_approvals,
)
from app.db import Base


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db_session:
        yield db_session


def _enqueue(session: Session, **overrides) -> Approval:
    defaults = {
        "action_id": "action-1",
        "agent_id": "agent-1",
        "tool": "issue_refund",
        "arguments": {"amount": 100},
        "context": None,
        "reason": "Refunds between $50 and $500 need human review.",
        "matched_rule": "refund_medium",
    }
    defaults.update(overrides)
    return enqueue(session, **defaults)


def test_enqueue_creates_a_pending_approval(session: Session) -> None:
    approval = _enqueue(session)

    assert approval.status == "pending"
    assert approval.decided_at is None


def test_get_approval_returns_it_by_action_id(session: Session) -> None:
    _enqueue(session, action_id="action-1")

    approval = get_approval(session, "action-1")

    assert approval.action_id == "action-1"


def test_get_approval_raises_for_unknown_action_id(session: Session) -> None:
    with pytest.raises(ApprovalNotFoundError):
        get_approval(session, "does-not-exist")


def test_decide_approve_sets_status_and_reviewer(session: Session) -> None:
    _enqueue(session, action_id="action-1")

    approval = decide(session, "action-1", approve=True, reviewer="alex", reason="looks fine")

    assert approval.status == "approved"
    assert approval.decided_by == "alex"
    assert approval.decision_reason == "looks fine"
    assert approval.decided_at is not None


def test_decide_reject_sets_status(session: Session) -> None:
    _enqueue(session, action_id="action-1")

    approval = decide(session, "action-1", approve=False, reviewer="alex", reason="too risky")

    assert approval.status == "rejected"


def test_decide_twice_raises_not_pending(session: Session) -> None:
    _enqueue(session, action_id="action-1")
    decide(session, "action-1", approve=True, reviewer="alex", reason="ok")

    with pytest.raises(ApprovalNotPendingError):
        decide(session, "action-1", approve=True, reviewer="alex", reason="ok again")


def test_decide_raises_for_unknown_action_id(session: Session) -> None:
    with pytest.raises(ApprovalNotFoundError):
        decide(session, "does-not-exist", approve=True, reviewer="alex", reason="ok")


def test_list_approvals_filters_by_status(session: Session) -> None:
    _enqueue(session, action_id="action-1")
    _enqueue(session, action_id="action-2")
    decide(session, "action-1", approve=True, reviewer="alex", reason="ok")

    pending = list_approvals(session, status="pending")
    approved = list_approvals(session, status="approved")

    assert [approval.action_id for approval in pending] == ["action-2"]
    assert [approval.action_id for approval in approved] == ["action-1"]


def test_expired_pending_approval_flips_to_expired_on_read(session: Session) -> None:
    approval = _enqueue(session, action_id="action-1")
    approval.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    session.commit()

    refreshed = get_approval(session, "action-1")

    assert refreshed.status == "expired"
    assert refreshed.decided_at is not None


def test_deciding_an_expired_approval_raises_not_pending(session: Session) -> None:
    approval = _enqueue(session, action_id="action-1")
    approval.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    session.commit()

    with pytest.raises(ApprovalNotPendingError):
        decide(session, "action-1", approve=True, reviewer="alex", reason="too late")
