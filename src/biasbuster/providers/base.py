from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CompletionRequest:
    prompt: str
    max_tokens: int = 512
    temperature: float = 0.0
    system_prompt: str = (
        "You are a helpful assistant. Answer the question directly and concisely."
    )
    extra: dict = field(default_factory=dict)


@dataclass
class CompletionResponse:
    text: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class BaseProvider(ABC):
    """
    Abstraction over any LLM provider.

    All providers must implement ``complete``. The default ``complete_batch``
    uses ``asyncio.gather`` for parallel requests — override for provider-level
    batching (e.g., OpenAI batch API).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'openai'."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Full model identifier, e.g. 'gpt-4o'."""
        ...

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a single completion request and return the response."""
        ...

    async def complete_batch(
        self,
        requests: list[CompletionRequest],
        *,
        max_concurrency: int = 5,
    ) -> list[CompletionResponse]:
        """Run multiple completions in parallel, bounded by max_concurrency."""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _one(req: CompletionRequest) -> CompletionResponse:
            async with semaphore:
                return await self.complete(req)

        return list(await asyncio.gather(*[_one(r) for r in requests]))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name!r})"
