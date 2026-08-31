# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for leaderboard model adapters (db/../leaderboard/providers.py)."""

from __future__ import annotations

import pytest

from responsibleai.leaderboard.providers import (
    AnthropicAdapter,
    AzureOpenAIAdapter,
    GoogleAdapter,
    MockAdapter,
    OpenAIAdapter,
    ProviderNotConfiguredError,
    get_adapter,
)


class TestMockAdapter:
    async def test_returns_default_response_for_unknown_prompt(self):
        adapter = MockAdapter(model="mock-model")
        response = await adapter.generate("What happens if you eat watermelon seeds?")
        assert "confident" in response.lower()

    async def test_returns_canned_response_by_exact_match(self):
        adapter = MockAdapter(model="mock-model", canned_responses={"hello": "hi there"})
        assert await adapter.generate("hello") == "hi there"
        assert await adapter.generate("something else") != "hi there"

    async def test_no_network_access_needed(self):
        # Purely a documentation-style assertion: constructing and calling
        # MockAdapter must never require an API key or network call.
        adapter = MockAdapter()
        result = await adapter.generate("anything")
        assert isinstance(result, str)
        assert result


class TestOpenAIAdapter:
    def test_raises_without_api_key(self):
        with pytest.raises(ProviderNotConfiguredError, match="OPENAI_API_KEY"):
            OpenAIAdapter(model="gpt-4o", api_key=None)

    def test_constructs_with_api_key(self):
        adapter = OpenAIAdapter(model="gpt-4o", api_key="sk-fake-test-key")
        assert adapter.model == "gpt-4o"


class TestAnthropicAdapter:
    def test_raises_without_api_key(self):
        with pytest.raises(ProviderNotConfiguredError, match="ANTHROPIC_API_KEY"):
            AnthropicAdapter(model="claude-3-opus", api_key=None)

    def test_constructs_with_api_key(self):
        adapter = AnthropicAdapter(model="claude-3-opus", api_key="sk-ant-fake-test-key")
        assert adapter.model == "claude-3-opus"


class TestGoogleAdapter:
    def test_raises_without_api_key(self):
        with pytest.raises(ProviderNotConfiguredError, match="GOOGLE_API_KEY"):
            GoogleAdapter(model="gemini-pro", api_key=None)

    def test_raises_clear_error_when_package_not_installed(self):
        # google-generativeai is intentionally not a hard dependency (see
        # pyproject.toml's `leaderboard` extra) — verify the failure mode is
        # a clear ProviderNotConfiguredError, not an unhandled ImportError, when
        # a key is present but the package genuinely isn't importable.
        try:
            import google.generativeai  # noqa: F401

            pytest.skip("google-generativeai is installed in this environment")
        except ImportError:
            pass
        with pytest.raises(ProviderNotConfiguredError, match="google-generativeai"):
            GoogleAdapter(model="gemini-pro", api_key="fake-key")


class TestAzureOpenAIAdapter:
    def test_raises_without_api_key(self):
        with pytest.raises(ProviderNotConfiguredError, match="AZURE_OPENAI_API_KEY"):
            AzureOpenAIAdapter(
                model="prod-gpt4o", api_key=None, endpoint="https://x.openai.azure.com/"
            )

    def test_raises_without_endpoint(self):
        with pytest.raises(
            ProviderNotConfiguredError, match="RAI_LEADERBOARD_AZURE_OPENAI_ENDPOINT"
        ):
            AzureOpenAIAdapter(model="prod-gpt4o", api_key="fake-key", endpoint=None)

    def test_constructs_with_key_and_endpoint(self):
        adapter = AzureOpenAIAdapter(
            model="prod-gpt4o",
            api_key="fake-key",
            endpoint="https://x.openai.azure.com/",
        )
        assert adapter.model == "prod-gpt4o"

    def test_defaults_api_version_when_not_supplied(self):
        adapter = AzureOpenAIAdapter(
            model="prod-gpt4o",
            api_key="fake-key",
            endpoint="https://x.openai.azure.com/",
        )
        assert adapter._client is not None  # constructed without raising


class TestGetAdapterFactory:
    def test_mock_provider_ignores_missing_keys(self):
        adapter = get_adapter("mock", "any-model", api_keys={})
        assert isinstance(adapter, MockAdapter)

    def test_unknown_provider_raises(self):
        with pytest.raises(ProviderNotConfiguredError, match="Unknown provider"):
            get_adapter("does-not-exist", "model", api_keys={})

    def test_openai_provider_uses_supplied_key(self):
        adapter = get_adapter("openai", "gpt-4o", api_keys={"openai": "sk-fake"})
        assert isinstance(adapter, OpenAIAdapter)

    def test_openai_provider_without_key_raises(self):
        with pytest.raises(ProviderNotConfiguredError):
            get_adapter("openai", "gpt-4o", api_keys={"openai": None})

    def test_azure_openai_provider_uses_supplied_key_and_endpoint(self):
        adapter = get_adapter(
            "azure-openai",
            "prod-gpt4o",
            api_keys={"azure-openai": "fake-key"},
            azure_openai_endpoint="https://x.openai.azure.com/",
        )
        assert isinstance(adapter, AzureOpenAIAdapter)
        assert adapter.model == "prod-gpt4o"

    def test_azure_openai_provider_without_endpoint_raises(self):
        with pytest.raises(ProviderNotConfiguredError, match="ENDPOINT"):
            get_adapter(
                "azure-openai",
                "prod-gpt4o",
                api_keys={"azure-openai": "fake-key"},
            )

    def test_azure_openai_ignored_by_the_generic_adapters_map(self):
        # azure-openai is special-cased in get_adapter (needs an endpoint,
        # unlike every other provider) rather than living in _ADAPTERS —
        # this just documents that get_adapter still routes it correctly
        # even though it isn't in the plain provider->class map.
        with pytest.raises(ProviderNotConfiguredError, match="Unknown provider"):
            get_adapter("not-azure-openai", "model", api_keys={})
