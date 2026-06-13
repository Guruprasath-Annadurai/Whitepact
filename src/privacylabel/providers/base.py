from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LabelRequest:
    """A single labeling request."""

    text: str
    prompt_template: str = "Classify the following text into one of the appropriate categories:\n\n{text}\n\nLabel:"
    max_tokens: int = 64
    temperature: float = 0.0


@dataclass(frozen=True)
class LabelResponse:
    """A single labeling response from a provider."""

    label: str
    confidence: float
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class BaseLabelProvider(ABC):
    """
    Abstract base for all PrivacyLabel LLM providers.

    Providers wrap a language model and expose a uniform interface for
    on-device label generation. The calling code never sees raw API details.

    To add a new provider, subclass this and implement ``label`` and
    the two name properties.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier, e.g. 'openai'."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model name string as returned by the provider."""
        ...

    @abstractmethod
    async def label(self, request: LabelRequest) -> LabelResponse:
        """Generate a single label for the given request."""
        ...

    async def batch_label(
        self, texts: list[str], prompt_template: str | None = None
    ) -> list[dict[str, object]]:
        """
        Label a list of texts.

        Default: sequential calls to ``label``. Override for providers
        that support native batching (e.g. OpenAI batch API).
        """
        import asyncio

        template = prompt_template or LabelRequest.prompt_template
        requests = [LabelRequest(text=t, prompt_template=template) for t in texts]
        responses = await asyncio.gather(*[self.label(r) for r in requests])
        return [
            {
                "label": r.label,
                "confidence": r.confidence,
                "model": r.model,
                "provider": r.provider,
            }
            for r in responses
        ]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name!r})"
