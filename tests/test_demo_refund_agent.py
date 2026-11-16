"""Tests for the demo refund agent CLI, with httpx calls faked via monkeypatch."""

import pytest

from demo import refund_agent


class _FakeResponse:
    def __init__(self, body: dict) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._body


def test_api_key_raises_systemexit_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("DEMO_AGENT_API_KEY", raising=False)

    with pytest.raises(SystemExit):
        refund_agent._api_key()


def test_api_key_returns_the_env_value(monkeypatch) -> None:
    monkeypatch.setenv("DEMO_AGENT_API_KEY", "some-key")

    assert refund_agent._api_key() == "some-key"


def test_submit_refund_posts_the_expected_payload(monkeypatch) -> None:
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse(
            {"decision": "allow", "reason": "ok", "action_id": "x", "matched_rule": "r"}
        )

    monkeypatch.setattr(refund_agent.httpx, "post", fake_post)

    result = refund_agent.submit_refund(
        "http://example.test", "key-123", 10.0, "alice@example.com"
    )

    assert result["decision"] == "allow"
    assert captured["url"] == "http://example.test/v1/actions/evaluate"
    assert captured["headers"]["Authorization"] == "Bearer key-123"
    assert captured["json"]["tool"] == "issue_refund"
    assert captured["json"]["arguments"] == {"amount": 10.0, "customer": "alice@example.com"}


def test_check_status_gets_the_expected_url(monkeypatch) -> None:
    captured = {}

    def fake_get(url, headers, timeout):
        captured["url"] = url
        return _FakeResponse(
            {"decision": "approved", "reason": "ok", "action_id": "x", "matched_rule": None}
        )

    monkeypatch.setattr(refund_agent.httpx, "get", fake_get)

    refund_agent.check_status("http://example.test", "key-123", "action-42")

    assert captured["url"] == "http://example.test/v1/actions/action-42"
