"""FastAPI application entry point."""

import uuid

from fastapi import FastAPI

from app.models import ActionRequest, DecisionResponse
from app.policy import evaluate, load_policy

app = FastAPI(title="Countersign")
policy = load_policy()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    return {"status": "ok"}


@app.post("/v1/actions/evaluate")
def evaluate_action(request: ActionRequest) -> DecisionResponse:
    """Evaluate an agent's proposed tool call against the loaded policy."""
    result = evaluate(policy, request.tool, request.arguments)
    return DecisionResponse(
        action_id=uuid.uuid4(),
        decision=result.decision,
        reason=result.reason,
        matched_rule=result.matched_rule,
    )
