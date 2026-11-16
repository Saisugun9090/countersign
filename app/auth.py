"""API key authentication for agents calling the Countersign API.

Agents are registered in agents.yaml by id and the SHA-256 hash of their
key, so the raw key is never stored at rest. A request's bearer token is
hashed and looked up against the registry: an agent can't simply claim to
be a given agent_id in its request body, since the authenticated identity
always comes from the key, never from anything the client wrote.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import yaml
from fastapi import Header, HTTPException
from pydantic import BaseModel

DEFAULT_AGENTS_PATH = Path(__file__).resolve().parent.parent / "agents.yaml"


class RegisteredAgent(BaseModel):
    """One agent allowed to call the API, identified by its key's hash."""

    agent_id: str
    key_hash: str


class AgentRegistry(BaseModel):
    """The set of agents registered to call the API."""

    agents: list[RegisteredAgent]


def hash_key(api_key: str) -> str:
    """SHA-256 hash of an API key, in the form stored in agents.yaml."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def load_agents(path: str | Path | None = None) -> AgentRegistry:
    """Load and validate the agent registry YAML file.

    Raises on invalid YAML or a well-formed file missing required fields,
    so a broken registry fails loudly at startup rather than silently.
    """
    if path is not None:
        resolved = Path(path)
    else:
        resolved = Path(os.environ.get("AGENTS_PATH", DEFAULT_AGENTS_PATH))
    with open(resolved) as f:
        raw = yaml.safe_load(f)
    return AgentRegistry.model_validate(raw)


def authenticate(registry: AgentRegistry, api_key: str) -> str | None:
    """Return the agent_id matching this API key's hash, or None."""
    key_hash = hash_key(api_key)
    for agent in registry.agents:
        if agent.key_hash == key_hash:
            return agent.agent_id
    return None


def make_require_agent_api_key(registry: AgentRegistry):
    """Build a FastAPI dependency that authenticates a request's bearer API key.

    A factory, not a module-level dependency, so the registry is loaded once
    by the caller (main.py, alongside the policy) rather than as an import-time
    side effect of this module.
    """

    def require_agent_api_key(authorization: str | None = Header(default=None)) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        api_key = authorization.removeprefix("Bearer ")
        agent_id = authenticate(registry, api_key)
        if agent_id is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return agent_id

    return require_agent_api_key
