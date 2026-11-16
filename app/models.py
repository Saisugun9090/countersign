"""Pydantic request/response models for the Countersign API."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ActionRequest(BaseModel):
    """A tool call an agent wants to take, sent to Countersign before executing it.

    The caller's identity comes from its API key (see app/auth.py), not from
    the request body, so a request can't claim to be a different agent.
    """

    tool: str
    arguments: dict[str, Any]
    context: str | None = None


class DecisionResponse(BaseModel):
    """The outcome of evaluating an ActionRequest against the policy."""

    action_id: UUID
    decision: Literal["allow", "block", "needs_approval"]
    reason: str
    matched_rule: str | None


class AuditEntryResponse(BaseModel):
    """One entry of the hash-chained audit log, as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    action_id: str
    agent_id: str
    tool: str
    arguments: dict[str, Any]
    context: str | None
    decision: Literal["allow", "block", "needs_approval"]
    reason: str
    matched_rule: str | None
    prev_hash: str
    hash: str
    created_at: datetime


class ApprovalResponse(BaseModel):
    """One entry in the human approval queue, as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    action_id: str
    agent_id: str
    tool: str
    arguments: dict[str, Any]
    context: str | None
    reason: str
    matched_rule: str | None
    status: Literal["pending", "approved", "rejected", "expired"]
    created_at: datetime
    expires_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    decision_reason: str | None


class ApprovalDecisionRequest(BaseModel):
    """A human reviewer's approve/reject decision on a queued action."""

    reviewer: str
    reason: str
