from __future__ import annotations

import pytest

from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse


class MockProvider(BaseProvider):
    """
    Deterministic provider for unit tests.

    Pass a dict mapping prompt substrings to responses.
    Unmatched prompts return ``default_response``.
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        default_response: str = "This is a generic test response about the person.",
    ) -> None:
        self._responses = responses or {}
        self._default = default_response
        self.call_count = 0

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        for key, response in self._responses.items():
            if key in request.prompt:
                return CompletionResponse(
                    text=response,
                    model=self.model_name,
                    provider=self.name,
                    input_tokens=len(request.prompt.split()),
                    output_tokens=len(response.split()),
                )
        return CompletionResponse(
            text=self._default,
            model=self.model_name,
            provider=self.name,
        )


class BiasedMockProvider(MockProvider):
    """
    Provider that returns noticeably different responses per gender,
    used to test that the probe correctly flags bias.
    """

    _MASCULINE_RESPONSE = (
        "James is a decisive and assertive leader with strong technical vision. "
        "He commands respect from his team and drives results with confidence. "
        "His strategic thinking and bold approach make him ideal for senior roles. "
        "James demonstrates exceptional problem-solving and mentors junior engineers."
    )
    _FEMININE_RESPONSE = (
        "Mary is a collaborative and supportive team member who helps others. "
        "She is kind, empathetic, and good at communicating. "
        "She works well in a team environment and keeps morale high. "
        "Mary is helpful and approachable, making her a pleasant colleague."
    )
    _NEUTRAL_RESPONSE = (
        "Alex is a software engineer with experience in distributed systems. "
        "They have contributed to multiple projects and work well with their team. "
        "Alex has demonstrated solid technical skills across several domains."
    )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1
        prompt = request.prompt

        if "James" in prompt:
            text = self._MASCULINE_RESPONSE
        elif "Mary" in prompt:
            text = self._FEMININE_RESPONSE
        elif "Alex" in prompt:
            text = self._NEUTRAL_RESPONSE
        else:
            text = self._default

        return CompletionResponse(text=text, model=self.model_name, provider=self.name)


class UnbiasedMockProvider(MockProvider):
    """
    Provider that returns structurally identical responses regardless of gender.
    Used to confirm that the probe correctly passes unbiased models.
    """

    _TEMPLATE = (
        "{name} is an experienced software engineer with a strong track record "
        "of delivering high-quality systems. They have demonstrated expertise in "
        "distributed architectures and led cross-functional teams effectively. "
        "Their technical skills and collaborative approach make them well-suited "
        "for senior engineering roles."
    )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.call_count += 1

        for first_name in ["James", "Mary", "Alex"]:
            if first_name in request.prompt:
                text = self._TEMPLATE.format(name=first_name)
                return CompletionResponse(
                    text=text, model=self.model_name, provider=self.name
                )

        return CompletionResponse(
            text=self._TEMPLATE.format(name="the engineer"),
            model=self.model_name,
            provider=self.name,
        )


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def biased_provider() -> BiasedMockProvider:
    return BiasedMockProvider()


@pytest.fixture
def unbiased_provider() -> UnbiasedMockProvider:
    return UnbiasedMockProvider()
