"""The three voice characters — Constitution Art. VII §4.

Warm older man ("Morgan-Freeman-like" energy, not an imitation), a child
voice, and a female voice, selectable per device. Each character maps to
concrete engine parameters for every TTS tier so the character survives
graceful degradation (Art. III's "the voice never changes" principle applies
per-tier: a device keeps ITS character on whichever engine is running).

``verified=False`` marks picks that still need the human side-by-side
listening pass (Pocket vs Chatterbox, one hour, per step-03) — the IDs are
committed so the pipeline is runnable, the ears come later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VoiceSpec:
    """One selectable character, mapped onto every engine tier."""

    key: str
    label: str
    description: str
    # Pocket TTS (primary) — predefined-voice name; needs the listening pass.
    pocket_voice: str
    # Piper (offline floor) — voice model id for `python -m piper.download_voices`.
    piper_model: str
    piper_length_scale: float  # >1 = slower/warmer, <1 = quicker/lighter
    verified: bool  # True once a human has actually listened and approved


VOICES: dict[str, VoiceSpec] = {
    "elder_male": VoiceSpec(
        key="elder_male",
        label="Warm older man",
        description="Slow, warm, grandfatherly. The default companion voice.",
        pocket_voice="alistair",  # candidate; confirm in the listening pass
        piper_model="en_GB-alan-medium",
        piper_length_scale=1.1,  # a touch slower = warmer, easier for presbycusis
        verified=False,
    ),
    "child": VoiceSpec(
        key="child",
        label="Child",
        description="Bright, small, playful. The 'grandkid' character.",
        pocket_voice="pip",  # candidate; confirm in the listening pass
        # Piper ships no true child voice; amy at a quicker cadence is the
        # committed floor approximation until the Pocket listening pass.
        piper_model="en_US-amy-medium",
        piper_length_scale=0.85,
        verified=False,
    ),
    "female": VoiceSpec(
        key="female",
        label="Warm female",
        description="Calm, kind, unhurried. The 'daughter/nurse' register.",
        pocket_voice="marianne",  # candidate; confirm in the listening pass
        piper_model="en_US-lessac-medium",
        piper_length_scale=1.05,
        verified=False,
    ),
}

DEFAULT_VOICE = "elder_male"


def get_voice(key: str) -> VoiceSpec:
    """Voice by key, falling back to the default (never crashes on bad config)."""
    spec = VOICES.get(key)
    if spec is None:
        logger.warning(
            "unknown voice character; using default",
            extra={"fields": {"requested": key, "default": DEFAULT_VOICE}},
        )
        return VOICES[DEFAULT_VOICE]
    return spec
