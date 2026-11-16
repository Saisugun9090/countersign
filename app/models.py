"""Pydantic request/response models for the Countersign API."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class ActionRequest(BaseModel):
    """A tool call an agent wants to take, sent to Countersign before executing it."""

    agent_id: str
    tool: str
    arguments: dict[str, Any]
    context: str | None = None


class DecisionResponse(BaseModel):
    """The outcome of evaluating an ActionRequest against the policy."""

    action_id: UUID
    decision: Literal["allow", "block", "needs_approval"]
    reason: str
    matched_rule: str | None
