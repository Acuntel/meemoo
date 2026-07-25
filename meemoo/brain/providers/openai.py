"""OpenAI adapter — official ``openai`` SDK, lazily imported.

Install via ``uv sync --group brain``. System prompt travels as a leading
``{"role": "system"}`` message (Chat Completions convention). Usage fields:
``usage.prompt_tokens`` / ``usage.completion_tokens``.
"""

from __future__ import annotations

import logging
from typing import Any

from meemoo.brain.types import CompletionResponse, Messages, Provider, ProviderError

logger = logging.getLogger(__name__)


class OpenAIProvider(Provider):
    """GPT models via the Chat Completions API (official SDK)."""

    name = "openai"
    requires_key = True

    def _client(self) -> Any:
        try:
            import openai
        except ImportError as exc:
            raise ProviderError(self.name, "openai SDK not installed") from exc
        return openai.OpenAI(api_key=self._api_key)

    def complete(
        self,
        messages: Messages,
        model: str,
        max_tokens: int,
        *,
        system: str | None = None,
    ) -> CompletionResponse:
        client = self._client()
        chat: list[dict[str, str]] = []
        if system:
            chat.append({"role": "system", "content": system})
        chat.extend(dict(m) for m in messages)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=chat,
                max_completion_tokens=max_tokens,
            )
        except Exception as exc:  # never leak the key
            raise ProviderError(self.name, type(exc).__name__) from exc

        choice = response.choices[0] if getattr(response, "choices", None) else None
        text = str(getattr(getattr(choice, "message", None), "content", "") or "")
        finish = str(getattr(choice, "finish_reason", "") or "")
        stop = {"stop": "end_turn", "length": "max_tokens",
                "content_filter": "refusal"}.get(finish, "other")
        usage = getattr(response, "usage", None)
        return CompletionResponse(
            text=text, provider=self.name, model=model,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            stop_reason=stop,
        )


PROVIDER = OpenAIProvider
