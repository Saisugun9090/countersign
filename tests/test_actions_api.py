from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_evaluate_action_allows_small_refund() -> None:
    response = client.post(
        "/v1/actions/evaluate",
        json={"agent_id": "agent-1", "tool": "issue_refund", "arguments": {"amount": 20}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "allow"
    assert body["matched_rule"] == "refund_small"


def test_evaluate_action_blocks_delete() -> None:
    response = client.post(
        "/v1/actions/evaluate",
        json={"agent_id": "agent-1", "tool": "delete_record", "arguments": {"id": 1}},
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "block"


def test_evaluate_action_defaults_to_needs_approval() -> None:
    response = client.post(
        "/v1/actions/evaluate",
        json={"agent_id": "agent-1", "tool": "transfer_funds", "arguments": {"amount": 100}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "needs_approval"
    assert body["matched_rule"] is None
