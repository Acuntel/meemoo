"""STT implementations behind the :class:`meemoo.voice.types.STT` interface.

Primary: **Moonshine v2** (MIT) — beats Whisper-large-v3 at 1/6 the size and,
critically for this population, does not hallucinate text during silence
(long pauses are a defining feature of elderly speech — research 02 §A, §open
questions). Fallback: **faster-whisper small.en** (ports the restoration-one
service pattern: int8 CPU, VAD filter, beam 1 — the anti-hallucination
lessons from project_ptt_dictation).

Both engines are lazy optional deps (``uv sync --group voice``); the factory
degrades to ``None`` (text-input mode) rather than crashing (Art. IX §3).
"""

from __future__ import annotations

import logging

from meemoo.core.config import get_settings
from meemoo.voice.types import SAMPLE_RATE

logger = logging.getLogger(__name__)


def _pcm16_to_f32(pcm: bytes) -> object:
    """PCM16 bytes → float32 numpy array in [-1, 1] (numpy is an STT-tier dep)."""
    import numpy as np

    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


class MoonshineSTT:
    """Moonshine ONNX (usefulsensors) — primary engine.

    Install: ``pip install useful-moonshine-onnx@git+https://git@github.com/
    usefulsensors/moonshine.git#subdirectory=moonshine-onnx`` (not on PyPI at
    pin time — hence the lazy import and the honest fallback chain).
    """

    name = "moonshine"

    def __init__(self, model_name: str = "moonshine/base") -> None:
        from moonshine_onnx import MoonshineOnnxModel, load_tokenizer  # lazy optional

        self._model = MoonshineOnnxModel(model_name=model_name)
        self._tokenizer = load_tokenizer()
        logger.info("STT: moonshine", extra={"fields": {"model": model_name}})

    def transcribe(self, pcm: bytes) -> str:
        if not pcm:
            return ""
        audio = _pcm16_to_f32(pcm)
        tokens = self._model.generate(audio[None, :])  # type: ignore[index]
        text = self._tokenizer.decode_batch(tokens)[0]
        return str(text).strip()

    def partial(self, pcm: bytes) -> str | None:
        # Moonshine is fast enough to re-decode the utterance-so-far as the
        # streaming partial (v2 streaming API lands behind this same method).
        if len(pcm) < SAMPLE_RATE:  # <0.5 s of audio: not worth a partial
            return None
        return self.transcribe(pcm)


class FasterWhisperSTT:
    """faster-whisper small.en — the proven fallback (restoration-one pattern)."""

    name = "faster_whisper"

    def __init__(self, model_size: str = "small.en") -> None:
        from faster_whisper import WhisperModel  # lazy optional

        # int8 keeps the footprint small; research 02 warns against the
        # tiniest tier for elderly speech, so small.en is the floor here.
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("STT: faster-whisper", extra={"fields": {"model": model_size}})

    def transcribe(self, pcm: bytes) -> str:
        if not pcm:
            return ""
        audio = _pcm16_to_f32(pcm)
        segments, _info = self._model.transcribe(
            audio,
            language="en",
            vad_filter=True,  # drop silence → no hallucinated phantom text
            beam_size=1,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def partial(self, pcm: bytes) -> str | None:
        return None  # whisper re-decode is too slow to run as a live partial


def create_stt() -> MoonshineSTT | FasterWhisperSTT | None:
    """Best available engine per config; ``None`` = text-input-only mode."""
    choice = get_settings().voice_stt
    if choice == "off":
        logger.info("STT disabled by config", extra={"fields": {"engine": "off"}})
        return None
    if choice in ("auto", "moonshine"):
        try:
            return MoonshineSTT()
        except ImportError as exc:
            logger.info(
                "moonshine unavailable",
                extra={"fields": {"reason": str(exc), "fallback": "faster_whisper"}},
            )
            if choice == "moonshine":
                return None
    if choice in ("auto", "faster_whisper"):
        try:
            return FasterWhisperSTT()
        except ImportError as exc:
            logger.warning(
                "no STT engine available; voice runs in text mode "
                "(install with: uv sync --group voice)",
                extra={"fields": {"reason": str(exc)}},
            )
    return None
