"""Audio I/O implementations: laptop mic/speaker now, fakes for tests.

``sounddevice`` is a lazy optional dependency (``uv sync --group voice``).
Missing audio hardware or a missing library must NEVER crash startup
(Constitution Art. IX §3) — the factories degrade to buffer/null endpoints
and log what happened. The blimp-satellite endpoints arrive later behind the
same interfaces, speaking the framed transport in :mod:`meemoo.voice.transport`.
"""

from __future__ import annotations

import array
import asyncio
import contextlib
import logging
import time
from typing import Any

from meemoo.voice.types import CHUNK_SAMPLES, SAMPLE_RATE, AudioChunk

logger = logging.getLogger(__name__)

DUCK_FACTOR = 0.18  # ≈ -15 dB — partial ducking, never a mute (research 02 §D.2)


def scale_pcm(pcm: bytes, factor: float) -> bytes:
    """Scale PCM16 samples by ``factor`` (pure stdlib; audioop is deprecated)."""
    samples = array.array("h")
    samples.frombytes(pcm)
    for i, s in enumerate(samples):
        samples[i] = max(-32768, min(32767, int(s * factor)))
    return samples.tobytes()


class BufferSource:
    """In-memory :class:`AudioSource` — tests and transport-fed audio."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self._ducked = False
        self.duck_events: list[bool] = []  # observable for tests

    def feed(self, pcm: bytes, t: float | None = None) -> None:
        chunk = AudioChunk(pcm=pcm, t=time.monotonic() if t is None else t)
        self._queue.put_nowait(chunk)

    def end(self) -> None:
        self._queue.put_nowait(None)

    async def read(self) -> AudioChunk | None:
        chunk = await self._queue.get()
        if chunk is not None and self._ducked:
            chunk = AudioChunk(pcm=scale_pcm(chunk.pcm, DUCK_FACTOR), t=chunk.t)
        return chunk

    def set_ducked(self, on: bool) -> None:
        self._ducked = on
        self.duck_events.append(on)

    def close(self) -> None:
        self.end()


class CollectSink:
    """In-memory :class:`AudioSink` — collects everything played (tests)."""

    def __init__(self) -> None:
        self.chunks: list[tuple[bytes, int]] = []
        self.stopped = False

    async def play(self, pcm: bytes, rate: int) -> None:
        if not self.stopped:
            self.chunks.append((pcm, rate))

    def stop(self) -> None:
        self.stopped = True

    def close(self) -> None:
        return None


class MicSource:
    """Laptop microphone via sounddevice; resamples handled by the driver."""

    def __init__(self, device: int | None = None) -> None:
        import sounddevice  # lazy — optional dependency

        self._loop = asyncio.get_event_loop()
        self._queue: asyncio.Queue[AudioChunk | None] = asyncio.Queue(maxsize=256)
        self._ducked = False

        def _callback(indata: Any, frames: int, timeinfo: Any, status: Any) -> None:
            pcm = bytes(indata)
            if self._ducked:
                pcm = scale_pcm(pcm, DUCK_FACTOR)
            chunk = AudioChunk(pcm=pcm, t=time.monotonic())
            with contextlib.suppress(RuntimeError):  # loop closed during shutdown
                self._loop.call_soon_threadsafe(self._queue.put_nowait, chunk)

        self._stream = sounddevice.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SAMPLES,
            channels=1,
            dtype="int16",
            device=device,
            callback=_callback,
        )
        self._stream.start()
        logger.info("mic open", extra={"fields": {"rate": SAMPLE_RATE, "device": device}})

    async def read(self) -> AudioChunk | None:
        return await self._queue.get()

    def set_ducked(self, on: bool) -> None:
        self._ducked = on

    def close(self) -> None:
        self._stream.stop()
        self._stream.close()
        self._queue.put_nowait(None)


class SpeakerSink:
    """Laptop speaker via sounddevice; one output stream per sample rate."""

    def __init__(self, device: int | None = None) -> None:
        import sounddevice

        self._sd = sounddevice
        self._device = device
        self._stream: Any = None
        self._stream_rate = 0
        self._abort = False

    def _ensure_stream(self, rate: int) -> Any:
        if self._stream is None or self._stream_rate != rate:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
            self._stream = self._sd.RawOutputStream(
                samplerate=rate, channels=1, dtype="int16", device=self._device
            )
            self._stream.start()
            self._stream_rate = rate
        return self._stream

    async def play(self, pcm: bytes, rate: int) -> None:
        if self._abort:
            return
        stream = self._ensure_stream(rate)
        # RawOutputStream.write blocks until buffered — run off the event loop.
        await asyncio.to_thread(stream.write, pcm)

    def stop(self) -> None:
        self._abort = True
        if self._stream is not None:
            self._stream.abort()
        self._abort = False

    def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class NullSink:
    """Discards audio but tracks how much 'played' — headless dev floor."""

    def __init__(self) -> None:
        self.bytes_played = 0

    async def play(self, pcm: bytes, rate: int) -> None:
        self.bytes_played += len(pcm)

    def stop(self) -> None:
        return None

    def close(self) -> None:
        return None


def create_mic() -> MicSource | None:
    """Best-available microphone source; ``None`` (with a log) if unavailable."""
    try:
        return MicSource()
    except (ImportError, OSError) as exc:
        logger.warning("no microphone available; voice runs in text mode",
                       extra={"fields": {"reason": str(exc)}})
        return None


def create_speaker() -> SpeakerSink | NullSink:
    """Best-available speaker sink; NullSink keeps timing paths honest headless."""
    try:
        return SpeakerSink()
    except (ImportError, OSError) as exc:
        logger.warning("no speaker available; audio discarded",
                       extra={"fields": {"reason": str(exc)}})
        return NullSink()
