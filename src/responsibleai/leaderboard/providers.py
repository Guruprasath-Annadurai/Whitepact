"""Model adapters — the thin, swappable layer that actually calls a live LLM
provider to collect responses for a leaderboard run.

Every adapter exposes the same `async generate(prompt: str) -> str` contract.
`LeaderboardRunner` (runner.py) never imports a provider SDK directly — it
only depends on this interface, so adding a new provider means adding one
adapter class here, nothing else.

Provider SDKs are imported lazily, inside `__init__`, not at module load
time. This keeps `google-generativeai` (not a required dependency — see
pyproject.toml's `leaderboard` extra) from breaking imports for anyone who
hasn't installed it, and keeps this module importable even with zero
provider credentials configured (the common case for running the test suite
or a self-hosted install that only uses the mock adapter for CI).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class ProviderNotConfiguredError(Exception):
    """Raised when an adapter is instantiated without a usable API key, or
    the provider's SDK package isn't installed. Callers should catch this
    and skip/flag the model rather than letting a run crash outright."""


class ModelAdapter(ABC):
    """Common interface every provider adapter implements."""

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """Return the model's raw text response to *prompt*.

        Implementations should use low/zero temperature and a bounded
        max-token budget — this is an evaluation harness, not a chat UI, and
        consistent, comparable outputs matter more than creativity.
        """


class OpenAIAdapter(ModelAdapter):
    def __init__(self, model: str, api_key: str | None) -> None:
        super().__init__(model)
        if not api_key:
            raise ProviderNotConfiguredError(
                "OPENAI_API_KEY / RAI_LEADERBOARD_OPENAI_API_KEY is not set — "
                "cannot evaluate an OpenAI model without it."
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "The 'openai' package is not installed. Install the "
                "'leaderboard' extra: pip install 'rai-governance-platform[leaderboard]'"
            ) from exc
        self._client = AsyncOpenAI(api_key=api_key)

    async def generate(self, prompt: str) -> str:
        response = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=400,
            temperature=0.0,
        )
        content = response.choices[0].message.content if response.choices else None
        return content or ""


class AnthropicAdapter(ModelAdapter):
    def __init__(self, model: str, api_key: str | None) -> None:
        super().__init__(model)
        if not api_key:
            raise ProviderNotConfiguredError(
                "ANTHROPIC_API_KEY / RAI_LEADERBOARD_ANTHROPIC_API_KEY is not set — "
                "cannot evaluate an Anthropic model without it."
            )
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "The 'anthropic' package is not installed. Install the "
                "'leaderboard' extra: pip install 'rai-governance-platform[leaderboard]'"
            ) from exc
        self._client = AsyncAnthropic(api_key=api_key)

    async def generate(self, prompt: str) -> str:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in response.content if hasattr(block, "text")]
        return "".join(parts)


class GoogleAdapter(ModelAdapter):
    def __init__(self, model: str, api_key: str | None) -> None:
        super().__init__(model)
        if not api_key:
            raise ProviderNotConfiguredError(
                "GOOGLE_API_KEY / RAI_LEADERBOARD_GOOGLE_API_KEY is not set — "
                "cannot evaluate a Google model without it."
            )
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ProviderNotConfiguredError(
                "The 'google-generativeai' package is not installed. Install "
                "the 'leaderboard' extra: pip install 'rai-governance-platform[leaderboard]'"
            ) from exc
        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(self.model)

    async def generate(self, prompt: str) -> str:
        response = await self._client.generate_content_async(
            prompt,
            generation_config={"max_output_tokens": 400, "temperature": 0.0},
        )
        return response.text or ""


class MockAdapter(ModelAdapter):
    """Deterministic, offline adapter — no network calls, no API keys.

    Used for the test suite and for `--dry-run` / demo mode so the entire
    pipeline (scoring, persistence, API, UI) is exercisable and CI-testable
    without real provider credentials. This intentionally does NOT attempt
    to simulate real model quality — every prompt gets the same generic,
    hedging, safe response unless a caller supplies `canned_responses` to
    override specific prompts by exact text match. Never presented as real
    eval data anywhere in the product; `source="mock"` is threaded through
    to the persisted run so it can't be confused with a live result.
    """

    _DEFAULT_RESPONSE = (
        "I don't have enough verified information to answer that confidently."
    )

    def __init__(
        self,
        model: str = "mock-model",
        canned_responses: dict[str, str] | None = None,
    ) -> None:
        super().__init__(model)
        self._canned = canned_responses or {}

    async def generate(self, prompt: str) -> str:
        return self._canned.get(prompt, self._DEFAULT_RESPONSE)


_ADAPTERS: dict[str, Callable[[str, str | None], ModelAdapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "google": GoogleAdapter,
}


def get_adapter(provider: str, model: str, api_keys: dict[str, str | None]) -> ModelAdapter:
    """Factory: build the right adapter for *provider*.

    *api_keys* maps provider name -> API key (or None), so callers pass in
    whatever's configured once rather than every call site reading env vars
    directly. Raises ProviderNotConfiguredError (not a bare KeyError/ImportError)
    for every failure mode, so callers have one exception type to catch.
    """
    if provider == "mock":
        return MockAdapter(model=model)
    adapter_cls = _ADAPTERS.get(provider)
    if adapter_cls is None:
        raise ProviderNotConfiguredError(
            f"Unknown provider '{provider}'. Supported: {', '.join([*_ADAPTERS, 'mock'])}."
        )
    return adapter_cls(model, api_keys.get(provider))
