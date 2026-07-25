"""TTS implementations behind the :class:`meemoo.voice.types.TTS` interface.

Tier order (research 02 §A/§B): **Pocket TTS** (Kyutai, CC-BY-4.0, ~200 ms
first chunk on M-class CPUs) primary → **Piper** (MIT) always-works offline
floor → **NullTTS** (logs the line, emits timed silence) so headless dev and
CI keep honest timing paths. The Pocket-vs-Chatterbox side-by-side listening
hour is still owed (see voices.py ``verified`` flags).

All engines lazy/optional; the factory never crashes (Art. IX §3). Voice
characters come from :mod:`meemoo.voice.voices` — each engine maps the
character key to its own model/params.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from meemoo.core.config import get_settings
from meemoo.voice.types import SAMPLE_RATE
from meemoo.voice.voices import get_voice

logger = logging.getLogger(__name__)


class PocketTTS:
    """Pocket TTS (kyutai/pocket-tts) — primary engine, streamed chunks.

    API written against the published ``pocket_tts`` package; treated as
    unverified until the listening pass runs on real hardware (lazy import
    means a broken/renamed API degrades to Piper instead of crashing).
    """

    name = "pocket"
    sample_rate = 24_000

    def __init__(self) -> None:
        from pocket_tts import TTSModel  # lazy optional

        self._model = TTSModel.load()
        logger.info("TTS: pocket", extra={"fields": {"engine": "pocket"}})

    def synthesize(self, text: str, voice_key: str) -> Iterator[bytes]:
        import numpy as np

        spec = get_voice(voice_key)
        for chunk in self._model.stream(text, voice=spec.pocket_voice):
            audio = np.asarray(chunk, dtype=np.float32)
            yield (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()


class PiperTTS:
    """Piper (MIT) — the offline floor. Voices download once into
    ``settings.piper_voices_dir`` via ``python -m piper.download_voices <id>``."""

    name = "piper"
    sample_rate = 22_050  # per-voice; updated from the loaded model config

    def __init__(self) -> None:
        from piper import PiperVoice  # lazy optional

        self._piper_voice_cls = PiperVoice
        self._voices: dict[str, object] = {}
        self._dir = Path(get_settings().piper_voices_dir)
        logger.info("TTS: piper", extra={"fields": {"voices_dir": str(self._dir)}})

    def _load(self, model_id: str) -> object:
        cached = self._voices.get(model_id)
        if cached is not None:
            return cached
        path = self._dir / f"{model_id}.onnx"
        if not path.exists():
            raise FileNotFoundError(
                f"Piper voice missing: {path} — run: "
                f"uv run python -m piper.download_voices {model_id} "
                f"--data-dir {self._dir}"
            )
        voice = self._piper_voice_cls.load(str(path))
        self._voices[model_id] = voice
        self.sample_rate = int(voice.config.sample_rate)
        return voice

    def synthesize(self, text: str, voice_key: str) -> Iterator[bytes]:
        from piper import SynthesisConfig

        spec = get_voice(voice_key)
        voice = self._load(spec.piper_model)
        cfg = SynthesisConfig(length_scale=spec.piper_length_scale)
        for chunk in voice.synthesize(text, cfg):  # type: ignore[attr-defined]
            self.sample_rate = int(chunk.sample_rate)
            yield bytes(chunk.audio_int16_bytes)


class NullTTS:
    """Logs the spoken line and yields timed silence — the headless floor.

    Keeps every timing/ducking/barge-in path honest with zero dependencies:
    ~150 ms of silence per word approximates real speech duration.
    """

    name = "null"
    sample_rate = SAMPLE_RATE
    MS_PER_WORD = 150

    def synthesize(self, text: str, voice_key: str) -> Iterator[bytes]:
        spec = get_voice(voice_key)
        logger.info(
            "spoken (null-tts)",
            extra={"fields": {"voice": spec.key, "text": text}},
        )
        words = max(1, len(text.split()))
        samples_per_word = int(self.sample_rate * self.MS_PER_WORD / 1000)
        for _ in range(words):
            yield b"\x00\x00" * samples_per_word


def create_tts() -> PocketTTS | PiperTTS | NullTTS:
    """Best available engine per config; NullTTS is the never-crash floor."""
    choice = get_settings().voice_tts
    if choice in ("auto", "pocket"):
        try:
            return PocketTTS()
        except ImportError as exc:
            logger.info(
                "pocket-tts unavailable",
                extra={"fields": {"reason": str(exc), "fallback": "piper"}},
            )
    if choice in ("auto", "piper", "pocket"):
        try:
            return PiperTTS()
        except ImportError as exc:
            logger.warning(
                "piper unavailable; using null TTS "
                "(install with: uv sync --group voice)",
                extra={"fields": {"reason": str(exc)}},
            )
    logger.info("TTS: null (text logged, timed silence)", extra={"fields": {"engine": "null"}})
    return NullTTS()
