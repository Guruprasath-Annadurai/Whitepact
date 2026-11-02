from __future__ import annotations

import pytest

from biasbuster.providers.base import CompletionRequest
from tests.conftest import MockProvider


class TestBaseProviderBatch:
    @pytest.mark.asyncio
    async def test_complete_batch_returns_correct_count(self) -> None:
        provider = MockProvider()
        requests = [CompletionRequest(prompt=f"Prompt {i}") for i in range(5)]
        responses = await provider.complete_batch(requests)
        assert len(responses) == 5

    @pytest.mark.asyncio
    async def test_complete_batch_all_responses_have_text(self) -> None:
        provider = MockProvider()
        requests = [CompletionRequest(prompt="Hello") for _ in range(3)]
        responses = await provider.complete_batch(requests)
        for r in responses:
            assert isinstance(r.text, str)
            assert len(r.text) > 0

    @pytest.mark.asyncio
    async def test_complete_batch_respects_key_mapping(self) -> None:
        provider = MockProvider(responses={"special": "special response"})
        requests = [
            CompletionRequest(prompt="special prompt"),
            CompletionRequest(prompt="normal prompt"),
        ]
        responses = await provider.complete_batch(requests)
        assert responses[0].text == "special response"
        assert responses[1].text == provider._default

    @pytest.mark.asyncio
    async def test_mock_provider_call_count(self) -> None:
        provider = MockProvider()
        requests = [CompletionRequest(prompt=f"p{i}") for i in range(4)]
        await provider.complete_batch(requests)
        assert provider.call_count == 4

    @pytest.mark.asyncio
    async def test_provider_name_and_model(self) -> None:
        provider = MockProvider()
        assert provider.name == "mock"
        assert provider.model_name == "mock-1.0"

    @pytest.mark.asyncio
    async def test_completion_response_fields(self) -> None:
        provider = MockProvider(responses={"test": "a response"})
        response = await provider.complete(CompletionRequest(prompt="test query"))
        assert response.provider == "mock"
        assert response.model == "mock-1.0"
        assert response.text == "a response"
