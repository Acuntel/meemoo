"""Google adapter — official ``google-genai`` SDK, lazily imported.

Install via ``uv sync --group brain``. Gemini role names differ ("model", not
"assistant"); the system prompt travels as ``system_instruction`` in config.
Usage fields: ``usage_metadata.prompt_token_count`` /
``usage_metadata.candidates_token_count``.
"""

from __future__ import annotations

import logging
from typing import Any

from meemoo.brain.types import CompletionResponse, Messages, Provider, ProviderError

logger = logging.getLogger(__name__)


class GoogleProvider(Provider):
    """Gemini models via the google-genai SDK."""

    name = "google"
    requires_key = True

    def _client(self) -> Any:
        try:
            from google import genai
        except ImportError as exc:
            raise ProviderError(self.name, "google-genai SDK not installed") from exc
        return genai.Client(api_key=self._api_key)

    def complete(
        self,
        messages: Messages,
        model: str,
        max_tokens: int,
        *,
        system: str | None = None,
    ) -> CompletionResponse:
        client = self._client()
        contents = [
            {
                "role": "model" if m.get("role") == "assistant" else "user",
                "parts": [{"text": m.get("content", "")}],
            }
            for m in messages
        ]
        config: dict[str, Any] = {"max_output_tokens": max_tokens}
        if system:
            config["system_instruction"] = system
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except Exception as exc:  # never leak the key
            raise ProviderError(self.name, type(exc).__name__) from exc

        text = str(getattr(response, "text", "") or "")
        meta = getattr(response, "usage_metadata", None)
        return CompletionResponse(
            text=text, provider=self.name, model=model,
            input_tokens=int(getattr(meta, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(meta, "candidates_token_count", 0) or 0),
            stop_reason="end_turn" if text else "other",
        )


PROVIDER = GoogleProvider
