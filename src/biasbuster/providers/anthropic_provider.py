from __future__ import annotations

from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse


class AnthropicProvider(BaseProvider):
    """
    Provider for Anthropic Claude models.

    Requires the ``anthropic`` extra::

        pip install "biasbuster[anthropic]"

    Usage::

        provider = AnthropicProvider(api_key="sk-ant-...", model="claude-3-5-sonnet-20241022")
        runner = BiasBusterRunner(provider=provider)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(
                "Anthropic provider requires the anthropic package. "
                "Install it with: pip install 'biasbuster[anthropic]'"
            ) from e

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=request.max_tokens,
            system=request.system_prompt,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=request.temperature,
        )
        return CompletionResponse(
            text=response.content[0].text if response.content else "",
            model=response.model,
            provider=self.name,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
