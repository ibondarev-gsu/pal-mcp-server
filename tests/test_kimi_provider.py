"""Tests for the native Moonshot Kimi provider."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from providers.kimi import KimiModelProvider
from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from utils.conversation_memory import ConversationTurn, ThreadContext


def _response(message, *, finish_reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8, total_tokens=20),
        model="kimi-k3",
        id="chatcmpl-test",
        created=1,
    )


def _turn(state, *, model="kimi-k3"):
    return ConversationTurn(
        role="assistant",
        content=state["assistant_message"].get("content") or "",
        timestamp="2026-09-05T00:00:00+00:00",
        model_provider="kimi",
        model_name=model,
        model_metadata={"provider_state": state},
    )


def _context(*turns):
    return ThreadContext(
        thread_id="thread-1",
        created_at="2026-09-05T00:00:00+00:00",
        last_updated_at="2026-09-05T00:00:00+00:00",
        tool_name="chat",
        turns=list(turns),
        initial_context={},
    )


class TestKimiProvider:
    def setup_method(self):
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def test_initialization_and_capabilities(self):
        provider = KimiModelProvider("test-key")

        assert provider.base_url == "https://api.moonshot.ai/v1"
        assert provider.get_provider_type() == ProviderType.KIMI
        assert provider._resolve_model_name("kimi") == "kimi-k3"
        assert provider._resolve_model_name("k3") == "kimi-k3"

        capabilities = provider.get_capabilities("kimi-k3")
        assert capabilities.context_window == 1_048_576
        assert capabilities.max_output_tokens == 1_048_576
        assert capabilities.supports_extended_thinking is True
        assert capabilities.supports_temperature is False
        assert capabilities.default_reasoning_effort == "max"

    @patch.dict("os.environ", {"KIMI_BASE_URL": "https://example.test/v1"})
    def test_custom_base_url(self):
        assert KimiModelProvider("test-key").base_url == "https://example.test/v1"

    @patch.dict("os.environ", {"KIMI_BASE_URL": "https://api.moonshot.ai/v1"})
    def test_explicit_base_url_overrides_kimi_code_key_detection(self):
        provider = KimiModelProvider("sk-kimi-test-key")

        assert provider.base_url == "https://api.moonshot.ai/v1"
        assert provider._api_model_name("kimi-k3") == "kimi-k3"

    def test_kimi_code_key_selects_subscription_endpoint(self):
        provider = KimiModelProvider("sk-kimi-test-key")

        assert provider.base_url == "https://api.kimi.com/coding/v1"
        assert provider._api_model_name("kimi-k3") == "k3"

    def test_open_platform_key_keeps_international_endpoint_and_model_id(self):
        provider = KimiModelProvider("sk-open-platform-test-key")

        assert provider.base_url == "https://api.moonshot.ai/v1"
        assert provider._api_model_name("kimi-k3") == "kimi-k3"

    @pytest.mark.parametrize(
        ("thinking_mode", "expected"),
        [
            (None, "max"),
            ("minimal", "low"),
            ("low", "low"),
            ("medium", "high"),
            ("high", "high"),
            ("max", "max"),
        ],
    )
    def test_reasoning_effort_mapping_and_fixed_sampling(self, thinking_mode, expected):
        provider = KimiModelProvider("sk-kimi-test-key")
        provider._client = MagicMock()
        message = SimpleNamespace(content="done", reasoning_content="private reasoning", tool_calls=None)
        provider._client.chat.completions.create.return_value = _response(message)

        result = provider.generate_content(
            prompt="review this",
            model_name="kimi",
            system_prompt="be critical",
            temperature=0.9,
            max_output_tokens=4096,
            thinking_mode=thinking_mode,
            top_p=0.4,
            frequency_penalty=0.5,
        )

        params = provider._client.chat.completions.create.call_args.kwargs
        assert params["model"] == "k3"
        assert params["extra_body"] == {
            "reasoning_effort": expected,
            "max_completion_tokens": 4096,
        }
        for unsupported in ("temperature", "top_p", "frequency_penalty", "presence_penalty", "n"):
            assert unsupported not in params

        assert result.content == "done"
        assert result.provider_state["assistant_message"]["reasoning_content"] == "private reasoning"
        assert result.provider_state["reset"] is True

    def test_complete_assistant_message_is_preserved(self):
        provider = KimiModelProvider("test-key")
        provider._client = MagicMock()
        tool_call = SimpleNamespace(
            model_dump=lambda **_: {
                "id": "call-1",
                "type": "function",
                "function": {"name": "lookup", "arguments": "{}"},
            }
        )
        message = SimpleNamespace(content=None, reasoning_content="reasoning", tool_calls=[tool_call])
        provider._client.chat.completions.create.return_value = _response(message, finish_reason="tool_calls")

        result = provider.generate_content(prompt="use a tool", model_name="kimi-k3")

        assistant = result.provider_state["assistant_message"]
        assert assistant == {
            "role": "assistant",
            "content": None,
            "reasoning_content": "reasoning",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "lookup", "arguments": "{}"},
                }
            ],
        }

    def test_generate_content_appends_to_native_continuation(self):
        provider = KimiModelProvider("test-key")
        provider._client = MagicMock()
        provider._client.chat.completions.create.return_value = _response(
            SimpleNamespace(content="answer two", reasoning_content="reasoning two", tool_calls=None)
        )
        prior_messages = [
            {"role": "user", "content": "question one"},
            {
                "role": "assistant",
                "content": "answer one",
                "reasoning_content": "reasoning one",
            },
        ]

        result = provider.generate_content(
            prompt="question two",
            model_name="kimi-k3",
            conversation_messages=prior_messages,
        )

        params = provider._client.chat.completions.create.call_args.kwargs
        assert params["messages"] == [
            *prior_messages,
            {"role": "user", "content": "question two"},
        ]
        assert result.provider_state["reset"] is False
        assert result.provider_state["request_messages"] == [{"role": "user", "content": "question two"}]

        params["messages"][0]["content"] = "changed"
        assert prior_messages[0]["content"] == "question one"

    def test_continuation_replays_native_messages_exactly(self):
        provider = KimiModelProvider("test-key")
        first_state = {
            "provider": "kimi",
            "model": "kimi-k3",
            "reset": True,
            "request_messages": [
                {"role": "system", "content": "system one"},
                {"role": "user", "content": "question one"},
            ],
            "assistant_message": {
                "role": "assistant",
                "content": "answer one",
                "reasoning_content": "reasoning one",
            },
        }
        second_state = {
            "provider": "kimi",
            "model": "kimi-k3",
            "reset": False,
            "request_messages": [{"role": "user", "content": "question two"}],
            "assistant_message": {
                "role": "assistant",
                "content": "answer two",
                "reasoning_content": "reasoning two",
            },
        }

        messages = provider.build_continuation_messages(_context(_turn(first_state), _turn(second_state)), "kimi")

        assert messages == [
            {"role": "system", "content": "system one"},
            {"role": "user", "content": "question one"},
            first_state["assistant_message"],
            {"role": "user", "content": "question two"},
            second_state["assistant_message"],
        ]

        # The returned structure must be safe for callers to mutate.
        messages[2]["reasoning_content"] = "changed"
        assert first_state["assistant_message"]["reasoning_content"] == "reasoning one"

    def test_continuation_falls_back_after_incompatible_turn(self):
        provider = KimiModelProvider("test-key")
        state = {
            "provider": "openai",
            "model": "gpt-5.2",
            "reset": True,
            "request_messages": [{"role": "user", "content": "question"}],
            "assistant_message": {"role": "assistant", "content": "answer"},
        }

        assert provider.build_continuation_messages(_context(_turn(state, model="gpt-5.2")), "kimi-k3") is None

    def test_continuation_falls_back_for_partial_native_state(self):
        provider = KimiModelProvider("test-key")
        state = {
            "provider": "kimi",
            "model": "kimi-k3",
            "reset": True,
            "request_messages": "not-a-message-list",
            "assistant_message": {"role": "assistant", "content": "answer"},
        }

        assert provider.build_continuation_messages(_context(_turn(state)), "kimi-k3") is None

    @patch.dict(
        "os.environ",
        {"KIMI_API_KEY": "your_kimi_api_key_here", "MOONSHOT_API_KEY": "moonshot-real-key"},
        clear=False,
    )
    def test_registry_uses_moonshot_key_when_kimi_value_is_placeholder(self):
        assert ModelProviderRegistry._get_api_key_for_provider(ProviderType.KIMI) == "moonshot-real-key"

    @patch.dict("os.environ", {"KIMI_API_KEY": "kimi-test-key"}, clear=True)
    def test_configure_providers_with_kimi_only(self):
        from server import configure_providers

        registry = ModelProviderRegistry()
        original_providers = registry._providers.copy()
        original_instances = registry._initialized_providers.copy()
        try:
            registry._providers.clear()
            registry._initialized_providers.clear()

            configure_providers()

            provider = ModelProviderRegistry.get_provider(ProviderType.KIMI)
            assert isinstance(provider, KimiModelProvider)
            assert ModelProviderRegistry.get_provider_for_model("k3") is provider
        finally:
            registry._providers.clear()
            registry._providers.update(original_providers)
            registry._initialized_providers.clear()
            registry._initialized_providers.update(original_instances)

    @pytest.mark.asyncio
    async def test_server_uses_native_history_only_for_supported_execution_path(self):
        from server import reconstruct_thread_context

        provider = KimiModelProvider("test-key")
        state = {
            "provider": "kimi",
            "model": "kimi-k3",
            "reset": True,
            "request_messages": [{"role": "user", "content": "question one"}],
            "assistant_message": {
                "role": "assistant",
                "content": "answer one",
                "reasoning_content": "reasoning one",
            },
        }
        context = _context(_turn(state))
        arguments = {
            "continuation_id": "thread-1",
            "prompt": "question two",
            "model": "kimi-k3",
        }

        with (
            patch("utils.conversation_memory.get_thread", return_value=context),
            patch("utils.conversation_memory.add_turn", return_value=True),
            patch.object(ModelProviderRegistry, "get_provider_for_model", return_value=provider),
        ):
            chat_arguments = await reconstruct_thread_context(arguments.copy(), current_tool_name="chat")
            workflow_arguments = await reconstruct_thread_context(arguments.copy(), current_tool_name="codereview")

        assert chat_arguments["_provider_conversation_messages"] == [
            {"role": "user", "content": "question one"},
            state["assistant_message"],
        ]
        assert "=== CONVERSATION HISTORY" not in chat_arguments["prompt"]

        assert "_provider_conversation_messages" not in workflow_arguments
        assert "=== CONVERSATION HISTORY" in workflow_arguments["prompt"]
        assert "answer one" in workflow_arguments["prompt"]
