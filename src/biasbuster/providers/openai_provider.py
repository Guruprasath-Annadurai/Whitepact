from __future__ import annotations

from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse


class OpenAIProvider(BaseProvider):
    """
    Provider for OpenAI models (GPT-4o, GPT-4-turbo, GPT-3.5-turbo, etc.).

    Requires the ``openai`` extra::

        pip install "biasbuster[openai]"

    Usage::

        provider = OpenAIProvider(api_key="sk-...", model="gpt-4o")
        runner = BiasBusterRunner(provider=provider)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,
    ) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError(
                "OpenAI provider requires the openai package. "
                "Install it with: pip install 'biasbuster[openai]'"
            ) from e

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.prompt},
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        choice = response.choices[0]
        return CompletionResponse(
            text=choice.message.content or "",
            model=response.model,
            provider=self.name,
            input_tokens=response.usage.prompt_tokens if response.usage else None,
            output_tokens=response.usage.completion_tokens if response.usage else None,
        )
