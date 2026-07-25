"""Anthropic adapter — official ``anthropic`` SDK, lazily imported.

Install via ``uv sync --group brain``. Without the SDK, calls raise
:class:`ProviderError` (the engine degrades to the scripted fallback); the
module itself always imports so startup never crashes (Art. IX §3).

API notes (per Anthropic docs, 2026-06):
- ``system`` is a top-level parameter, not a message role.
- Safety classifiers on Claude Opus 5 / Fable 5 can decline with a normal 200
  and ``stop_reason: "refusal"`` — we check it BEFORE reading content and we
  opt into server-side fallbacks (``fallbacks: "default"`` + beta header) on
  those models so a benign decline is re-served by a fallback model.
- Usage token fields: ``usage.input_tokens`` / ``usage.output_tokens``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from meemoo.brain.types import CompletionResponse, Messages, Provider, ProviderError

logger = logging.getLogger(__name__)

#: Models whose safety classifiers can refuse; opt into server-side fallbacks.
_FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5", "claude-mythos-5")
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(Provider):
    """Claude via the Messages API (official SDK)."""

    name = "anthropic"
    requires_key = True

    def _client(self) -> Any:
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderError(self.name, "anthropic SDK not installed") from exc
        return anthropic.Anthropic(api_key=self._api_key)

    def _request_kwargs(
        self, messages: Messages, model: str, max_tokens: int, system: str | None
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [dict(m) for m in messages],
        }
        if system:
            kwargs["system"] = system
        if model.startswith(_FALLBACK_MODELS):
            # Version-safe opt-in (extra_body works on any SDK release).
            kwargs["extra_headers"] = {"anthropic-beta": _FALLBACK_BETA}
            kwargs["extra_body"] = {"fallbacks": "default"}
        return kwargs

    def complete(
        self,
        messages: Messages,
        model: str,
        max_tokens: int,
        *,
        system: str | None = None,
    ) -> CompletionResponse:
        client = self._client()
        try:
            response = client.messages.create(
                **self._request_kwargs(messages, model, max_tokens, system)
            )
        except Exception as exc:  # SDK error classes vary; never leak the key
            raise ProviderError(self.name, type(exc).__name__) from exc

        stop = str(getattr(response, "stop_reason", None) or "end_turn")
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        # Check refusal BEFORE reading content — a refusal may have no blocks.
        if stop == "refusal":
            logger.warning("anthropic refusal", extra={"fields": {"model": model}})
            return CompletionResponse(
                text="", provider=self.name, model=model,
                input_tokens=input_tokens, output_tokens=output_tokens,
                stop_reason="refusal",
            )
        text = "".join(
            str(block.text)
            for block in getattr(response, "content", [])
            if getattr(block, "type", "") == "text"
        )
        normalized = stop if stop in ("end_turn", "max_tokens") else "other"
        return CompletionResponse(
            text=text, provider=self.name, model=model,
            input_tokens=input_tokens, output_tokens=output_tokens,
            stop_reason=normalized,
        )

    def stream(
        self,
        messages: Messages,
        model: str,
        max_tokens: int,
        *,
        system: str | None = None,
    ) -> Iterator[str]:
        client = self._client()
        kwargs = self._request_kwargs(messages, model, max_tokens, system)
        try:
            with client.messages.stream(**kwargs) as stream:
                yield from stream.text_stream
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(self.name, type(exc).__name__) from exc


PROVIDER = AnthropicProvider
