"""Ollama adapter — the first-class local/offline brain (Art. III §3).

The Constitution names a local model as a first-class offline fallback whose
VOICE is identical to the hosted brain (same system prompt, same persona).
Ollama speaks plain REST on localhost, so this adapter uses only the stdlib —
no SDK to install. Configure with ``OLLAMA_URL`` (e.g. http://localhost:11434).

Usage fields: ``prompt_eval_count`` / ``eval_count`` in the /api/chat reply.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from meemoo.brain.types import CompletionResponse, Messages, Provider, ProviderError

logger = logging.getLogger(__name__)

_TIMEOUT_S = 120.0  # local models on laptop CPUs can be slow; generous but bounded


class OllamaProvider(Provider):
    """Local models via Ollama's ``POST /api/chat`` (stdlib HTTP, no SDK)."""

    name = "ollama"
    requires_key = False
    requires_url = True

    def complete(
        self,
        messages: Messages,
        model: str,
        max_tokens: int,
        *,
        system: str | None = None,
    ) -> CompletionResponse:
        chat: list[dict[str, str]] = []
        if system:
            chat.append({"role": "system", "content": system})
        chat.extend(dict(m) for m in messages)
        body = json.dumps(
            {
                "model": model,
                "messages": chat,
                "stream": False,
                "options": {"num_predict": max_tokens},
            }
        ).encode()
        url = f"{(self._base_url or '').rstrip('/')}/api/chat"
        request = urllib.request.Request(  # noqa: S310 — owner-configured local URL
            url, data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
                payload: dict[str, Any] = json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise ProviderError(self.name, type(exc).__name__) from exc

        message = payload.get("message") or {}
        text = str(message.get("content", "") or "")
        return CompletionResponse(
            text=text, provider=self.name, model=model,
            input_tokens=int(payload.get("prompt_eval_count", 0) or 0),
            output_tokens=int(payload.get("eval_count", 0) or 0),
            stop_reason="end_turn" if payload.get("done", True) else "other",
        )


PROVIDER = OllamaProvider
