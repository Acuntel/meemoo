"""THE DISTRESS BYPASS tests — the most important tests of Phase 3.

Prove, with all API keys absent AND the network mocked dead, that every
distress phrase (and fuzzy STT-typo variants) fires ``utterance.distress``
directly, with the brain never consulted (Constitution Art. IV §4–5).
"""

from __future__ import annotations

import socket

import pytest

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.core.config import Settings
from meemoo.voice.distress import (
    DISTRESS_ACK,
    DISTRESS_PHRASES,
    DistressDetector,
    StopDetector,
)
from meemoo.voice.pipeline import VoicePipeline

from .conftest import CountingBrain, FakeTTS

DISTRESS_UTTERANCES = [
    "help me",
    "Help me!",
    "please help me now",
    "I need help",
    "helb me",  # STT typo — fuzzy match must catch it
    "i need helb",
    "call someone",
    "call someone please",
    "emergency",
    "emergensy",  # STT typo
    "this is an emergency",
    "call 911",
    "call nine one one",
    "I've fallen",
    "i have fallen down",
    "I can't get up",
    "i cant get up",
    "get help",
    "send help",
    "somebody help",
    "HELP",
]


@pytest.fixture
def dead_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any attempt to CONNECT anywhere blows up the test (asyncio's local
    self-pipe still works — we kill the network, not the event loop)."""

    def _refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted in the distress path")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)


class TestDetector:
    @pytest.mark.parametrize("utterance", DISTRESS_UTTERANCES)
    def test_fires_on_variants(self, utterance: str) -> None:
        assert DistressDetector().check(utterance) is not None

    def test_every_configured_phrase_fires_verbatim(self) -> None:
        detector = DistressDetector()
        for phrase in DISTRESS_PHRASES:
            assert detector.check(phrase) is not None, phrase

    def test_recall_over_precision_negation_still_fires(self) -> None:
        # Art. IV §5: a false alarm is a cheap question. Negations fire.
        assert DistressDetector().check("I don't need help") is not None

    def test_ordinary_chat_does_not_fire(self) -> None:
        detector = DistressDetector()
        for text in [
            "good morning meemoo",
            "the garden looks lovely today",
            "my grandson visited yesterday",
            "what time is my medication",
            "hey meemoo",  # the wake word must never collide (Constitution)
        ]:
            assert detector.check(text) is None, text

    def test_construction_is_pure(self, dead_network: None) -> None:
        DistressDetector().check("help me")  # no socket, no key, no model


class TestBypass:
    async def test_distress_bypasses_brain_offline(
        self,
        pipeline: VoicePipeline,
        bus: EventBus,
        brain: CountingBrain,
        fake_tts: FakeTTS,
        dead_network: None,
        bare_settings: Settings,
    ) -> None:
        """No API keys (bare_settings), no network — distress still escalates."""
        assert bare_settings.anthropic_api_key is None  # keys truly absent
        sub = bus.subscribe(topics.DISTRESS_HEARD)
        await pipeline.handle_text("help me")

        event = await sub.get()
        assert event.topic == topics.DISTRESS_HEARD
        assert event.payload["phrase"] == "help me"
        assert event.payload["transcript"] == "help me"
        assert brain.calls == []  # THE bypass: brain never consulted
        spoken = [text for text, _voice in fake_tts.spoken]
        assert DISTRESS_ACK in spoken  # deterministic ack was spoken

    async def test_fires_mid_conversation_on_every_final_transcript(
        self,
        pipeline: VoicePipeline,
        bus: EventBus,
        brain: CountingBrain,
        dead_network: None,
    ) -> None:
        sub = bus.subscribe(topics.DISTRESS_HEARD)
        await pipeline.handle_text("good morning")
        await pipeline.handle_text("tell me about the weather")
        assert len(brain.calls) == 2  # normal turns reach the brain
        await pipeline.handle_text("I need helb")  # typo'd distress mid-chat
        event = await sub.get()
        assert event.payload["phrase"] == "i need help"
        assert len(brain.calls) == 2  # distress turn did NOT reach the brain

    async def test_distress_ack_is_deterministic(
        self, pipeline: VoicePipeline, fake_tts: FakeTTS, dead_network: None
    ) -> None:
        await pipeline.handle_text("help me")
        await pipeline.handle_text("emergency")
        acks = [t for t, _v in fake_tts.spoken if t == DISTRESS_ACK]
        assert len(acks) == 2  # same template every time — never generated


class TestStopDetector:
    @pytest.mark.parametrize(
        "utterance", ["stop", "stop talking", "be quiet", "that's enough", "shush"]
    )
    def test_stop_variants(self, utterance: str) -> None:
        assert StopDetector().check(utterance) is not None

    def test_chat_is_not_stop(self) -> None:
        assert StopDetector().check("tell me a story") is None
