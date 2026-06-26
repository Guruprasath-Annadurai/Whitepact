from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from biasbuster.providers.anthropic_provider import AnthropicProvider
from biasbuster.providers.base import CompletionRequest


def _mock_response(
    text: str = "This is a test response from Claude.",
    model: str = "claude-3-5-sonnet-20241022",
    input_tokens: int = 12,
    output_tokens: int = 24,
) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.model = model
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    return resp


class TestAnthropicProviderProperties:
    def test_name_is_anthropic(self) -> None:
        assert AnthropicProvider(api_key="sk-ant-test").name == "anthropic"

    def test_model_name_default(self) -> None:
        assert AnthropicProvider(api_key="sk-ant-test").model_name == "claude-3-5-sonnet-20241022"

    def test_model_name_custom(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-haiku-20240307")
        assert provider.model_name == "claude-3-haiku-20240307"


class TestAnthropicProviderComplete:
    @pytest.mark.asyncio
    async def test_returns_text(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        create = AsyncMock(return_value=_mock_response("Hello from Claude."))
        with patch.object(provider._client.messages, "create", create):
            result = await provider.complete(CompletionRequest(prompt="Say hello."))
        assert result.text == "Hello from Claude."

    @pytest.mark.asyncio
    async def test_provider_field(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.messages, "create", create):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_model_forwarded_to_api(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test", model="claude-3-haiku-20240307")
        create = AsyncMock(return_value=_mock_response(model="claude-3-haiku-20240307"))
        with patch.object(provider._client.messages, "create", create):
            await provider.complete(CompletionRequest(prompt="Hello"))
        assert create.call_args.kwargs["model"] == "claude-3-haiku-20240307"

    @pytest.mark.asyncio
    async def test_system_prompt_forwarded(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.messages, "create", create):
            await provider.complete(
                CompletionRequest(prompt="Hello", system_prompt="You are helpful.")
            )
        assert create.call_args.kwargs["system"] == "You are helpful."

    @pytest.mark.asyncio
    async def test_user_message_forwarded(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.messages, "create", create):
            await provider.complete(CompletionRequest(prompt="Test prompt content"))
        messages = create.call_args.kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Test prompt content"

    @pytest.mark.asyncio
    async def test_temperature_forwarded(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.messages, "create", create):
            await provider.complete(CompletionRequest(prompt="Hello", temperature=0.5))
        assert create.call_args.kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_max_tokens_forwarded(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        create = AsyncMock(return_value=_mock_response())
        with patch.object(provider._client.messages, "create", create):
            await provider.complete(CompletionRequest(prompt="Hello", max_tokens=256))
        assert create.call_args.kwargs["max_tokens"] == 256

    @pytest.mark.asyncio
    async def test_token_counts_captured(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        create = AsyncMock(return_value=_mock_response(input_tokens=18, output_tokens=42))
        with patch.object(provider._client.messages, "create", create):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.input_tokens == 18
        assert result.output_tokens == 42

    @pytest.mark.asyncio
    async def test_empty_content_returns_empty_string(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        resp = _mock_response()
        resp.content = []
        with patch.object(provider._client.messages, "create", AsyncMock(return_value=resp)):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.text == ""

    @pytest.mark.asyncio
    async def test_model_from_response_used(self) -> None:
        provider = AnthropicProvider(api_key="sk-ant-test")
        create = AsyncMock(return_value=_mock_response(model="claude-3-5-sonnet-20241022"))
        with patch.object(provider._client.messages, "create", create):
            result = await provider.complete(CompletionRequest(prompt="Hello"))
        assert result.model == "claude-3-5-sonnet-20241022"


class TestAnthropicProviderImportError:
    def test_raises_import_error_without_anthropic(self) -> None:
        import sys
        original = sys.modules.get("anthropic")
        sys.modules["anthropic"] = None  # type: ignore[assignment]
        try:
            import importlib

            import biasbuster.providers.anthropic_provider as mod
            importlib.reload(mod)
            with pytest.raises(ImportError, match="anthropic"):
                mod.AnthropicProvider(api_key="sk-ant-test")
        finally:
            if original is None:
                sys.modules.pop("anthropic", None)
            else:
                sys.modules["anthropic"] = original
            import importlib

            import biasbuster.providers.anthropic_provider as mod
            importlib.reload(mod)
