"""Voice-activity detection + end-of-turn endpointing.

Primary VAD: Silero (via the ONNX-only ``pysilero-vad`` — no torch), lazy and
optional. Fallback: a pure-python adaptive energy VAD so the pipeline (and
every test) runs with zero downloads. Endpointing: silence-duration state
machine now; smart-turn v3 (semantic endpointing, 12 ms CPU) is the planned
upgrade behind the same interface once its model download story is wired —
see research 02 §A.
"""

from __future__ import annotations

import array
import logging
import math
from dataclasses import dataclass

from meemoo.core.config import get_settings

logger = logging.getLogger(__name__)


class EnergyVAD:
    """Adaptive RMS energy gate — the always-works floor.

    Tracks a slow noise-floor estimate; a chunk is speech when its RMS clears
    ``ratio``× the floor (and an absolute minimum, so digital silence never
    triggers). Good enough to drive endpointing in quiet rooms and tests;
    Silero replaces it wherever installed.
    """

    name = "energy"

    def __init__(self, ratio: float = 3.0, min_rms: float = 250.0) -> None:
        self._ratio = ratio
        self._min_rms = min_rms
        self._floor = 100.0

    @staticmethod
    def _rms(pcm: bytes) -> float:
        samples = array.array("h")
        samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        if not samples:
            return 0.0
        return math.sqrt(sum(s * s for s in samples) / len(samples))

    def is_speech(self, pcm: bytes) -> bool:
        rms = self._rms(pcm)
        speech = rms >= max(self._min_rms, self._floor * self._ratio)
        if not speech:  # only quiet frames update the noise floor
            self._floor = 0.95 * self._floor + 0.05 * max(rms, 1.0)
        return speech


class SileroVAD:
    """Silero VAD via ``pysilero-vad`` (ONNX runtime, model bundled, no torch)."""

    name = "silero"

    def __init__(self, threshold: float = 0.5) -> None:
        from pysilero_vad import SileroVoiceActivityDetector  # lazy optional

        self._detector = SileroVoiceActivityDetector()
        self._threshold = threshold
        self._chunk_bytes = int(self._detector.chunk_bytes())

    def is_speech(self, pcm: bytes) -> bool:
        # Feed native-size windows; any speechy window makes the chunk speech.
        for off in range(0, len(pcm) - self._chunk_bytes + 1, self._chunk_bytes):
            if self._detector(pcm[off : off + self._chunk_bytes]) >= self._threshold:
                return True
        return False


@dataclass(frozen=True, slots=True)
class TurnEvent:
    """Endpointer output for one chunk: did an utterance start or end here?"""

    started: bool = False
    ended: bool = False


class SilenceEndpointer:
    """End-of-turn by trailing-silence duration, elderly-pause tolerant.

    ``end_silence_s`` is deliberately generous (research 02: long pauses are a
    defining feature of elderly speech — cutting people off is a worse failure
    than replying a beat late). smart-turn v3 will shrink this semantically.
    """

    def __init__(
        self,
        min_speech_s: float = 0.25,
        end_silence_s: float = 1.0,
        chunk_s: float = 0.032,
    ) -> None:
        self._min_speech_chunks = max(1, round(min_speech_s / chunk_s))
        self._end_silence_chunks = max(1, round(end_silence_s / chunk_s))
        self._speech_chunks = 0
        self._silence_chunks = 0
        self._in_utterance = False

    def feed(self, is_speech: bool) -> TurnEvent:
        """Advance one chunk; report utterance start/end transitions."""
        if is_speech:
            self._silence_chunks = 0
            self._speech_chunks += 1
            if not self._in_utterance and self._speech_chunks >= self._min_speech_chunks:
                self._in_utterance = True
                return TurnEvent(started=True)
            return TurnEvent()
        self._speech_chunks = 0
        if self._in_utterance:
            self._silence_chunks += 1
            if self._silence_chunks >= self._end_silence_chunks:
                self._in_utterance = False
                self._silence_chunks = 0
                return TurnEvent(ended=True)
        return TurnEvent()

    @property
    def in_utterance(self) -> bool:
        return self._in_utterance


def create_vad() -> EnergyVAD | SileroVAD:
    """Best available VAD per config; never crashes, always returns something."""
    choice = get_settings().voice_vad
    if choice in ("auto", "silero"):
        try:
            vad = SileroVAD()
            logger.info("VAD: silero", extra={"fields": {"engine": "silero"}})
            return vad
        except ImportError as exc:
            if choice == "silero":
                logger.warning(
                    "silero VAD requested but unavailable; falling back to energy",
                    extra={"fields": {"reason": str(exc)}},
                )
    logger.info("VAD: energy (pure python)", extra={"fields": {"engine": "energy"}})
    return EnergyVAD()
