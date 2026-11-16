"""Integration tests for the audit log API endpoints."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_AGENT_API_KEY

client = TestClient(app)

AGENT_HEADERS = {"Authorization": f"Bearer {TEST_AGENT_API_KEY}"}


def test_evaluate_action_is_recorded_in_audit_log() -> None:
    response = client.post(
        "/v1/actions/evaluate",
        json={"tool": "issue_refund", "arguments": {"amount": 20}},
        headers=AGENT_HEADERS,
    )
    action_id = response.json()["action_id"]

    audit_response = client.get("/v1/audit", params={"action_id": action_id})

    assert audit_response.status_code == 200
    entries = audit_response.json()
    assert len(entries) == 1
    assert entries[0]["decision"] == "allow"
    assert entries[0]["matched_rule"] == "refund_small"


def test_audit_entries_for_unknown_action_id_is_empty() -> None:
    response = client.get("/v1/audit", params={"action_id": "does-not-exist"})

    assert response.status_code == 200
    assert response.json() == []


def test_audit_log_verifies_as_valid() -> None:
    client.post(
        "/v1/actions/evaluate",
        json={"tool": "read_record", "arguments": {}},
        headers=AGENT_HEADERS,
    )

    response = client.get("/v1/audit/verify")

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["entries_checked"] >= 1
