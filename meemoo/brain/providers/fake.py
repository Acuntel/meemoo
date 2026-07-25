"""FakeProvider — the fifth provider, and the proof it takes ONE file.

Deterministic, offline, dependency-free. Used by tests (the config-flip gate
runs the same conversation through "anthropic"-shaped stubs, "ollama", and
this) and by ``python -m meemoo.brain.demo --provider fake``. It records every
call so tests can assert the SAME system prompt (persona) reaches every
provider — the Constitution's "the user can never tell which brain is
driving" invariant, checked at the seam.
"""

from __future__ import annotations

from meemoo.brain.types import CompletionResponse, Messages, Provider

_CANNED = [
    ("bye", "Goodbye for now. I'll be right here."),
    ("thank", "You're very welcome."),
    ("morning", "Good morning! I hope you slept well."),
    ("how are you", "I'm doing just fine, thank you for asking."),
    ("tired", "I'm sorry you're feeling tired. Be gentle with yourself today."),
    ("good", "That's wonderful to hear."),
]


class FakeProvider(Provider):
    """Keyless, deterministic stand-in provider."""

    name = "fake"
    requires_key = False

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None) -> None:
        super().__init__(api_key=api_key, base_url=base_url)
        self.calls: list[dict[str, object]] = []
        self.last_system: str | None = None

    def complete(
        self,
        messages: Messages,
        model: str,
        max_tokens: int,
        *,
        system: str | None = None,
    ) -> CompletionResponse:
        self.last_system = system
        self.calls.append(
            {"messages": [dict(m) for m in messages], "model": model,
             "max_tokens": max_tokens, "system": system}
        )
        last_user = next(
            (m.get("content", "") for m in reversed(list(messages))
             if m.get("role") == "user"),
            "",
        )
        lowered = last_user.lower()
        reply = next(
            (line for needle, line in _CANNED if needle in lowered),
            f"I hear you — you said: {last_user}",
        )
        return CompletionResponse(
            text=reply, provider=self.name, model=model,
            input_tokens=sum(len(m.get("content", "").split()) for m in messages),
            output_tokens=len(reply.split()),
        )


PROVIDER = FakeProvider
