"""Unit tests for the audit log, against an isolated in-memory SQLite database."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.audit import GENESIS_HASH, append_entry, get_entries_for_action, verify_chain
from app.db import Base


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db_session:
        yield db_session


def _append(session: Session, **overrides):
    defaults = {
        "action_id": "action-1",
        "agent_id": "agent-1",
        "tool": "issue_refund",
        "arguments": {"amount": 10},
        "context": None,
        "decision": "allow",
        "reason": "ok",
        "matched_rule": "refund_small",
    }
    defaults.update(overrides)
    return append_entry(session, **defaults)


def test_first_entry_chains_to_genesis_hash(session: Session) -> None:
    entry = _append(session)

    assert entry.prev_hash == GENESIS_HASH
    assert len(entry.hash) == 64


def test_second_entry_chains_to_first_entrys_hash(session: Session) -> None:
    first = _append(session, action_id="action-1")
    second = _append(session, action_id="action-2")

    assert second.prev_hash == first.hash
    assert second.hash != first.hash


def test_verify_chain_passes_on_untouched_log(session: Session) -> None:
    _append(session, action_id="action-1")
    _append(session, action_id="action-2")

    result = verify_chain(session)

    assert result.valid is True
    assert result.entries_checked == 2
    assert result.error is None


def test_verify_chain_passes_on_empty_log(session: Session) -> None:
    result = verify_chain(session)

    assert result.valid is True
    assert result.entries_checked == 0


def test_verify_chain_detects_edited_entry(session: Session) -> None:
    entry = _append(session, action_id="action-1")
    _append(session, action_id="action-2")

    entry.reason = "tampered"
    session.commit()

    result = verify_chain(session)

    assert result.valid is False
    assert f"entry {entry.id}" in result.error


def test_verify_chain_detects_deleted_entry(session: Session) -> None:
    first = _append(session, action_id="action-1")
    _append(session, action_id="action-2")

    session.delete(first)
    session.commit()

    result = verify_chain(session)

    assert result.valid is False


def test_get_entries_for_action_filters_by_action_id(session: Session) -> None:
    _append(session, action_id="action-1")
    _append(session, action_id="action-2")
    _append(session, action_id="action-1")

    entries = get_entries_for_action(session, "action-1")

    assert [entry.action_id for entry in entries] == ["action-1", "action-1"]
