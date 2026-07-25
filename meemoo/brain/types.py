"""Provider adapter interface — the model-agnostic seam (MASTER_PROMPT §3).

Every LLM provider sits behind :class:`Provider` with the exact signature the
spec demands: ``complete(messages, model, max_tokens) -> response`` plus a
streaming variant. One provider = one file in ``meemoo/brain/providers/``;
a fifth provider must require exactly one new file (proved by ``fake.py`` and
the factory's import-by-name convention).

Constitution Art. III §3: hosted LLMs are a sanctioned exception, but they sit
behind THIS adapter — swapping vendors is a config change, never a rewrite.
Art. IX §3: a missing SDK or credential surfaces as ``None`` from the factory
or a :class:`ProviderError` at call time — never a crash at import/startup.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

#: One chat turn: ``{"role": "user"|"assistant"|"system", "content": "..."}``.
#: Matches the voice SessionManager's rolling-context shape exactly.
Messages = Sequence[Mapping[str, str]]


class ProviderError(Exception):
    """A provider call failed (SDK missing, network, API error).

    Never carries key material — wrap upstream exceptions with a short reason.
    """

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason


@dataclass(frozen=True, slots=True)
class CompletionResponse:
    """One completed LLM turn, normalized across providers."""

    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    #: normalized: "end_turn" | "max_tokens" | "refusal" | "other"
    stop_reason: str = "end_turn"

    @property
    def refused(self) -> bool:
        return self.stop_reason == "refusal"


class Provider(ABC):
    """Abstract LLM provider. Subclasses live one-per-file under providers/.

    Class attributes let the factory resolve credentials generically:
    ``requires_key`` providers need an API key; ``requires_url`` providers
    (Ollama) need a base URL instead.
    """

    name: str = "abstract"
    requires_key: bool = True
    requires_url: bool = False

    def __init__(self, *, api_key: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key
        self._base_url = base_url

    @abstractmethod
    def complete(
        self,
        messages: Messages,
        model: str,
        max_tokens: int,
        *,
        system: str | None = None,
    ) -> CompletionResponse:
        """Run one completion. Raises :class:`ProviderError` on any failure."""

    def stream(
        self,
        messages: Messages,
        model: str,
        max_tokens: int,
        *,
        system: str | None = None,
    ) -> Iterator[str]:
        """Streaming variant. Default: one chunk from :meth:`complete`.

        Providers with real incremental streaming override this; callers get
        the same iterator contract either way.
        """
        yield self.complete(messages, model, max_tokens, system=system).text

    def __repr__(self) -> str:  # never include key material
        return f"<{type(self).__name__} name={self.name!r}>"
