"""Provider interface + factory: lazy SDKs, graceful degradation, 5th file."""

from __future__ import annotations

import io
import json
import sys
import types as pytypes
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.providers import create_provider, first_available, load_provider_class
from meemoo.brain.providers.anthropic import AnthropicProvider
from meemoo.brain.providers.fake import FakeProvider
from meemoo.brain.providers.ollama import OllamaProvider
from meemoo.brain.types import CompletionResponse, Provider, ProviderError
from meemoo.core.config import Settings
from meemoo.core.models import ProviderKey
from meemoo.core.secrets import encrypt_secret


# --------------------------------------------------------------- degradation
def test_no_credentials_yields_none_never_crash(bare_settings: Settings) -> None:
    assert create_provider("anthropic") is None
    assert create_provider("openai") is None
    assert create_provider("google") is None
    assert create_provider("ollama") is None  # no OLLAMA_URL configured
    assert first_available() is None


def test_unknown_provider_module_is_none_not_crash(bare_settings: Settings) -> None:
    assert create_provider("does_not_exist") is None
    assert load_provider_class("../evil") is None


def test_missing_sdk_raises_provider_error_at_call_not_import(
    bare_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SDK absence surfaces at call time as ProviderError, never at startup."""
    monkeypatch.setitem(sys.modules, "anthropic", None)  # force ImportError
    provider = AnthropicProvider(api_key="k")
    with pytest.raises(ProviderError):
        provider.complete([{"role": "user", "content": "hi"}], "claude-opus-5", 64)


# ------------------------------------------------------------ key resolution
def test_db_encrypted_key_resolves_provider(
    bare_settings: Settings,
    db_factory: sessionmaker[DbSession],
    seeded: tuple[int, int],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    device_id, _ = seeded
    monkeypatch.setenv("MEEMOO_FERNET_KEY_FILE", str(tmp_path / "f.key"))
    from meemoo.core.config import get_settings

    get_settings.cache_clear()
    with db_factory() as db:
        db.add(ProviderKey(
            device_id=device_id, provider="anthropic",
            encrypted_key=encrypt_secret("sk-test-123"),
        ))
        db.commit()
    provider = create_provider("anthropic", device_id=device_id, db_factory=db_factory)
    assert isinstance(provider, AnthropicProvider)
    assert provider._api_key == "sk-test-123"
    assert "sk-test-123" not in repr(provider)
    get_settings.cache_clear()


# --------------------------------------------------- fifth provider = 1 file
def test_fake_is_the_fifth_provider_one_file(bare_settings: Settings) -> None:
    provider = create_provider("fake")
    assert isinstance(provider, FakeProvider)
    response = provider.complete(
        [{"role": "user", "content": "good morning"}], "fake-1", 64,
        system="persona",
    )
    assert "morning" in response.text.lower()
    assert provider.last_system == "persona"
    assert response.input_tokens > 0 and response.output_tokens > 0


def test_synthetic_sixth_provider_needs_only_a_module(
    bare_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Injecting one module under providers/ is ALL a new provider needs."""

    class SixthProvider(Provider):
        name = "sixth"
        requires_key = False

        def complete(
            self, messages: Any, model: str, max_tokens: int, *, system: str | None = None
        ) -> CompletionResponse:
            return CompletionResponse(text="six", provider=self.name, model=model)

    module = pytypes.ModuleType("meemoo.brain.providers.sixth")
    module.PROVIDER = SixthProvider  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "meemoo.brain.providers.sixth", module)
    provider = create_provider("sixth")
    assert provider is not None
    assert provider.complete([], "m", 8).text == "six"


# ------------------------------------------------------------------- adapters
class _StubBlock:
    type = "text"

    def __init__(self, text: str) -> None:
        self.text = text


class _StubUsage:
    input_tokens = 11
    output_tokens = 7


class _StubMessage:
    def __init__(self, stop_reason: str) -> None:
        self.stop_reason = stop_reason
        self.usage = _StubUsage()
        self.content = [_StubBlock("hello "), _StubBlock("there")]


def _install_stub_anthropic(
    monkeypatch: pytest.MonkeyPatch, stop_reason: str = "end_turn"
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    class _Messages:
        def create(self, **kwargs: Any) -> _StubMessage:
            calls.append(kwargs)
            return _StubMessage(stop_reason)

    class _Client:
        def __init__(self, api_key: str | None = None) -> None:
            self.messages = _Messages()

    module = pytypes.ModuleType("anthropic")
    module.Anthropic = _Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", module)
    return calls


def test_anthropic_adapter_request_and_response(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_stub_anthropic(monkeypatch)
    provider = AnthropicProvider(api_key="k")
    response = provider.complete(
        [{"role": "user", "content": "hi"}], "claude-haiku-4-5", 300, system="sys"
    )
    assert response.text == "hello there"
    assert (response.input_tokens, response.output_tokens) == (11, 7)
    request = calls[0]
    assert request["model"] == "claude-haiku-4-5"
    assert request["max_tokens"] == 300
    assert request["system"] == "sys"
    assert "extra_body" not in request  # fallbacks only on opus-5/fable-5


def test_anthropic_adapter_refusal_and_fallback_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_stub_anthropic(monkeypatch, stop_reason="refusal")
    provider = AnthropicProvider(api_key="k")
    response = provider.complete(
        [{"role": "user", "content": "hi"}], "claude-opus-5", 300
    )
    assert response.refused and response.text == ""
    request = calls[0]
    assert request["extra_body"] == {"fallbacks": "default"}
    assert "server-side-fallback" in request["extra_headers"]["anthropic-beta"]


def test_ollama_adapter_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class _Resp(io.BytesIO):
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: Any, timeout: float = 0) -> _Resp:
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode())
        return _Resp(json.dumps({
            "message": {"role": "assistant", "content": "local hello"},
            "done": True, "prompt_eval_count": 5, "eval_count": 3,
        }).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    provider = OllamaProvider(base_url="http://localhost:11434/")
    response = provider.complete(
        [{"role": "user", "content": "hi"}], "llama3.2", 128, system="sys"
    )
    assert response.text == "local hello"
    assert (response.input_tokens, response.output_tokens) == (5, 3)
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["body"]["messages"][0] == {"role": "system", "content": "sys"}
    assert captured["body"]["options"]["num_predict"] == 128


def test_stream_default_yields_completion(bare_settings: Settings) -> None:
    provider = FakeProvider()
    chunks = list(provider.stream([{"role": "user", "content": "bye"}], "fake", 16))
    assert chunks and "".join(chunks)
