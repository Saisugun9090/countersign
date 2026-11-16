"""Integration tests for the approval queue API endpoints."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_AGENT_API_KEY

client = TestClient(app)

REVIEWER_HEADERS = {"Authorization": "Bearer test-reviewer-token"}
AGENT_HEADERS = {"Authorization": f"Bearer {TEST_AGENT_API_KEY}"}


def _create_pending_approval() -> str:
    response = client.post(
        "/v1/actions/evaluate",
        json={"tool": "issue_refund", "arguments": {"amount": 100}},
        headers=AGENT_HEADERS,
    )
    assert response.json()["decision"] == "needs_approval"
    return response.json()["action_id"]


def test_evaluate_needs_approval_creates_a_pending_approval() -> None:
    action_id = _create_pending_approval()

    response = client.get(f"/v1/approvals/{action_id}", headers=REVIEWER_HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_list_approvals_requires_reviewer_token() -> None:
    response = client.get("/v1/approvals")

    assert response.status_code == 401


def test_approve_endpoint_requires_reviewer_token() -> None:
    action_id = _create_pending_approval()

    response = client.post(
        f"/v1/approvals/{action_id}/approve", json={"reviewer": "alex", "reason": "ok"}
    )

    assert response.status_code == 401


def test_approve_endpoint_rejects_wrong_token() -> None:
    action_id = _create_pending_approval()

    response = client.post(
        f"/v1/approvals/{action_id}/approve",
        json={"reviewer": "alex", "reason": "ok"},
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401


def test_approve_endpoint_transitions_to_approved() -> None:
    action_id = _create_pending_approval()

    response = client.post(
        f"/v1/approvals/{action_id}/approve",
        json={"reviewer": "alex", "reason": "looks fine"},
        headers=REVIEWER_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["decided_by"] == "alex"


def test_reject_endpoint_transitions_to_rejected() -> None:
    action_id = _create_pending_approval()

    response = client.post(
        f"/v1/approvals/{action_id}/reject",
        json={"reviewer": "alex", "reason": "too risky"},
        headers=REVIEWER_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_approving_twice_returns_conflict() -> None:
    action_id = _create_pending_approval()
    client.post(
        f"/v1/approvals/{action_id}/approve",
        json={"reviewer": "alex", "reason": "ok"},
        headers=REVIEWER_HEADERS,
    )

    response = client.post(
        f"/v1/approvals/{action_id}/approve",
        json={"reviewer": "alex", "reason": "ok again"},
        headers=REVIEWER_HEADERS,
    )

    assert response.status_code == 409


def test_get_unknown_approval_returns_404() -> None:
    response = client.get("/v1/approvals/does-not-exist", headers=REVIEWER_HEADERS)

    assert response.status_code == 404


def test_approved_action_is_recorded_in_audit_log() -> None:
    action_id = _create_pending_approval()
    client.post(
        f"/v1/approvals/{action_id}/approve",
        json={"reviewer": "alex", "reason": "looks fine"},
        headers=REVIEWER_HEADERS,
    )

    audit_response = client.get("/v1/audit", params={"action_id": action_id})
    entries = audit_response.json()

    assert len(entries) == 2
    assert entries[0]["decision"] == "needs_approval"
    assert entries[1]["decision"] == "allow"
    assert entries[1]["agent_id"] == "alex"
