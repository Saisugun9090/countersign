"""Demo CLI agent: sends a refund request through Countersign and prints the decision.

Usage:
    python demo/refund_agent.py --amount 25 --customer alice@example.com
    python demo/refund_agent.py --amount 250 --customer bob@example.com --wait

Reads the agent's API key from the DEMO_AGENT_API_KEY environment variable
and the gateway's base URL from COUNTERSIGN_URL (default
http://localhost:8000). With --wait, if the action needs approval, the
agent polls GET /v1/actions/{action_id} until a human reviewer decides or
the approval expires.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_POLL_INTERVAL_SECONDS = 2.0


def _api_key() -> str:
    api_key = os.environ.get("DEMO_AGENT_API_KEY")
    if not api_key:
        print("DEMO_AGENT_API_KEY is not set.", file=sys.stderr)
        raise SystemExit(1)
    return api_key


def submit_refund(base_url: str, api_key: str, amount: float, customer: str) -> dict[str, Any]:
    """Send an issue_refund tool call to Countersign and return the decision."""
    response = httpx.post(
        f"{base_url}/v1/actions/evaluate",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"tool": "issue_refund", "arguments": {"amount": amount, "customer": customer}},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def check_status(base_url: str, api_key: str, action_id: str) -> dict[str, Any]:
    """Fetch the current decision for a previously submitted action."""
    response = httpx.get(
        f"{base_url}/v1/actions/{action_id}",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Demo agent: submit a refund through Countersign."
    )
    parser.add_argument("--amount", type=float, required=True, help="Refund amount in dollars.")
    parser.add_argument("--customer", required=True, help="Customer identifier (e.g. an email).")
    parser.add_argument("--base-url", default=os.environ.get("COUNTERSIGN_URL", DEFAULT_BASE_URL))
    parser.add_argument(
        "--wait",
        action="store_true",
        help="If the action needs approval, poll until a human decides or it expires.",
    )
    parser.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL_SECONDS)
    args = parser.parse_args()

    api_key = _api_key()
    decision = submit_refund(args.base_url, api_key, args.amount, args.customer)
    print(f"Decision: {decision['decision']} ({decision['reason']})")

    if decision["decision"] == "needs_approval" and args.wait:
        print("Waiting for a human reviewer...")
        while decision["decision"] == "needs_approval":
            time.sleep(args.poll_interval)
            decision = check_status(args.base_url, api_key, decision["action_id"])
        print(f"Final decision: {decision['decision']} ({decision['reason']})")


if __name__ == "__main__":
    main()
