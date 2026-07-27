"""Voice motion commands (Amendment A5) — where they sit in the safety ladder.

Distress still outranks every motion command (Art. IV §4), "stop" outranks
everything else including the brain, and a capability decline publishes
nothing at all.
"""

from __future__ import annotations

import socket

import pytest

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.flight.capabilities import MotionKind
from meemoo.voice.audio_io import BufferSource, CollectSink
from meemoo.voice.pipeline import VoicePipeline
from meemoo.voice.session import SessionManager
from meemoo.voice.vad import EnergyVAD, SilenceEndpointer

from .conftest import CountingBrain, FakeClock, FakeSTT, FakeTTS

PINS: dict[str, tuple[float, float]] = {
    "kitchen": (5.0, 1.5),
    "living room": (2.0, 2.0),
    "Ruth's chair": (6.6, 4.6),
}


def pins() -> dict[str, tuple[float, float]]:
    return PINS


@pytest.fixture
def dead_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted in the motion path")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse)


@pytest.fixture
def motion_pipeline(
    bus: EventBus, clock: FakeClock, fake_tts: FakeTTS, brain: CountingBrain
) -> VoicePipeline:
    """A pipeline that knows the same named pins the onboarding wizard drops."""
    return VoicePipeline(
        bus,
        source=BufferSource(),
        sink=CollectSink(),
        stt=FakeSTT(),
        tts=fake_tts,
        vad=EnergyVAD(),
        sessions=SessionManager(bus, None, silence_close_s=45.0, clock=clock),
        brain=brain,
        endpointer=SilenceEndpointer(),
        clock=clock,
        pins=pins,
    )


class TestPipelinePriority:
    async def test_command_publishes_a_flight_event(
        self, motion_pipeline: VoicePipeline, bus: EventBus, brain: CountingBrain
    ) -> None:
        sub = bus.subscribe(topics.FLIGHT_COMMAND, replay_last=False)
        await motion_pipeline.handle_text("go to the kitchen")

        event = await sub.get()
        assert event.payload["command"] == MotionKind.GOTO.value
        assert event.payload["label"] == "kitchen"
        assert (event.payload["x"], event.payload["y"]) == (5.0, 1.5)
        assert event.payload["source"] == "voice"
        assert brain.calls == []  # motion never goes to the brain

    async def test_decline_publishes_nothing(
        self, motion_pipeline: VoicePipeline, bus: EventBus,
        brain: CountingBrain, fake_tts: FakeTTS,
    ) -> None:
        await motion_pipeline.handle_text("do a barrel roll")
        assert bus.last(topics.FLIGHT_COMMAND) is None  # the aircraft never heard it
        assert brain.calls == []
        spoken = [text for text, _voice in fake_tts.spoken]
        assert "I can't do a roll, but I can do a spin." in spoken

    async def test_distress_still_outranks_every_motion_command(
        self, motion_pipeline: VoicePipeline, bus: EventBus, dead_network: None
    ) -> None:
        """Art. IV §4: nothing gets in front of the distress bypass."""
        sub = bus.subscribe(topics.DISTRESS_HEARD, replay_last=False)
        # a distress phrase that also carries motion words
        await motion_pipeline.handle_text("help me, I can't get up, come here")

        event = await sub.get()
        assert event.topic == topics.DISTRESS_HEARD
        assert bus.last(topics.FLIGHT_COMMAND) is None  # escalation, not a flight

    async def test_stop_outranks_the_brain_and_fires_offline(
        self, motion_pipeline: VoicePipeline, bus: EventBus,
        brain: CountingBrain, dead_network: None,
    ) -> None:
        sub = bus.subscribe(topics.FLIGHT_COMMAND, replay_last=False)
        await motion_pipeline.handle_text("stop moving")

        event = await sub.get()
        assert event.payload["command"] == MotionKind.STOP.value
        assert brain.calls == []

    async def test_stop_while_speaking_halts_playback_and_the_aircraft(
        self, motion_pipeline: VoicePipeline, bus: EventBus
    ) -> None:
        """Barge-in must not delay a stop: mid-sentence, both halt (A5)."""
        stop_sub = bus.subscribe(topics.STOP_HEARD, replay_last=False)
        flight_sub = bus.subscribe(topics.FLIGHT_COMMAND, replay_last=False)
        motion_pipeline._speaking = True  # noqa: SLF001 — mid-monologue
        await motion_pipeline.handle_text("stop")

        assert (await stop_sub.get()).topic == topics.STOP_HEARD
        assert (await flight_sub.get()).payload["command"] == MotionKind.STOP.value

    async def test_be_quiet_stops_the_mouth_but_not_the_aircraft(
        self, motion_pipeline: VoicePipeline, bus: EventBus
    ) -> None:
        """"Be quiet" is about the voice; it must not ground the blimp."""
        motion_pipeline._speaking = True  # noqa: SLF001
        await motion_pipeline.handle_text("be quiet")
        assert bus.last(topics.STOP_HEARD) is not None
        assert bus.last(topics.FLIGHT_COMMAND) is None

    async def test_motion_reply_is_spoken_and_kept_in_the_transcript(
        self, motion_pipeline: VoicePipeline, fake_tts: FakeTTS
    ) -> None:
        await motion_pipeline.handle_text("go left")
        spoken = [text for text, _voice in fake_tts.spoken]
        assert "Okay, drifting to my left." in spoken
        session = motion_pipeline.sessions.active
        assert session is not None
        assert session.context[-1]["content"] == "Okay, drifting to my left."

    async def test_pins_are_read_late_so_setup_edits_take_effect(
        self, bus: EventBus, clock: FakeClock, brain: CountingBrain
    ) -> None:
        """A pin dropped after boot is reachable without a restart (A6)."""
        book: dict[str, tuple[float, float]] = {}
        pipeline = VoicePipeline(
            bus, source=BufferSource(), sink=CollectSink(), stt=FakeSTT(),
            tts=FakeTTS(), vad=EnergyVAD(),
            sessions=SessionManager(bus, None, clock=clock),
            brain=brain, clock=clock, pins=lambda: book,
        )
        await pipeline.handle_text("go to the porch")
        assert bus.last(topics.FLIGHT_COMMAND) is None  # unknown place: declined

        book["porch"] = (7.0, 0.5)  # the owner drops a pin in setup
        await pipeline.handle_text("go to the porch")
        last = bus.last(topics.FLIGHT_COMMAND)
        assert last is not None and last.payload["label"] == "porch"
