from __future__ import annotations

import asyncio
from functools import partial

from biasbuster.providers.base import BaseProvider, CompletionRequest, CompletionResponse


class HuggingFaceProvider(BaseProvider):
    """
    Provider for local HuggingFace models via the transformers pipeline.

    Requires the ``huggingface`` extra::

        pip install "biasbuster[huggingface]"

    Usage::

        provider = HuggingFaceProvider(model="mistralai/Mistral-7B-Instruct-v0.2")
        runner = BiasBusterRunner(provider=provider)
    """

    def __init__(
        self,
        model: str = "microsoft/Phi-3-mini-4k-instruct",
        device: str = "cpu",
    ) -> None:
        try:
            from transformers import pipeline
        except ImportError as e:
            raise ImportError(
                "HuggingFace provider requires transformers and torch. "
                "Install with: pip install 'biasbuster[huggingface]'"
            ) from e

        self._model = model
        self._pipe = pipeline(
            "text-generation",
            model=model,
            device=device,
            trust_remote_code=True,
        )

    @property
    def name(self) -> str:
        return "huggingface"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.prompt},
        ]
        loop = asyncio.get_event_loop()
        fn = partial(
            self._pipe,
            messages,
            max_new_tokens=request.max_tokens,
            temperature=max(request.temperature, 1e-7),
            do_sample=request.temperature > 0,
        )
        result = await loop.run_in_executor(None, fn)
        text: str = result[0]["generated_text"][-1]["content"]
        return CompletionResponse(text=text, model=self._model, provider=self.name)


class OllamaProvider(BaseProvider):
    """
    Provider for local Ollama models (no API key required).

    Requires Ollama running locally: https://ollama.ai

    Usage::

        provider = OllamaProvider(model="llama3.2")
        runner = BiasBusterRunner(provider=provider)
    """

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
    ) -> None:
        import httpx

        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=120.0)

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.prompt},
            ],
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        response = await self._client.post(
            f"{self._base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return CompletionResponse(
            text=data["message"]["content"],
            model=self._model,
            provider=self.name,
        )
