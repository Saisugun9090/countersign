import pytest
import yaml

from app.policy import evaluate, load_policy

POLICY = load_policy("policies/default.yaml")

# (tool, arguments, expected_decision, expected_rule)
CASES = [
    ("issue_refund", {"amount": 10}, "allow", "refund_small"),
    ("issue_refund", {"amount": 50}, "allow", "refund_small"),
    ("issue_refund", {"amount": 51}, "needs_approval", "refund_medium"),
    ("issue_refund", {"amount": 500}, "needs_approval", "refund_medium"),
    ("issue_refund", {"amount": 501}, "block", "refund_large"),
    ("delete_record", {"id": 1}, "block", "block_deletes"),
    ("delete_user", {}, "block", "block_deletes"),
    ("send_email", {"to": "pat@our-company.com"}, "allow", "email_internal"),
    ("send_email", {"to": "pat@example.com"}, "needs_approval", "email_external"),
    ("read_record", {"id": 1}, "allow", "read_allowed"),
    ("read_anything_at_all", {}, "allow", "read_allowed"),
]


@pytest.mark.parametrize(("tool", "arguments", "expected_decision", "expected_rule"), CASES)
def test_rule_matches(
    tool: str, arguments: dict, expected_decision: str, expected_rule: str
) -> None:
    result = evaluate(POLICY, tool, arguments)

    assert result.decision == expected_decision
    assert result.matched_rule == expected_rule


def test_unmatched_tool_falls_back_to_default() -> None:
    result = evaluate(POLICY, "transfer_funds", {"amount": 100})

    assert result.decision == "needs_approval"
    assert result.matched_rule is None


def test_glob_matching_is_case_sensitive_and_prefix_based() -> None:
    assert evaluate(POLICY, "delete_", {}).matched_rule == "block_deletes"
    assert evaluate(POLICY, "DELETE_RECORD", {}).matched_rule is None


def test_malformed_policy_missing_default_fails_loudly(tmp_path) -> None:
    bad_policy = tmp_path / "bad.yaml"
    bad_policy.write_text(yaml.dump({"rules": []}))

    with pytest.raises(Exception, match="default"):
        load_policy(bad_policy)


def test_malformed_policy_bad_decision_fails_loudly(tmp_path) -> None:
    bad_policy = tmp_path / "bad.yaml"
    bad_policy.write_text(
        yaml.dump(
            {
                "rules": [{"name": "x", "tool": "*", "decision": "maybe", "reason": "r"}],
                "default": {"decision": "needs_approval", "reason": "r"},
            }
        )
    )

    with pytest.raises(Exception, match="decision"):
        load_policy(bad_policy)
