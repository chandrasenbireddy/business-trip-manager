"""Shared Strands agent base: tool registration + OTel + Secret Manager wiring.

Every BTM agent (orchestrator, planner, booking, memory) subclasses this
instead of `strands.Agent` directly, so instrumentation and credential
resolution are never opt-in per agent.
"""

from strands import Agent

from tools import secrets
from tools.telemetry import traced


class BtmAgent(Agent):
    """Strands agent with the constitution's mandatory hooks pre-wired.

    - `traced(node_name)` MUST decorate every tool method (Principle XV).
    - `self.resolve_secret(path)` is the only sanctioned way to read a
      credential — never accept one as a constructor/call argument (Principle XIII).
    """

    agent_version: str = "0.1.0"

    def resolve_secret(self, secret_path: str) -> str:
        return secrets.resolve(secret_path)


__all__ = ["BtmAgent", "traced"]
