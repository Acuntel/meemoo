"""Energy VAD + silence endpointer tests (pure python — no models)."""

from __future__ import annotations

import math

from meemoo.voice.audio_io import scale_pcm
from meemoo.voice.types import CHUNK_SAMPLES
from meemoo.voice.vad import EnergyVAD, SilenceEndpointer


def tone(amplitude: int, samples: int = CHUNK_SAMPLES) -> bytes:
    """A PCM16 sine chunk at the given amplitude."""
    return b"".join(
        int(amplitude * math.sin(2 * math.pi * 220 * i / 16_000)).to_bytes(
            2, "little", signed=True
        )
        for i in range(samples)
    )


SILENCE = b"\x00\x00" * CHUNK_SAMPLES
LOUD = tone(12_000)


class TestEnergyVAD:
    def test_silence_is_not_speech(self) -> None:
        vad = EnergyVAD()
        assert vad.is_speech(SILENCE) is False

    def test_loud_tone_is_speech(self) -> None:
        vad = EnergyVAD()
        assert vad.is_speech(LOUD) is True

    def test_adapts_noise_floor_without_losing_speech(self) -> None:
        vad = EnergyVAD()
        quiet_hum = tone(80)
        for _ in range(50):  # long quiet period raises the floor slightly
            assert vad.is_speech(quiet_hum) is False
        assert vad.is_speech(LOUD) is True  # real speech still clears it

    def test_empty_chunk_safe(self) -> None:
        assert EnergyVAD().is_speech(b"") is False


class TestSilenceEndpointer:
    def test_utterance_start_and_end(self) -> None:
        ep = SilenceEndpointer(min_speech_s=0.25, end_silence_s=1.0, chunk_s=0.032)
        started = ended = 0
        # ~0.5 s speech then ~1.2 s silence
        for _ in range(16):
            event = ep.feed(True)
            started += event.started
        for _ in range(40):
            event = ep.feed(False)
            ended += event.ended
        assert started == 1
        assert ended == 1
        assert ep.in_utterance is False

    def test_short_blip_does_not_start_utterance(self) -> None:
        ep = SilenceEndpointer(min_speech_s=0.25, end_silence_s=1.0, chunk_s=0.032)
        for _ in range(3):  # ~0.1 s — a door click, not speech
            assert ep.feed(True).started is False
        for _ in range(40):
            assert ep.feed(False).ended is False

    def test_elderly_pause_does_not_end_turn(self) -> None:
        ep = SilenceEndpointer(min_speech_s=0.25, end_silence_s=1.0, chunk_s=0.032)
        for _ in range(16):
            ep.feed(True)
        for _ in range(20):  # ~0.64 s pause — mid-thought, not end of turn
            assert ep.feed(False).ended is False
        for _ in range(10):  # speech resumes
            ep.feed(True)
        assert ep.in_utterance is True


class TestDucking:
    def test_scale_pcm_reduces_amplitude(self) -> None:
        ducked = scale_pcm(LOUD, 0.18)
        vad = EnergyVAD()
        assert vad.is_speech(LOUD) is True
        # -15 dB duck drops the same audio under the default speech gate
        assert max(abs(int.from_bytes(ducked[i : i + 2], "little", signed=True))
                   for i in range(0, len(ducked), 2)) < 12_000 * 0.2 + 2
