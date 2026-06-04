"""Entry module for `adk web` / `adk run`.

The ADK agent loader looks for `root_agent` at the package level
(`multi_agent.agent.root_agent`). The actual definition lives in the
coordinator package; re-export it here.
"""
from multi_agent.coordinator_agent.agent import root_agent

__all__ = ["root_agent"]
