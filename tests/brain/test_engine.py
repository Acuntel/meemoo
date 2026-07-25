"""The step-04 gate: same conversation, three brains, one persona.

The conversation runs against (a) the real Anthropic adapter over a stubbed
SDK, (b) the real Ollama adapter over stubbed local HTTP, and (c) the scripted
zero-key fallback — flipped purely by config. The SAME system prompt (persona)
must reach every provider, the cost meter must move, and the deterministic
rails (medical, refusal, provider failure) must never depend on a model.
"""

from __future__ import annotations

import io
import json
import sys
import types as pytypes
from typing import Any

import pytest
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.engine import REFUSAL_LINE, ConversationBrain
from meemoo.brain.medical import MEDICAL_HANDOFF
from meemoo.brain.personality import DeviceContext
from meemoo.brain.providers.fake import FakeProvider
from meemoo.brain.types import CompletionResponse, Messages, Provider, ProviderError
from meemoo.brain.usage import usage_today
from meemoo.core.config import get_settings
from meemoo.core.models import ModelConfig

CONVERSATION = ["good morning meemoo", "I'm feeling pretty good", "thank you, goodbye"]


def _stub_anthropic_sdk(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    class _Usage:
        input_tokens = 100
        output_tokens = 20

    class _Block:
        type = "text"
        text = "Hello from Claude."

    class _Message:
        stop_reason = "end_turn"
        usage = _Usage()
        content = [_Block()]

    class _Messages:
        def create(self, **kwargs: Any) -> _Message:
            calls.append(kwargs)
            return _Message()

    class _Client:
        def __init__(self, api_key: str | None = None) -> None:
            self.messages = _Messages()

    module = pytypes.ModuleType("anthropic")
    module.Anthropic = _Client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", module)
    return calls


def _stub_ollama_http(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    bodies: list[dict[str, Any]] = []

    class _Resp(io.BytesIO):
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: Any, timeout: float = 0) -> _Resp:
        bodies.append(json.loads(request.data.decode()))
        return _Resp(json.dumps({
            "message": {"role": "assistant", "content": "Hello from llama."},
            "done": True, "prompt_eval_count": 50, "eval_count": 10,
        }).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return bodies


def _flip_all_tiers(
    db_factory: sessionmaker[DbSession], device_id: int, provider: str, model: str
) -> None:
    with db_factory() as db:
        db.query(ModelConfig).filter(ModelConfig.device_id == device_id).delete()
        for tier in ("reflex", "conversation", "reasoning"):
            db.add(ModelConfig(device_id=device_id, tier=tier,
                               provider=provider, model=model, max_tokens=256))
        db.commit()


def _brain(db_factory: sessionmaker[DbSession], device_id: int) -> ConversationBrain:
    return ConversationBrain(
        device_id=device_id, db_factory=db_factory,
        device=DeviceContext(person_name="Ruth"),
    )


# ------------------------------------------------------------ the gate test
def test_same_conversation_three_brains_one_persona(
    db_factory: sessionmaker[DbSession],
    seeded: tuple[int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device_id, _ = seeded
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    get_settings.cache_clear()
    anthropic_calls = _stub_anthropic_sdk(monkeypatch)
    ollama_bodies = _stub_ollama_http(monkeypatch)

    transcripts: dict[str, list[str]] = {}

    # --- config: Anthropic ---------------------------------------------------
    _flip_all_tiers(db_factory, device_id, "anthropic", "claude-sonnet-5")
    brain = _brain(db_factory, device_id)
    transcripts["anthropic"] = [brain.reply(line) for line in CONVERSATION]

    # --- config flip: Ollama -------------------------------------------------
    _flip_all_tiers(db_factory, device_id, "ollama", "llama3.2")
    brain = _brain(db_factory, device_id)
    transcripts["ollama"] = [brain.reply(line) for line in CONVERSATION]

    # --- config flip: scripted (no provider at all) --------------------------
    _flip_all_tiers(db_factory, device_id, "scripted", "-")
    brain = _brain(db_factory, device_id)
    transcripts["scripted"] = [brain.reply(line) for line in CONVERSATION]

    # every brain answered every turn
    for name, lines in transcripts.items():
        assert len(lines) == len(CONVERSATION) and all(lines), name

    # the persona (system prompt) is IDENTICAL across hosted and local brains
    anthropic_system = anthropic_calls[0]["system"]
    ollama_system = ollama_bodies[0]["messages"][0]
    assert ollama_system["role"] == "system"
    assert anthropic_system == ollama_system["content"]
    assert "Ruth" in anthropic_system and "Meemoo" in anthropic_system

    # the cost meter moved (per-request rows + daily aggregate)
    today = usage_today(db_factory, device_id)
    assert today.requests == 2 * len(CONVERSATION)  # scripted burns no tokens
    assert today.cost_usd > 0  # claude-sonnet-5 calls are priced

    get_settings.cache_clear()


# ----------------------------------------------------------- rails and flow
def test_medical_rail_answers_without_any_provider_call(
    seeded: tuple[int, int], db_factory: sessionmaker[DbSession]
) -> None:
    device_id, _ = seeded
    fake = FakeProvider()
    brain = ConversationBrain(
        device_id=device_id, db_factory=db_factory,
        provider_overrides={"anthropic": fake},
        device=DeviceContext(person_name="Ruth"),
    )
    reply = brain.reply("should I double my dose of my heart medication?")
    assert reply == MEDICAL_HANDOFF
    assert fake.calls == []  # the model was provably never consulted
    assert usage_today(db_factory, device_id).requests == 0


def test_provider_failure_degrades_to_scripted(seeded: tuple[int, int]) -> None:
    class Exploding(Provider):
        name = "anthropic"
        requires_key = False

        def complete(
            self, messages: Messages, model: str, max_tokens: int,
            *, system: str | None = None,
        ) -> CompletionResponse:
            raise ProviderError(self.name, "boom")

    brain = ConversationBrain(
        device_id=seeded[0], provider_overrides={"anthropic": Exploding()},
        device=DeviceContext(person_name="Ruth"),
    )
    reply = brain.reply("good morning")
    assert reply  # warm scripted line, not an exception
    assert "Ruth" in reply


def test_refusal_yields_deterministic_warm_line(seeded: tuple[int, int]) -> None:
    class Refusing(Provider):
        name = "anthropic"
        requires_key = False

        def complete(
            self, messages: Messages, model: str, max_tokens: int,
            *, system: str | None = None,
        ) -> CompletionResponse:
            return CompletionResponse(
                text="", provider=self.name, model=model, stop_reason="refusal"
            )

    brain = ConversationBrain(
        device_id=seeded[0], provider_overrides={"anthropic": Refusing()}
    )
    assert brain.reply("hello") == REFUSAL_LINE


def test_task_type_routes_to_tier_models(seeded: tuple[int, int]) -> None:
    fake = FakeProvider()
    brain = ConversationBrain(
        device_id=seeded[0], provider_overrides={"anthropic": fake}
    )
    brain.reply("time for your reminder", task_type="reminder")
    brain.reply("something ambiguous happened", task_type="ambiguous")
    models = [call["model"] for call in fake.calls]
    assert models == ["claude-haiku-4-5", "claude-opus-5"]  # cheap vs strong


def test_preset_switch_visibly_changes_the_persona(seeded: tuple[int, int]) -> None:
    brain = ConversationBrain(device_id=seeded[0], role="trainer",
                              sub_preset="encouraging")
    nice = brain.system_prompt()
    brain.set_preset("trainer", "hardcore")
    hard = brain.system_prompt()
    assert nice != hard and "drill" in hard.lower()


def test_rolling_context_is_capped(seeded: tuple[int, int]) -> None:
    fake = FakeProvider()
    brain = ConversationBrain(
        device_id=seeded[0], provider_overrides={"anthropic": fake}
    )
    for i in range(60):
        brain.reply(f"turn {i}")
    assert len(brain.context) <= 40
