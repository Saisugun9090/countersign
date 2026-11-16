"""FastAPI application entry point."""

import hmac
import os
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException

from app.approvals import (
    ApprovalNotFoundError,
    ApprovalNotPendingError,
    decide,
    enqueue,
    get_approval,
    list_approvals,
)
from app.audit import ChainVerificationResult, append_entry, get_entries_for_action, verify_chain
from app.db import Base, SessionLocal, engine
from app.models import (
    ActionRequest,
    ApprovalDecisionRequest,
    ApprovalResponse,
    AuditEntryResponse,
    DecisionResponse,
)
from app.policy import evaluate, load_policy

app = FastAPI(title="Countersign")
policy = load_policy()

Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    return {"status": "ok"}


@app.post("/v1/actions/evaluate")
def evaluate_action(request: ActionRequest) -> DecisionResponse:
    """Evaluate an agent's proposed tool call against the loaded policy.

    Every request and its decision are written to the audit log. A
    `needs_approval` decision also enqueues the action for human review.
    """
    result = evaluate(policy, request.tool, request.arguments)
    action_id = uuid.uuid4()

    with SessionLocal() as session:
        append_entry(
            session,
            action_id=str(action_id),
            agent_id=request.agent_id,
            tool=request.tool,
            arguments=request.arguments,
            context=request.context,
            decision=result.decision,
            reason=result.reason,
            matched_rule=result.matched_rule,
        )
        if result.decision == "needs_approval":
            enqueue(
                session,
                action_id=str(action_id),
                agent_id=request.agent_id,
                tool=request.tool,
                arguments=request.arguments,
                context=request.context,
                reason=result.reason,
                matched_rule=result.matched_rule,
            )

    return DecisionResponse(
        action_id=action_id,
        decision=result.decision,
        reason=result.reason,
        matched_rule=result.matched_rule,
    )


@app.get("/v1/audit")
def get_audit_entries(action_id: str) -> list[AuditEntryResponse]:
    """Return the audit log entries recorded for a given action_id."""
    with SessionLocal() as session:
        entries = get_entries_for_action(session, action_id)
        return [AuditEntryResponse.model_validate(entry) for entry in entries]


@app.get("/v1/audit/verify")
def verify_audit_log() -> ChainVerificationResult:
    """Walk the audit log and confirm no entry has been edited or deleted."""
    with SessionLocal() as session:
        return verify_chain(session)


def require_reviewer_token(authorization: str | None = Header(default=None)) -> None:
    """Require a valid `Authorization: Bearer <REVIEWER_TOKEN>` header.

    A separate shared secret, not per-agent API keys (those arrive with the
    demo agent in a later feature) — only a human reviewer should be able to
    see or decide on queued approvals.
    """
    token = os.environ.get("REVIEWER_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="REVIEWER_TOKEN is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    provided = authorization.removeprefix("Bearer ")
    if not hmac.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="Invalid reviewer token")


approvals_router = APIRouter(
    prefix="/v1/approvals", tags=["approvals"], dependencies=[Depends(require_reviewer_token)]
)


@approvals_router.get("")
def list_pending_approvals(
    status: Literal["pending", "approved", "rejected", "expired"] | None = None,
) -> list[ApprovalResponse]:
    """List queued approvals, optionally filtered by status."""
    with SessionLocal() as session:
        approvals = list_approvals(session, status=status)
        return [ApprovalResponse.model_validate(approval) for approval in approvals]


@approvals_router.get("/{action_id}")
def get_one_approval(action_id: str) -> ApprovalResponse:
    """Fetch one queued approval by its action_id."""
    with SessionLocal() as session:
        try:
            approval = get_approval(session, action_id)
        except ApprovalNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="No approval found for this action_id"
            ) from exc
        return ApprovalResponse.model_validate(approval)


@approvals_router.post("/{action_id}/approve")
def approve_action(action_id: str, request: ApprovalDecisionRequest) -> ApprovalResponse:
    """Approve a pending action, recording who approved it and why."""
    with SessionLocal() as session:
        try:
            approval = decide(
                session, action_id, approve=True, reviewer=request.reviewer, reason=request.reason
            )
        except ApprovalNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="No approval found for this action_id"
            ) from exc
        except ApprovalNotPendingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApprovalResponse.model_validate(approval)


@approvals_router.post("/{action_id}/reject")
def reject_action(action_id: str, request: ApprovalDecisionRequest) -> ApprovalResponse:
    """Reject a pending action, recording who rejected it and why."""
    with SessionLocal() as session:
        try:
            approval = decide(
                session, action_id, approve=False, reviewer=request.reviewer, reason=request.reason
            )
        except ApprovalNotFoundError as exc:
            raise HTTPException(
                status_code=404, detail="No approval found for this action_id"
            ) from exc
        except ApprovalNotPendingError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return ApprovalResponse.model_validate(approval)


app.include_router(approvals_router)
