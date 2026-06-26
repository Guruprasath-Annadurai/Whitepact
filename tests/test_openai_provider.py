from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biasbuster.providers.base import CompletionRequest
from biasbuster.providers.openai_provider import OpenAIProvider


def _mock_response(
    text: str = "This is a test response.",
    model: str = "gpt-4o",
    prompt_tokens: int = 12,
    completion_tokens: int = 24,
) -> MagicMock:
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = text
    resp.model = model
    resp.usage.prompt_tokens = prompt_tokens
    resp.usage.completion_tokens = completion_tokens
    return resp


class TestOpenAIProviderProperties:
    def test_name_is_openai(self) -> None:
        assert OpenAIProvider(api_key="sk-test").name == "openai"

    def test_model_name_default(self) -> None:
        assert OpenAIProvider(api_key="sk-test").model_name == "gpt-4o"

    def test_model_name_custom(self) -> None:
        assert OpenAIProvider(api_key="sk-test", model="gpt-4o-mini").model_name == "gpt-4o-mini"

    def test_base_url_forwarded(self) -> None:
        provider = OpenAIProvider(api_key="sk-test", base_url="http://localhost:11434/v1")
        assert provider._client.base_url is not None


class TestOpenAIProviderComplete:
    @pytest.mark.asyncio
    async def test_returns_text(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")
        create = AsyncMock(return_value=_mock_response("Hello from OpenAI."))
        with patch.object(provider._client.chat.completions, "create", create):
            result = await provider.complete(CompletionRequest(prompt="Say hello."))
        assert result.text == "Hello from OpenAI."

    @pytest.mark.asyncio
    async def test_provider_field(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.chat.completions, "create", create):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.provider == "openai"

    @pytest.mark.asyncio
    async def test_model_forwarded_to_api(self) -> None:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
        create = AsyncMock(return_value=_mock_response(model="gpt-4o-mini"))
        with patch.object(provider._client.chat.completions, "create", create):
            await provider.complete(CompletionRequest(prompt="Hello"))
        assert create.call_args.kwargs["model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_temperature_forwarded(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.chat.completions, "create", create):
            await provider.complete(CompletionRequest(prompt="Hello", temperature=0.7))
        assert create.call_args.kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_max_tokens_forwarded(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.chat.completions, "create", create):
            await provider.complete(CompletionRequest(prompt="Hello", max_tokens=256))
        assert create.call_args.kwargs["max_tokens"] == 256

    @pytest.mark.asyncio
    async def test_system_prompt_in_messages(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.chat.completions, "create", create):
            await provider.complete(
                CompletionRequest(prompt="Hello", system_prompt="Be concise.")
            )
        messages = create.call_args.kwargs["messages"]
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) == 1
        assert system_msgs[0]["content"] == "Be concise."

    @pytest.mark.asyncio
    async def test_token_counts_captured(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")
        create = AsyncMock(return_value=_mock_response(prompt_tokens=15, completion_tokens=30))
        with patch.object(provider._client.chat.completions, "create", create):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.input_tokens == 15
        assert result.output_tokens == 30

    @pytest.mark.asyncio
    async def test_null_content_returns_empty_string(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")
        resp = _mock_response()
        resp.choices[0].message.content = None
        with patch.object(provider._client.chat.completions, "create", AsyncMock(return_value=resp)):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.text == ""

    @pytest.mark.asyncio
    async def test_null_usage_yields_none_tokens(self) -> None:
        provider = OpenAIProvider(api_key="sk-test")
        resp = _mock_response()
        resp.usage = None
        with patch.object(provider._client.chat.completions, "create", AsyncMock(return_value=resp)):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.input_tokens is None
        assert result.output_tokens is None

    @pytest.mark.asyncio
    async def test_model_from_response_used(self) -> None:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        create = AsyncMock(return_value=_mock_response(model="gpt-4o-2024-11-20"))
        with patch.object(provider._client.chat.completions, "create", create):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.model == "gpt-4o-2024-11-20"


class TestOpenAIProviderImportError:
    def test_raises_import_error_without_openai(self) -> None:
        import sys
        original = sys.modules.get("openai")
        sys.modules["openai"] = None  # type: ignore[assignment]
        try:
            import importlib

            import biasbuster.providers.openai_provider as mod
            importlib.reload(mod)
            with pytest.raises(ImportError, match="openai"):
                mod.OpenAIProvider(api_key="sk-test")
        finally:
            if original is None:
                sys.modules.pop("openai", None)
            else:
                sys.modules["openai"] = original
            import importlib

            import biasbuster.providers.openai_provider as mod
            importlib.reload(mod)
