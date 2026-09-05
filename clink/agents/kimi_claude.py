"""Kimi Code through the Claude Code CLI."""

from __future__ import annotations

from utils.env import get_env

from .base import CLIAgentError
from .claude import ClaudeAgent


class KimiClaudeAgent(ClaudeAgent):
    """Run Claude Code's agent loop against Kimi's Anthropic-compatible API."""

    requires_explicit_working_dir = True

    def _build_environment(self) -> dict[str, str]:
        env = super()._build_environment()
        api_key = (get_env("KIMI_CLAUDE_API_KEY") or get_env("KIMI_API_KEY") or "").strip()
        if not api_key:
            raise CLIAgentError(
                "Kimi through Claude Code requires KIMI_CLAUDE_API_KEY or KIMI_API_KEY in the PAL environment."
            )

        for key in list(env):
            if key.startswith(("ANTHROPIC_", "CLAUDE_")) and key not in self.client.env:
                del env[key]

        env.pop("KIMI_CLAUDE_API_KEY", None)
        env.pop("KIMI_API_KEY", None)
        env.pop("MOONSHOT_API_KEY", None)
        env["ANTHROPIC_API_KEY"] = api_key
        return env
