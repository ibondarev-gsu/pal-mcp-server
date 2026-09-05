import json

import pytest

from clink import get_registry
from clink.agents import AgentOutput, create_agent
from clink.agents.kimi_claude import KimiClaudeAgent
from clink.parsers.base import ParsedCLIResponse
from tools.clink import MAX_RESPONSE_CHARS, CLinkTool
from tools.shared.exceptions import ToolExecutionError


@pytest.mark.asyncio
async def test_clink_tool_execute(monkeypatch, tmp_path):
    tool = CLinkTool()
    invocation = {}

    async def fake_run(**kwargs):
        return AgentOutput(
            parsed=ParsedCLIResponse(content="Hello from Gemini", metadata={"model_used": "gemini-2.5-pro"}),
            sanitized_command=["gemini", "-o", "json"],
            returncode=0,
            stdout='{"response": "Hello from Gemini"}',
            stderr="",
            duration_seconds=0.42,
            parser_name="gemini_json",
            output_file_content=None,
        )

    class DummyAgent:
        injects_system_prompt_externally = False
        requires_explicit_working_dir = False

        async def run(self, **kwargs):
            invocation.update(kwargs)
            return await fake_run(**kwargs)

    def fake_create_agent(client):
        return DummyAgent()

    monkeypatch.setattr("tools.clink.create_agent", fake_create_agent)

    arguments = {
        "prompt": "Summarize the project",
        "cli_name": "gemini",
        "role": "default",
        "absolute_file_paths": [],
        "images": [],
        "working_directory_absolute_path": str(tmp_path),
    }

    results = await tool.execute(arguments)
    assert len(results) == 1

    payload = json.loads(results[0].text)
    assert payload["status"] in {"success", "continuation_available"}
    assert "Hello from Gemini" in payload["content"]
    metadata = payload.get("metadata", {})
    assert metadata.get("cli_name") == "gemini"
    assert metadata.get("command") == ["gemini", "-o", "json"]
    assert invocation["working_dir"] == tmp_path.resolve()


def test_registry_lists_roles():
    registry = get_registry()
    clients = registry.list_clients()
    assert {"codex", "gemini", "kimi"}.issubset(set(clients))
    roles = registry.list_roles("gemini")
    assert "default" in roles
    assert "default" in registry.list_roles("codex")
    assert "codereviewer" in registry.list_roles("kimi")
    codex_client = registry.get_client("codex")
    # Verify codex uses --enable web_search_request (not --search which is unsupported by exec)
    assert codex_client.config_args == [
        "--json",
        "--dangerously-bypass-approvals-and-sandbox",
        "--enable",
        "web_search_request",
    ]
    kimi_client = registry.get_client("kimi")
    assert kimi_client.executable == ["claude"]
    assert kimi_client.runner == "kimi_claude"
    assert kimi_client.timeout_seconds == 1100
    assert kimi_client.config_args == [
        "--bare",
        "--setting-sources",
        "",
        "--permission-mode",
        "plan",
        "--tools",
        "Read,Glob,Grep",
        "--model",
        "k3-256k",
        "--effort",
        "high",
        "--no-session-persistence",
    ]
    assert kimi_client.env == {
        "ANTHROPIC_BASE_URL": "https://api.kimi.com/coding/",
        "ANTHROPIC_MODEL": "k3-256k",
        "ANTHROPIC_DEFAULT_FABLE_MODEL": "k3-256k",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "k3-256k",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "k3-256k",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "k3-256k",
        "CLAUDE_CODE_SUBAGENT_MODEL": "k3-256k",
        "CLAUDE_CODE_EFFORT_LEVEL": "high",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "262144",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "262144",
    }
    assert isinstance(create_agent(kimi_client), KimiClaudeAgent)


@pytest.mark.asyncio
async def test_kimi_requires_explicit_working_directory():
    tool = CLinkTool()

    with pytest.raises(ToolExecutionError, match="requires 'working_directory_absolute_path'"):
        await tool.execute({"prompt": "Review this repository", "cli_name": "kimi", "role": "codereviewer"})


