"""Native Moonshot Kimi provider implementation."""

from __future__ import annotations

import copy
import logging
import math
from typing import TYPE_CHECKING, Any, ClassVar

from utils.env import get_env

from .openai_compatible import OpenAICompatibleProvider
from .registries.kimi import KimiModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ModelResponse, ProviderType

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

logger = logging.getLogger(__name__)


class KimiModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Direct integration for Kimi models exposed by Moonshot's API.

    Kimi K3 differs from generic OpenAI-compatible models in three important
    ways: sampling parameters are fixed, reasoning effort is a top-level Chat
    Completions field, and multi-turn requests must replay the complete prior
    assistant message (including ``reasoning_content`` and ``tool_calls``).
    """

    FRIENDLY_NAME = "Moonshot Kimi"
    REGISTRY_CLASS = KimiModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}
    PRIMARY_MODEL = "kimi-k3"
    _SUPPORTED_REASONING_EFFORTS = {"low", "high", "max"}
    _KIMI_CODE_KEY_PREFIX = "sk-kimi-"
    _KIMI_CODE_BASE_URL = "https://api.kimi.com/coding/v1"
    _OPEN_PLATFORM_BASE_URL = "https://api.moonshot.ai/v1"

    def __init__(self, api_key: str, **kwargs):
        """Initialize Kimi Code or Moonshot based on the key and overrides."""

        self._ensure_registry()
        base_url = get_env("KIMI_BASE_URL") or get_env("MOONSHOT_BASE_URL")
        if not base_url:
            base_url = (
                self._KIMI_CODE_BASE_URL
                if api_key.startswith(self._KIMI_CODE_KEY_PREFIX)
                else self._OPEN_PLATFORM_BASE_URL
            )
        kwargs.setdefault("base_url", base_url)
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def _api_model_name(self, resolved_model: str) -> str:
        """Translate PAL's display-oriented K3 name to Kimi Code's API ID."""

        if resolved_model == self.PRIMARY_MODEL and "api.kimi.com/coding" in self.base_url.rstrip("/"):
            return "k3"
        return resolved_model

    def get_provider_type(self) -> ProviderType:
        """Return the native Kimi provider type."""

        return ProviderType.KIMI

    def get_preferred_model(self, category: ToolModelCategory, allowed_models: list[str]) -> str | None:
        """Prefer Kimi K3 whenever it is allowed."""

        if not allowed_models:
            return None
        if self.PRIMARY_MODEL in allowed_models:
            return self.PRIMARY_MODEL
        return allowed_models[0]

    @classmethod
    def _map_reasoning_effort(cls, thinking_mode: str | None, capabilities: ModelCapabilities) -> str:
        """Map PAL's five thinking levels to K3's low/high/max contract."""

        normalized = (thinking_mode or capabilities.default_reasoning_effort or "high").lower()
        if normalized in {"minimal", "low"}:
            return "low"
        if normalized in {"medium", "high"}:
            return "high"
        if normalized == "max":
            return "max"

        logger.warning("Unsupported Kimi reasoning effort '%s'; using high", normalized)
        return "high"

    @staticmethod
    def _serialize_assistant_message(message: Any) -> dict[str, Any]:
        """Serialize the complete Kimi assistant message for exact replay."""

        if hasattr(message, "model_dump"):
            serialized = message.model_dump(exclude_none=True)
        elif isinstance(message, dict):
            serialized = copy.deepcopy(message)
        else:
            serialized = {"role": "assistant", "content": getattr(message, "content", None)}

        serialized["role"] = "assistant"

        # Older OpenAI SDK releases may not include vendor extension fields in
        # model_dump(), so copy them explicitly when the response exposes them.
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content is not None:
            serialized["reasoning_content"] = reasoning_content

        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls is not None and "tool_calls" not in serialized:
            serialized["tool_calls"] = [
                call.model_dump(exclude_none=True) if hasattr(call, "model_dump") else copy.deepcopy(call)
                for call in tool_calls
            ]

        return serialized

    def _build_user_message(
        self,
        prompt: str,
        images: list[str] | None,
        capabilities: ModelCapabilities,
    ) -> dict[str, Any]:
        """Build a Kimi user message, embedding local images as data URLs."""

        user_content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if images and capabilities.supports_images:
            for image_path in images:
                image_content = self._process_image(image_path)
                if image_content:
                    user_content.append(image_content)
        elif images:
            logger.warning(
                "Model %s does not support images; ignoring %d image(s)", capabilities.model_name, len(images)
            )

        if len(user_content) == 1:
            return {"role": "user", "content": prompt}
        return {"role": "user", "content": user_content}

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_output_tokens: int | None = None,
        images: list[str] | None = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate a Kimi completion with native reasoning and continuation semantics."""

        if not self.validate_model_name(model_name):
            raise ValueError(f"Model '{model_name}' is not available from the Kimi provider")

        capabilities = self.get_capabilities(model_name)
        resolved_model = self._resolve_model_name(model_name)
        api_model = self._api_model_name(resolved_model)
        prior_messages = kwargs.pop("conversation_messages", None)
        thinking_mode = kwargs.pop("thinking_mode", None)

        messages: list[dict[str, Any]] = copy.deepcopy(prior_messages) if prior_messages else []
        request_messages: list[dict[str, Any]] = []

        if system_prompt:
            system_message = {"role": "system", "content": system_prompt}
            messages.append(system_message)
            request_messages.append(system_message)

        user_message = self._build_user_message(prompt, images, capabilities)
        messages.append(user_message)
        request_messages.append(user_message)

        extra_body: dict[str, Any] = {
            "reasoning_effort": self._map_reasoning_effort(thinking_mode, capabilities),
        }
        if max_output_tokens is not None:
            if max_output_tokens <= 0:
                raise ValueError("max_output_tokens must be greater than zero")
            extra_body["max_completion_tokens"] = min(max_output_tokens, capabilities.max_output_tokens)

        # K3 fixes temperature/top_p/penalty values server-side. Deliberately
        # omit all sampling parameters instead of forwarding PAL defaults.
        completion_params = {
            "model": api_model,
            "messages": messages,
            "stream": False,
            "extra_body": extra_body,
        }

        attempt_counter = {"value": 0}

        def _attempt() -> ModelResponse:
            attempt_counter["value"] += 1
            response = self.client.chat.completions.create(**completion_params)
            choice = response.choices[0]
            assistant_message = self._serialize_assistant_message(choice.message)
            content = assistant_message.get("content") or ""

            return ModelResponse(
                content=content,
                usage=self._extract_usage(response),
                model_name=resolved_model,
                friendly_name=self.FRIENDLY_NAME,
                provider=self.get_provider_type(),
                metadata={
                    "finish_reason": choice.finish_reason,
                    "model": getattr(response, "model", resolved_model),
                    "id": getattr(response, "id", ""),
                    "created": getattr(response, "created", 0),
                    "reasoning_effort": extra_body["reasoning_effort"],
                },
                provider_state={
                    "provider": ProviderType.KIMI.value,
                    "model": resolved_model,
                    "reset": not bool(prior_messages),
                    "request_messages": request_messages,
                    "assistant_message": assistant_message,
                },
            )

        try:
            return self._run_with_retries(
                operation=_attempt,
                max_attempts=4,
                delays=[1, 3, 5],
                log_prefix=f"Kimi API ({resolved_model})",
            )
        except Exception as exc:
            attempts = max(attempt_counter["value"], 1)
            raise RuntimeError(
                f"Kimi API error for model {resolved_model} after {attempts} "
                f"attempt{'s' if attempts > 1 else ''}: {exc}"
            ) from exc

    def build_continuation_messages(self, context: Any, model_name: str) -> list[dict[str, Any]] | None:
        """Rebuild the latest contiguous Kimi message segment exactly."""

        resolved_model = self._resolve_model_name(model_name)
        assistant_turns = [turn for turn in context.turns if turn.role == "assistant"]
        if not assistant_turns:
            return None

        states: list[dict[str, Any]] = []
        for turn in reversed(assistant_turns):
            metadata = turn.model_metadata or {}
            state = metadata.get("provider_state") if isinstance(metadata, dict) else None
            if not isinstance(state, dict):
                break
            if state.get("provider") != ProviderType.KIMI.value or state.get("model") != resolved_model:
                break

            states.append(state)
            if state.get("reset"):
                break

        if not states or not states[-1].get("reset"):
            return None

        messages: list[dict[str, Any]] = []
        for state in reversed(states):
            request_messages = state.get("request_messages")
            assistant_message = state.get("assistant_message")
            if not isinstance(request_messages, list) or not isinstance(assistant_message, dict):
                return None
            messages.extend(copy.deepcopy(request_messages))
            messages.append(copy.deepcopy(assistant_message))

        return messages

    def count_tokens(self, text: str, model_name: str) -> int:
        """Conservatively estimate Kimi tokens without a network round trip."""

        if not text:
            return 0
        return max(1, math.ceil(len(text) / 3))


KimiModelProvider._ensure_registry()
