"""YAML-based policy engine: ordered, first-match-wins rules over agent tool calls."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

Decision = Literal["allow", "block", "needs_approval"]
ConditionOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains"]

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "default.yaml"

_OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "contains": lambda a, b: b in a,
}


class Condition(BaseModel):
    """A single check against one argument of an action."""

    field: str
    op: ConditionOp
    value: Any


class Rule(BaseModel):
    """One policy rule: a tool-name glob plus optional conditions, first-match-wins."""

    name: str
    tool: str
    decision: Decision
    reason: str
    conditions: list[Condition] = Field(default_factory=list)


class Default(BaseModel):
    """The decision used when no rule matches an action."""

    decision: Decision
    reason: str


class Policy(BaseModel):
    """An ordered list of rules plus the default decision for unmatched actions."""

    rules: list[Rule]
    default: Default


class PolicyDecision(BaseModel):
    """The outcome of evaluating one action against a Policy."""

    decision: Decision
    reason: str
    matched_rule: str | None


def load_policy(path: str | Path | None = None) -> Policy:
    """Load and validate a policy YAML file.

    Raises `yaml.YAMLError` on invalid YAML and `pydantic.ValidationError` on a
    well-formed file that is missing required fields or has bad values, so a
    broken policy file fails loudly at startup rather than silently.
    """
    if path is not None:
        resolved = Path(path)
    else:
        resolved = Path(os.environ.get("POLICY_PATH", DEFAULT_POLICY_PATH))
    with open(resolved) as f:
        raw = yaml.safe_load(f)
    return Policy.model_validate(raw)


def _condition_matches(condition: Condition, arguments: dict[str, Any]) -> bool:
    if condition.field not in arguments:
        return False
    try:
        return _OPS[condition.op](arguments[condition.field], condition.value)
    except TypeError:
        return False


def _rule_matches(rule: Rule, tool: str, arguments: dict[str, Any]) -> bool:
    if not fnmatch.fnmatchcase(tool, rule.tool):
        return False
    return all(_condition_matches(condition, arguments) for condition in rule.conditions)


def evaluate(policy: Policy, tool: str, arguments: dict[str, Any]) -> PolicyDecision:
    """Evaluate a tool call against the policy's rules, first match wins."""
    for rule in policy.rules:
        if _rule_matches(rule, tool, arguments):
            return PolicyDecision(
                decision=rule.decision, reason=rule.reason, matched_rule=rule.name
            )
    return PolicyDecision(
        decision=policy.default.decision, reason=policy.default.reason, matched_rule=None
    )
