"""End-to-end pipeline tests with fake stages: audio → text → reply → audio.

Covers the full loop, TTFA measurement, raw-audio deletion (Art. V §2),
ducking hooks, and stop/barge-in scaffolding.
"""

from __future__ import annotations

import logging

import pytest

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.voice.audio_io import BufferSource, CollectSink
from meemoo.voice.pipeline import VoicePipeline, templated_brain
from meemoo.voice.session import SessionManager
from meemoo.voice.types import CHUNK_BYTES
from meemoo.voice.vad import EnergyVAD, SilenceEndpointer

from .conftest import CountingBrain, FakeClock, FakeSTT, FakeTTS

LOUD = b"\x10\x27" * (CHUNK_BYTES // 2)  # constant 10000 amplitude — "speech"
SILENCE = b"\x00\x00" * (CHUNK_BYTES // 2)


def make_pipeline(
    bus: EventBus,
    clock: FakeClock,
    *,
    stt_texts: list[str],
    brain: CountingBrain,
) -> tuple[VoicePipeline, BufferSource, CollectSink, FakeSTT, FakeTTS]:
    source = BufferSource()
    sink = CollectSink()
    stt = FakeSTT(stt_texts)
    tts = FakeTTS()
    sessions = SessionManager(bus, None, clock=clock)
    pipeline = VoicePipeline(
        bus,
        source=source,
        sink=sink,
        stt=stt,
        tts=tts,
        vad=EnergyVAD(),
        sessions=sessions,
        brain=brain,
        endpointer=SilenceEndpointer(min_speech_s=0.25, end_silence_s=1.0),
        clock=clock,
    )
    return pipeline, source, sink, stt, tts


async def test_full_audio_loop(
    bus: EventBus, clock: FakeClock, brain: CountingBrain,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline, source, sink, stt, tts = make_pipeline(
        bus, clock, stt_texts=["good morning meemoo"], brain=brain
    )
    sub = bus.subscribe(topics.UTTERANCE_HEARD)
    # ~0.5 s of speech, then >1 s of silence closes the turn
    for _ in range(16):
        source.feed(LOUD)
    for _ in range(40):
        source.feed(SILENCE)
    source.end()
    with caplog.at_level(logging.INFO):
        await pipeline.run()

    assert stt.calls, "STT was handed the buffered utterance"
    assert brain.calls == ["good morning meemoo"]
    event = await sub.get()
    assert event.payload["transcript"] == "good morning meemoo"
    assert sink.chunks, "a reply was played"
    # gate metric: time-to-first-audio was measured and logged
    assert pipeline.last_ttfa_ms is not None
    assert any("time to first audio" in r.message for r in caplog.records)


async def test_raw_audio_discarded_after_transcription(
    bus: EventBus, clock: FakeClock, brain: CountingBrain,
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline, source, _sink, stt, _tts = make_pipeline(
        bus, clock, stt_texts=["hello"], brain=brain
    )
    for _ in range(16):
        source.feed(LOUD)
    for _ in range(40):
        source.feed(SILENCE)
    source.end()
    with caplog.at_level(logging.INFO):
        await pipeline.run()
    # the utterance buffer is empty the moment STT returned (Art. V §2)
    assert bytes(pipeline._utterance) == b""  # noqa: SLF001
    assert any("raw audio discarded" in r.message for r in caplog.records)
    assert stt.calls and len(stt.calls[0]) > 0  # STT really did get audio


async def test_ducking_wraps_playback(
    bus: EventBus, clock: FakeClock, brain: CountingBrain
) -> None:
    pipeline, source, _sink, _stt, _tts = make_pipeline(
        bus, clock, stt_texts=[], brain=brain
    )
    sub = bus.subscribe(topics.VOICE_SPEAKING)
    await pipeline.handle_text("hello meemoo")
    # duck ON before audio, OFF after — mic is never fully muted, just scaled
    assert source.duck_events[0] is True
    assert source.duck_events[-1] is False
    first = await sub.get()
    assert first.payload == {"on": True}


async def test_stop_phrase_halts_playback_only(
    bus: EventBus, clock: FakeClock, brain: CountingBrain
) -> None:
    pipeline, _source, sink, _stt, _tts = make_pipeline(
        bus, clock, stt_texts=[], brain=brain
    )
    sub = bus.subscribe(topics.STOP_HEARD)
    # simulate: Meemoo mid-monologue when "stop" arrives
    pipeline._speaking = True  # noqa: SLF001
    await pipeline.handle_text("stop")
    assert sink.stopped is True
    event = await sub.get()
    assert event.topic == topics.STOP_HEARD
    assert brain.calls == []  # "stop" is handled by the always-on detector


async def test_no_stt_engine_never_crashes(
    bus: EventBus, clock: FakeClock, brain: CountingBrain
) -> None:
    source = BufferSource()
    sessions = SessionManager(bus, None, clock=clock)
    pipeline = VoicePipeline(
        bus,
        source=source,
        sink=CollectSink(),
        stt=None,  # no engine installed — text mode
        tts=FakeTTS(),
        vad=EnergyVAD(),
        sessions=sessions,
        brain=brain,
    )
    for _ in range(16):
        source.feed(LOUD)
    for _ in range(40):
        source.feed(SILENCE)
    source.end()
    await pipeline.run()  # audio dropped with a log line; no exception
    assert brain.calls == []


def test_templated_brain_is_deterministic() -> None:
    assert templated_brain("hello") == templated_brain("hello")
    assert "morning" in templated_brain("good morning").lower()


async def test_session_reused_across_turns(
    bus: EventBus, clock: FakeClock, brain: CountingBrain
) -> None:
    pipeline, _source, _sink, _stt, tts = make_pipeline(
        bus, clock, stt_texts=[], brain=brain
    )
    await pipeline.handle_text("hello")
    session_a = pipeline.sessions.active
    await pipeline.handle_text("how are you")
    assert pipeline.sessions.active is session_a  # one session, rolling context
    assert session_a is not None
    roles = [m["role"] for m in session_a.context]
    assert roles.count("user") == 2
