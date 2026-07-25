"""Episode trackers for the fall state machine: rolling kinematic evidence.

Keeps the short history the machine consults every tick — descent-velocity
peaks, windowed hip drops, stillness/settle clocks, and the LONG_LIE
persistence clock (with noise hysteresis). Split from state_machine.py to
keep both under the 300-line law (Constitution Art. IX §1).
"""

from __future__ import annotations

from collections import deque

from meemoo.perception.thresholds import Thresholds
from meemoo.perception.types import SignalFrame

WINDOW_S = 3.0  # rolling window for v_peak / hip-drop episode aggregates
SETTLE_MAX_V = 0.3


class EpisodeTrackers:
    """Rolling per-episode evidence; feed every present SignalFrame."""

    def __init__(self, th: Thresholds) -> None:
        self._th = th
        self._vh: deque[tuple[float, float]] = deque()  # (t, v_descent)
        self._hip: deque[tuple[float, float, float]] = deque()  # (t, hip_y, S)
        self.still_since: float | None = None
        self.settle_since: float | None = None
        self._longlie_since: float | None = None

    def update(self, sig: SignalFrame) -> None:
        self._vh.append((sig.t, sig.v_descent))
        self._hip.append((sig.t, sig.hip_y, sig.scale))
        for dq in (self._vh, self._hip):
            while dq and sig.t - dq[0][0] > WINDOW_S + 1.0:
                dq.popleft()
        if sig.motion_energy < self._th.still_motion:
            self.still_since = self.still_since or sig.t
        else:
            self.still_since = None
        settled = abs(sig.v_descent) < SETTLE_MAX_V and (
            sig.motion_energy < self._th.purposeful_motion
        )
        if settled:
            self.settle_since = self.settle_since or sig.t
        else:
            self.settle_since = None

    def v_peak(self, now: float, window: float = WINDOW_S) -> float:
        return max((v for (t, v) in self._vh if now - t <= window), default=0.0)

    def hip_drop(self, now: float, window: float = WINDOW_S) -> float:
        """Max hip drop (torso-lengths) across any ~0.8 s span in the window."""
        pts = [(t, y, s) for (t, y, s) in self._hip if now - t <= window]
        best = 0.0
        for i, (t1, y1, s1) in enumerate(pts):
            for t0, y0, _s0 in pts[:i]:
                if 0.0 < t1 - t0 <= 0.8:
                    best = max(best, (y1 - y0) / max(s1, 1e-3))
        return best

    def still_duration(self, now: float) -> float:
        return (now - self.still_since) if self.still_since is not None else 0.0

    def longlie_duration(self, sig: SignalFrame, posture_ok: bool) -> float:
        """LONG_LIE persistence clock with hysteresis: STARTS on stillness
        (< STILL_MOTION) but only RESETS on purposeful motion — single noise
        frames in the mid-band must not wipe 90 s of persistence evidence
        (persistence is the recall engine)."""
        if not posture_ok or sig.motion_energy > self._th.purposeful_motion:
            self._longlie_since = None
            return 0.0
        if self._longlie_since is None:
            if sig.motion_energy < self._th.still_motion:
                self._longlie_since = sig.t
            return 0.0
        return sig.t - self._longlie_since
