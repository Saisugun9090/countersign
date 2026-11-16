"""Unit tests for agent API key authentication."""

import pytest
import yaml

from app.auth import AgentRegistry, authenticate, hash_key, load_agents


def _registry(*pairs: tuple[str, str]) -> AgentRegistry:
    return AgentRegistry(
        agents=[{"agent_id": agent_id, "key_hash": hash_key(key)} for agent_id, key in pairs]
    )


def test_authenticate_returns_agent_id_for_matching_key() -> None:
    registry = _registry(("agent-1", "secret-key"))

    assert authenticate(registry, "secret-key") == "agent-1"


def test_authenticate_returns_none_for_unknown_key() -> None:
    registry = _registry(("agent-1", "secret-key"))

    assert authenticate(registry, "wrong-key") is None


def test_authenticate_picks_the_right_agent_among_several() -> None:
    registry = _registry(("agent-1", "key-one"), ("agent-2", "key-two"))

    assert authenticate(registry, "key-two") == "agent-2"


def test_load_agents_reads_yaml_file(tmp_path) -> None:
    agents_file = tmp_path / "agents.yaml"
    agents_file.write_text(
        yaml.dump({"agents": [{"agent_id": "agent-1", "key_hash": hash_key("secret-key")}]})
    )

    registry = load_agents(agents_file)

    assert authenticate(registry, "secret-key") == "agent-1"


def test_load_agents_fails_loudly_on_missing_agents_key(tmp_path) -> None:
    agents_file = tmp_path / "agents.yaml"
    agents_file.write_text(yaml.dump({}))

    with pytest.raises(Exception, match="agents"):
        load_agents(agents_file)


def test_load_agents_fails_loudly_on_missing_key_hash(tmp_path) -> None:
    agents_file = tmp_path / "agents.yaml"
    agents_file.write_text(yaml.dump({"agents": [{"agent_id": "agent-1"}]}))

    with pytest.raises(Exception, match="key_hash"):
        load_agents(agents_file)
