"""Shared voice types + stage interfaces (Constitution Art. III §4).

One audio format flows through the whole pipeline: 16 kHz, mono, signed
16-bit little-endian PCM. Sources resample to it; TTS engines report their
own output rate and the sink handles it. Every stage sits behind a Protocol
so implementations (Moonshine vs faster-whisper, Pocket vs Piper, laptop mic
vs blimp satellite) swap without touching the pipeline.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

SAMPLE_RATE = 16_000  # Hz — pipeline-wide capture format
SAMPLE_WIDTH = 2  # bytes per sample (PCM16)
CHANNELS = 1
CHUNK_SAMPLES = 512  # 32 ms @ 16 kHz — Silero VAD's native window
CHUNK_BYTES = CHUNK_SAMPLES * SAMPLE_WIDTH


@dataclass(frozen=True, slots=True)
class AudioChunk:
    """One capture-side chunk of PCM16 mono @ ``SAMPLE_RATE``."""

    pcm: bytes
    t: float  # monotonic capture timestamp (seconds)


@dataclass(frozen=True, slots=True)
class Transcript:
    """STT output for one utterance (or a streaming partial of it)."""

    text: str
    final: bool
    t0: float  # utterance start (monotonic)
    t1: float  # utterance end / partial-emit time (monotonic)


@runtime_checkable
class AudioSource(Protocol):
    """Where mic audio comes from (laptop mic now; blimp satellite later)."""

    async def read(self) -> AudioChunk | None:
        """Next chunk, or ``None`` when the stream has ended."""
        ...

    def set_ducked(self, on: bool) -> None:
        """Partial ducking (-15 dB) while Meemoo speaks — never a full mute,
        so barge-in stays possible (research 02 §D.2)."""
        ...

    def close(self) -> None: ...


@runtime_checkable
class AudioSink(Protocol):
    """Where synthesized speech goes (laptop speaker now; satellite later)."""

    async def play(self, pcm: bytes, rate: int) -> None:
        """Play one PCM16 mono chunk at ``rate`` Hz. Returns when queued/written."""
        ...

    def stop(self) -> None:
        """Abort the current playback immediately (barge-in / 'stop')."""
        ...

    def close(self) -> None: ...


@runtime_checkable
class STT(Protocol):
    """Speech-to-text over one buffered utterance (PCM16 mono @ 16 kHz)."""

    name: str

    def transcribe(self, pcm: bytes) -> str:
        """Final transcription of a complete utterance."""
        ...

    def partial(self, pcm: bytes) -> str | None:
        """Cheap streaming partial for the utterance-so-far, or ``None`` if the
        engine has no streaming mode."""
        ...


@runtime_checkable
class TTS(Protocol):
    """Text-to-speech, streamed as PCM16 chunks at ``sample_rate``."""

    name: str
    sample_rate: int

    def synthesize(self, text: str, voice_key: str) -> Iterator[bytes]:
        """Yield PCM16 mono chunks; first chunk latency is the TTFA metric."""
        ...


@runtime_checkable
class VAD(Protocol):
    """Frame-level voice-activity decision on one ``CHUNK_BYTES`` chunk."""

    name: str

    def is_speech(self, pcm: bytes) -> bool: ...


@runtime_checkable
class WakeWord(Protocol):
    """Wake trigger. v1 = push-to-talk in the UI; openWakeWord optional."""

    name: str

    def process(self, pcm: bytes) -> bool:
        """True exactly when a wake event fires on this chunk."""
        ...
