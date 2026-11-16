from fastapi.testclient import TestClient

from app.main import app, require_agent_api_key
from tests.conftest import TEST_AGENT_API_KEY

client = TestClient(app)

AGENT_HEADERS = {"Authorization": f"Bearer {TEST_AGENT_API_KEY}"}


def test_evaluate_action_allows_small_refund() -> None:
    response = client.post(
        "/v1/actions/evaluate",
        json={"tool": "issue_refund", "arguments": {"amount": 20}},
        headers=AGENT_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "allow"
    assert body["matched_rule"] == "refund_small"


def test_evaluate_action_blocks_delete() -> None:
    response = client.post(
        "/v1/actions/evaluate",
        json={"tool": "delete_record", "arguments": {"id": 1}},
        headers=AGENT_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "block"


def test_evaluate_action_defaults_to_needs_approval() -> None:
    response = client.post(
        "/v1/actions/evaluate",
        json={"tool": "transfer_funds", "arguments": {"amount": 100}},
        headers=AGENT_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "needs_approval"
    assert body["matched_rule"] is None


def test_evaluate_action_requires_an_api_key() -> None:
    response = client.post(
        "/v1/actions/evaluate", json={"tool": "issue_refund", "arguments": {"amount": 20}}
    )

    assert response.status_code == 401


def test_evaluate_action_rejects_an_unknown_api_key() -> None:
    response = client.post(
        "/v1/actions/evaluate",
        json={"tool": "issue_refund", "arguments": {"amount": 20}},
        headers={"Authorization": "Bearer not-a-real-key"},
    )

    assert response.status_code == 401


def test_get_action_status_reflects_the_original_decision() -> None:
    evaluate_response = client.post(
        "/v1/actions/evaluate",
        json={"tool": "issue_refund", "arguments": {"amount": 20}},
        headers=AGENT_HEADERS,
    )
    action_id = evaluate_response.json()["action_id"]

    status_response = client.get(f"/v1/actions/{action_id}", headers=AGENT_HEADERS)

    assert status_response.status_code == 200
    assert status_response.json()["decision"] == "allow"


def test_get_action_status_is_404_for_unknown_action() -> None:
    response = client.get("/v1/actions/does-not-exist", headers=AGENT_HEADERS)

    assert response.status_code == 404


def test_get_action_status_is_403_for_another_agents_action() -> None:
    evaluate_response = client.post(
        "/v1/actions/evaluate",
        json={"tool": "issue_refund", "arguments": {"amount": 20}},
        headers=AGENT_HEADERS,
    )
    action_id = evaluate_response.json()["action_id"]

    app.dependency_overrides[require_agent_api_key] = lambda: "some-other-agent"
    try:
        response = client.get(f"/v1/actions/{action_id}", headers=AGENT_HEADERS)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