@pytest.mark.asyncio
async def test_clink_tool_defaults_to_first_cli(monkeypatch):
    tool = CLinkTool()

    async def fake_run(**kwargs):
        return AgentOutput(
            parsed=ParsedCLIResponse(content="Default CLI response", metadata={"events": ["foo"]}),
            sanitized_command=["gemini"],
            returncode=0,
            stdout='{"response": "Default CLI response"}',
            stderr="",
            duration_seconds=0.1,
            parser_name="gemini_json",
            output_file_content=None,
        )

    class DummyAgent:
        injects_system_prompt_externally = False
        requires_explicit_working_dir = False

        async def run(self, **kwargs):
            return await fake_run(**kwargs)

    monkeypatch.setattr("tools.clink.create_agent", lambda client: DummyAgent())

    arguments = {
        "prompt": "Hello",
        "absolute_file_paths": [],
        "images": [],
    }

    result = await tool.execute(arguments)
    payload = json.loads(result[0].text)
    metadata = payload.get("metadata", {})
    assert metadata.get("cli_name") == tool._default_cli_name
    assert metadata.get("events_removed_for_normal") is True


@pytest.mark.asyncio
async def test_clink_tool_truncates_large_output(monkeypatch):
    tool = CLinkTool()

    summary_section = "<SUMMARY>This is the condensed summary.</SUMMARY>"
    long_text = "A" * (MAX_RESPONSE_CHARS + 500) + summary_section

    async def fake_run(**kwargs):
        return AgentOutput(
            parsed=ParsedCLIResponse(content=long_text, metadata={"events": ["event1", "event2"]}),
            sanitized_command=["codex"],
            returncode=0,
            stdout="{}",
            stderr="",
            duration_seconds=0.2,
            parser_name="codex_jsonl",
            output_file_content=None,
        )

    class DummyAgent:
        injects_system_prompt_externally = False
        requires_explicit_working_dir = False

        async def run(self, **kwargs):
            return await fake_run(**kwargs)

    monkeypatch.setattr("tools.clink.create_agent", lambda client: DummyAgent())

    arguments = {
        "prompt": "Summarize",
        "cli_name": tool._default_cli_name,
        "absolute_file_paths": [],
        "images": [],
    }

    result = await tool.execute(arguments)
    payload = json.loads(result[0].text)
    assert payload["status"] in {"success", "continuation_available"}
    assert payload["content"].strip() == "This is the condensed summary."
    metadata = payload.get("metadata", {})
    assert metadata.get("output_summarized") is True
    assert metadata.get("events_removed_for_normal") is True
    assert metadata.get("output_original_length") == len(long_text)


@pytest.mark.asyncio
async def test_clink_tool_truncates_without_summary(monkeypatch):
    tool = CLinkTool()

    long_text = "B" * (MAX_RESPONSE_CHARS + 1000)

    async def fake_run(**kwargs):
        return AgentOutput(
            parsed=ParsedCLIResponse(content=long_text, metadata={"events": ["event"]}),
            sanitized_command=["codex"],
            returncode=0,
            stdout="{}",
            stderr="",
            duration_seconds=0.2,
            parser_name="codex_jsonl",
            output_file_content=None,
        )

    class DummyAgent:
        injects_system_prompt_externally = False
        requires_explicit_working_dir = False

        async def run(self, **kwargs):
            return await fake_run(**kwargs)

    monkeypatch.setattr("tools.clink.create_agent", lambda client: DummyAgent())

    arguments = {
        "prompt": "Summarize",
        "cli_name": tool._default_cli_name,
        "absolute_file_paths": [],
        "images": [],
    }

    result = await tool.execute(arguments)
    payload = json.loads(result[0].text)
    assert payload["status"] in {"success", "continuation_available"}
    assert "exceeding the configured clink limit" in payload["content"]
    metadata = payload.get("metadata", {})
    assert metadata.get("output_truncated") is True
    assert metadata.get("events_removed_for_normal") is True
    assert metadata.get("output_original_length") == len(long_text)
