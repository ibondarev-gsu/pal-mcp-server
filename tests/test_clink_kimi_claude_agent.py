"""Tests for Kimi Code routed through the Claude Code CLI."""

import asyncio
import json
import os
import shutil

import pytest

from clink import get_registry
from clink.agents.base import CLIAgentError
from clink.agents.kimi_claude import KimiClaudeAgent


class DummyProcess:
    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self, _input):
        return self._stdout, self._stderr


@pytest.fixture()
def kimi_agent():
    client = get_registry().get_client("kimi")
    role = client.get_role("codereviewer")
    return KimiClaudeAgent(client), role


@pytest.mark.asyncio
async def test_kimi_agent_routes_claude_to_kimi_without_leaking_key(monkeypatch, kimi_agent, tmp_path):
    agent, role = kimi_agent
    process = DummyProcess(
        stdout=json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": "No blockers.",
                "modelUsage": {"kimi-for-coding": {"inputTokens": 10, "outputTokens": 3}},
            }
        ).encode()
    )
    invocation: dict = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        invocation["args"] = args
        invocation["kwargs"] = kwargs
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", lambda _name: "/opt/homebrew/bin/claude")
    monkeypatch.setenv("KIMI_CLAUDE_API_KEY", "secret-kimi-code-key")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "unrelated-claude-token")
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "x-corporate-token: secret")
    monkeypatch.setenv("ANTHROPIC_SMALL_FAST_MODEL", "claude-haiku-from-user-settings")
    monkeypatch.setenv("CLAUDE_CODE_UNRELATED_SETTING", "user-value")

    result = await agent.run(
        role=role,
        prompt="Review the repository",
        system_prompt="Be critical.",
        files=[],
        images=[],
        working_dir=tmp_path,
    )

    child_env = invocation["kwargs"]["env"]
    assert child_env["ANTHROPIC_BASE_URL"] == "https://api.kimi.com/coding/"
    assert child_env["ANTHROPIC_API_KEY"] == "secret-kimi-code-key"
    assert "ANTHROPIC_AUTH_TOKEN" not in child_env
    assert "ANTHROPIC_CUSTOM_HEADERS" not in child_env
    assert "ANTHROPIC_SMALL_FAST_MODEL" not in child_env
    assert "CLAUDE_CODE_UNRELATED_SETTING" not in child_env
    assert "KIMI_CLAUDE_API_KEY" not in child_env
    assert "KIMI_API_KEY" not in child_env
    assert child_env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "262144"
    assert invocation["kwargs"]["cwd"] == str(tmp_path)
    assert "secret-kimi-code-key" not in " ".join(result.sanitized_command)
    assert "--bare" in result.sanitized_command
    assert result.sanitized_command[result.sanitized_command.index("--setting-sources") + 1] == ""
    assert "--permission-mode" in result.sanitized_command
    assert "--append-system-prompt" in result.sanitized_command
    assert result.parsed.content == "No blockers."
    assert result.parsed.metadata["model_used"] == "kimi-for-coding"
    assert os.environ["ANTHROPIC_CUSTOM_HEADERS"] == "x-corporate-token: secret"
    assert os.environ["CLAUDE_CODE_UNRELATED_SETTING"] == "user-value"


def test_kimi_agent_requires_dedicated_or_pal_kimi_key(monkeypatch, kimi_agent):
    agent, _ = kimi_agent
    monkeypatch.delenv("KIMI_CLAUDE_API_KEY", raising=False)
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    with pytest.raises(CLIAgentError, match="KIMI_CLAUDE_API_KEY or KIMI_API_KEY"):
        agent._build_environment()


def test_kimi_agent_rejects_whitespace_only_key(monkeypatch, kimi_agent):
    agent, _ = kimi_agent
    monkeypatch.setenv("KIMI_CLAUDE_API_KEY", "  ")
    monkeypatch.delenv("KIMI_API_KEY", raising=False)

    with pytest.raises(CLIAgentError, match="KIMI_CLAUDE_API_KEY or KIMI_API_KEY"):
        agent._build_environment()


def test_kimi_agent_falls_back_to_pal_kimi_key(monkeypatch, kimi_agent):
    agent, _ = kimi_agent
    monkeypatch.delenv("KIMI_CLAUDE_API_KEY", raising=False)
    monkeypatch.setenv("KIMI_API_KEY", "shared-pal-key")

    env = agent._build_environment()

    assert env["ANTHROPIC_API_KEY"] == "shared-pal-key"


@pytest.mark.asyncio
async def test_kimi_agent_kills_child_when_host_cancels(monkeypatch, kimi_agent, tmp_path):
    agent, role = kimi_agent

    class BlockingProcess:
        returncode = None

        def __init__(self):
            self.communicate_calls = 0
            self.killed = False
            self.started = asyncio.Event()

        async def communicate(self, _input=None):
            self.communicate_calls += 1
            if self.communicate_calls == 1:
                self.started.set()
                await asyncio.Event().wait()
            return b"", b""

        def kill(self):
            self.killed = True

    process = BlockingProcess()

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", lambda _name: "/opt/homebrew/bin/claude")
    monkeypatch.setenv("KIMI_CLAUDE_API_KEY", "secret-kimi-code-key")

    task = asyncio.create_task(
        agent.run(
            role=role,
            prompt="Review the repository",
            system_prompt="Be critical.",
            files=[],
            images=[],
            working_dir=tmp_path,
        )
    )
    await process.started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.killed is True
    assert process.communicate_calls == 2
