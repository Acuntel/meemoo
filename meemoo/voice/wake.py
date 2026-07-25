"""Wake triggers behind the :class:`meemoo.voice.types.WakeWord` interface.

v1 trigger is push-to-talk in the UI (TODO Phase 3); openWakeWord is the
optional dev-phase acoustic wake (research 02 §C). The production "Hey Meemoo"
microWakeWord model is a hardware-phase deliverable — budget 1–2 weeks of
training iteration per the maintainers' own warning.

The DISTRESS detector is architecturally separate from wake (Constitution
Art. IV §5) — nothing in this module may gate or swallow the word "help".
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PushToTalk:
    """Explicit trigger: UI button / Enter key. ``press()`` arms one wake."""

    name = "ptt"

    def __init__(self) -> None:
        self._armed = False

    def press(self) -> None:
        self._armed = True

    def process(self, pcm: bytes) -> bool:
        if self._armed:
            self._armed = False
            return True
        return False


class OpenWakeWord:
    """openWakeWord acoustic wake — optional dev-phase engine (lazy import).

    Uses a stock model until the custom "hey meemoo" model is trained
    (~20 min per candidate phrase per research 02 §C).
    """

    name = "openwakeword"

    def __init__(self, model_name: str = "hey_jarvis", threshold: float = 0.5) -> None:
        from openwakeword.model import Model  # lazy optional

        self._model = Model(wakeword_models=[model_name])
        self._key = model_name
        self._threshold = threshold
        logger.info("wake: openwakeword", extra={"fields": {"model": model_name}})

    def process(self, pcm: bytes) -> bool:
        import numpy as np

        audio = np.frombuffer(pcm, dtype=np.int16)
        scores = self._model.predict(audio)
        return float(scores.get(self._key, 0.0)) >= self._threshold


def create_wake() -> PushToTalk | OpenWakeWord:
    """openWakeWord if installed, else push-to-talk. Never crashes."""
    try:
        return OpenWakeWord()
    except (ImportError, OSError) as exc:
        logger.info(
            "openwakeword unavailable; push-to-talk is the wake trigger",
            extra={"fields": {"reason": str(exc)}},
        )
        return PushToTalk()
