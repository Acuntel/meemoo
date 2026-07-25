"""IDLE-tier motion gate: 3 fps grayscale frame-diff (research 05 §F.3).

Cost target: <1 ms/frame at 160x120 → ~0.3% of one core. Pure-Python over
``bytes`` so it is dependency-free and hermetically testable; the live
pipeline hands it downscaled grayscale frames.

CRITICAL subtlety (§F.3): the gate must NEVER be the only path into the state
machine. A fallen person lying still generates no motion — once a person has
been seen, pose keeps running until they are confirmed upright-and-gone. That
rule lives in the pipeline tier logic (see pipeline.next_tier), not here.
"""

from __future__ import annotations

DEFAULT_PIXEL_DELTA = 18  # 0-255 grayscale delta that counts as changed
DEFAULT_TRIGGER_FRAC = 0.02  # fraction of changed pixels that trips the gate


class MotionGate:
    """Frame-diff motion detector over small grayscale frames."""

    def __init__(
        self,
        pixel_delta: int = DEFAULT_PIXEL_DELTA,
        trigger_frac: float = DEFAULT_TRIGGER_FRAC,
    ) -> None:
        self._pixel_delta = pixel_delta
        self._trigger_frac = trigger_frac
        self._prev: bytes | None = None

    def reset(self) -> None:
        self._prev = None

    def update(self, gray: bytes) -> float:
        """Feed one grayscale frame; returns the changed-pixel fraction [0, 1]."""
        prev = self._prev
        self._prev = gray
        if prev is None or len(prev) != len(gray) or not gray:
            return 0.0
        delta = self._pixel_delta
        changed = sum(1 for a, b in zip(prev, gray, strict=True) if abs(a - b) > delta)
        return changed / len(gray)

    def triggered(self, gray: bytes) -> bool:
        """True if this frame's motion fraction crosses the trigger threshold."""
        return self.update(gray) >= self._trigger_frac
