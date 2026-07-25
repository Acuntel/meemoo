"""Voice test fixtures: fake stages so no model/download/hardware is needed."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from meemoo.core.bus import EventBus
from meemoo.voice.audio_io import BufferSource, CollectSink
from meemoo.voice.pipeline import VoicePipeline
from meemoo.voice.session import SessionManager
from meemoo.voice.types import SAMPLE_RATE
from meemoo.voice.vad import EnergyVAD, SilenceEndpointer


class FakeClock:
    """Deterministic monotonic clock the tests advance by hand."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class FakeSTT:
    """Returns queued transcripts regardless of audio content."""

    name = "fake"

    def __init__(self, texts: list[str] | None = None) -> None:
        self.texts = list(texts or [])
        self.calls: list[bytes] = []

    def transcribe(self, pcm: bytes) -> str:
        self.calls.append(pcm)
        return self.texts.pop(0) if self.texts else ""

    def partial(self, pcm: bytes) -> str | None:
        return None


class FakeTTS:
    """Yields a few small PCM chunks per call; records what was spoken."""

    name = "fake"
    sample_rate = SAMPLE_RATE

    def __init__(self, chunks_per_call: int = 3) -> None:
        self.spoken: list[tuple[str, str]] = []  # (text, voice_key)
        self.chunks_per_call = chunks_per_call

    def synthesize(self, text: str, voice_key: str) -> Iterator[bytes]:
        self.spoken.append((text, voice_key))
        for _ in range(self.chunks_per_call):
            yield b"\x01\x00" * 160


class CountingBrain:
    """A brain stub that counts invocations — proves the distress bypass."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, text: str) -> str:
        self.calls.append(text)
        return f"brain reply to: {text}"


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def fake_tts() -> FakeTTS:
    return FakeTTS()


@pytest.fixture
def brain() -> CountingBrain:
    return CountingBrain()


@pytest.fixture
def source() -> BufferSource:
    return BufferSource()


@pytest.fixture
def sink() -> CollectSink:
    return CollectSink()


@pytest.fixture
def pipeline(
    bus: EventBus,
    clock: FakeClock,
    fake_tts: FakeTTS,
    brain: CountingBrain,
    source: BufferSource,
    sink: CollectSink,
) -> VoicePipeline:
    sessions = SessionManager(bus, None, silence_close_s=45.0, clock=clock)
    return VoicePipeline(
        bus,
        source=source,
        sink=sink,
        stt=FakeSTT(),
        tts=fake_tts,
        vad=EnergyVAD(),
        sessions=sessions,
        brain=brain,
        endpointer=SilenceEndpointer(),
        clock=clock,
    )
