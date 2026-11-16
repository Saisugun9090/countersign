"""FastAPI application entry point."""

import uuid

from fastapi import FastAPI

from app.audit import ChainVerificationResult, append_entry, get_entries_for_action, verify_chain
from app.db import Base, SessionLocal, engine
from app.models import ActionRequest, AuditEntryResponse, DecisionResponse
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

    Every request and its decision are written to the audit log before the
    response is returned.
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
