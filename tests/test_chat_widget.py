"""Tests for the MCP Apps widget attached to PAL chat."""

import json

import pytest
from mcp.types import CallToolResult, TextContent

import server
from server import handle_list_resources, handle_list_tools, handle_read_resource
from tools.chat_widget import (
    CHAT_WIDGET_MIME_TYPE,
    CHAT_WIDGET_URI,
    build_chat_call_result,
)


def test_chat_call_result_preserves_fallback_and_adds_widget_data():
    payload = {
        "status": "continuation_available",
        "content": "Kimi found a race condition.\n\n---\n\nAGENT'S TURN: internal guidance",
        "content_type": "text",
        "metadata": {"provider_used": "kimi", "model_used": "kimi-k3"},
        "continuation_offer": {
            "continuation_id": "review-123",
            "remaining_turns": 9,
            "note": "Continue if useful.",
        },
    }
    original = TextContent(type="text", text=json.dumps(payload))

    result = build_chat_call_result([original])

    assert result.content == [original]
    assert result.structuredContent == {
        "status": "continuation_available",
        "answer": "Kimi found a race condition.",
        "contentType": "text",
        "provider": "kimi",
        "model": "kimi-k3",
        "continuationId": "review-123",
        "remainingTurns": 9,
    }


def test_chat_call_result_falls_back_when_payload_is_not_pal_json():
    original = TextContent(type="text", text="plain response")

    result = build_chat_call_result([original])

    assert result.content == [original]
    assert result.structuredContent is None


def test_chat_call_result_handles_non_string_content():
    payload = {
        "status": "success",
        "content": {"finding": "race condition"},
    }
    original = TextContent(type="text", text=json.dumps(payload))

    result = build_chat_call_result([original])

    assert result.content == [original]
    assert result.structuredContent["answer"] == "{'finding': 'race condition'}"


def test_external_model_widget_uses_cli_name_for_clink_provider():
    payload = {
        "status": "success",
        "content": "Repository review complete.",
        "metadata": {"cli_name": "kimi", "model_used": "kimi-for-coding"},
    }
    original = TextContent(type="text", text=json.dumps(payload))

    result = build_chat_call_result([original])

    assert result.structuredContent["provider"] == "kimi"
    assert result.structuredContent["model"] == "kimi-for-coding"


@pytest.mark.asyncio
async def test_chat_tool_advertises_mcp_apps_widget():
    tools = await handle_list_tools()

    chat = next(tool for tool in tools if tool.name == "chat")
    assert chat.meta["ui"]["resourceUri"] == CHAT_WIDGET_URI
    assert chat.meta["openai/outputTemplate"] == CHAT_WIDGET_URI

    clink = next(tool for tool in tools if tool.name == "clink")
    assert clink.meta["ui"]["resourceUri"] == CHAT_WIDGET_URI
    assert clink.annotations.readOnlyHint is False

    non_chat = next(tool for tool in tools if tool.name == "analyze")
    assert non_chat.meta is None


@pytest.mark.asyncio
async def test_clink_server_dispatch_adds_widget_structured_content(monkeypatch):
    payload = {
        "status": "success",
        "content": "Repository review complete.",
        "content_type": "text",
        "metadata": {"cli_name": "kimi", "model_used": "kimi-for-coding"},
    }

    async def fake_execute(_arguments):
        return [TextContent(type="text", text=json.dumps(payload))]

    monkeypatch.setattr(server.TOOLS["clink"], "execute", fake_execute)

    result = await server.handle_call_tool("clink", {"prompt": "Review this repository"})

    assert isinstance(result, CallToolResult)
    assert result.structuredContent["provider"] == "kimi"
    assert result.structuredContent["answer"] == "Repository review complete."


@pytest.mark.asyncio
async def test_chat_widget_resource_is_discoverable_and_self_contained():
    resources = await handle_list_resources()
    assert len(resources) == 1
    assert str(resources[0].uri) == CHAT_WIDGET_URI
    assert resources[0].mimeType == CHAT_WIDGET_MIME_TYPE

    contents = await handle_read_resource(CHAT_WIDGET_URI)
    assert len(contents) == 1
    assert contents[0].mime_type == CHAT_WIDGET_MIME_TYPE
    assert "ui/notifications/tool-input" in contents[0].content
    assert "ui/notifications/tool-result" in contents[0].content
    assert "structuredContent" in contents[0].content
    assert "<script src=" not in contents[0].content


@pytest.mark.asyncio
async def test_unknown_widget_resource_is_rejected():
    with pytest.raises(ValueError, match="Unknown resource"):
        await handle_read_resource("ui://pal/unknown.html")
