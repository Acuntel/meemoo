"""Signal extraction: pose landmarks → torso-length-normalized signals.

Research 05 §A.1. Everything is normalized by S = running median of the
shoulder-hip distance ("torso length"), which stays visible when legs are
occluded by furniture — the dominant occlusion case.

Noise handling: raw per-frame landmark jitter would swamp the STILL_MOTION
threshold (0.02 torso-lengths/sec), so `motion_energy` and `v_descent` are
computed from windowed **median positions** compared across a time baseline
(median-filtering per §A.1) rather than raw frame-to-frame deltas.
"""

from __future__ import annotations

import math
import statistics
from collections import deque

from meemoo.perception.types import (
    L_HIP,
    L_SHOULDER,
    N_LANDMARKS,
    R_HIP,
    R_SHOULDER,
    SUPPORT_LANDMARKS,
    FloorOracle,
    Landmarks,
    PoseFrame,
    SignalFrame,
)

VIS_THRESHOLD = 0.5
_HISTORY_S = 2.0  # seconds of landmark history kept for windowed medians
_MOTION_BASELINE_S = 0.5  # motion energy compares medians at least this far apart
_V_BASELINE_S = 0.2  # v_descent baseline
_MOTION_K = 5  # frames per median window (fps-adaptive: counts, not seconds)
_V_K = 3
_SCALE_SAMPLES = 300


def _mid(lm: Landmarks, a: int, b: int) -> tuple[float, float]:
    return ((lm[a][0] + lm[b][0]) / 2.0, (lm[a][1] + lm[b][1]) / 2.0)


def _visible(lm: Landmarks, idx: int) -> bool:
    return lm[idx][3] > VIS_THRESHOLD


class SignalExtractor:
    """Stateful per-person signal extractor. Feed frames in time order."""

    def __init__(self, floor: FloorOracle, default_floor_y: float = 0.95) -> None:
        self._floor = floor
        self._default_floor_y = default_floor_y
        self._scale_samples: deque[float] = deque(maxlen=_SCALE_SAMPLES)
        self._history: deque[tuple[float, Landmarks]] = deque()
        self._scale = 0.17  # sane prior until the running median warms up

    @property
    def scale(self) -> float:
        return self._scale

    def reset_motion_history(self) -> None:
        """Drop the landmark history (e.g. after a tracking gap)."""
        self._history.clear()

    def update(self, frame: PoseFrame) -> SignalFrame:
        """Compute the signal vector for one pose frame."""
        lm = frame.landmarks
        if lm is None:
            return SignalFrame.absent(frame.t)

        self._history.append((frame.t, lm))
        while self._history and frame.t - self._history[0][0] > _HISTORY_S:
            self._history.popleft()

        sx, sy = _mid(lm, L_SHOULDER, R_SHOULDER)
        hx, hy = _mid(lm, L_HIP, R_HIP)
        torso_vis = all(_visible(lm, i) for i in (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP))
        torso_len = math.hypot(sx - hx, sy - hy)
        if torso_vis and torso_len > 1e-4:
            self._scale_samples.append(torso_len)
            self._scale = statistics.median(self._scale_samples)
        s = max(self._scale, 1e-3)

        # torso_angle: angle between (mid_shoulder - mid_hip) and image vertical
        torso_angle = math.degrees(math.atan2(abs(sx - hx), abs(sy - hy)))

        # support_y: the body's lowest visible point among hip/shoulder/knee
        support_ys = [lm[i][1] for i in SUPPORT_LANDMARKS if _visible(lm, i)]
        support_y = max(support_ys) if support_ys else hy

        floor_y = self._floor.floor_y(hx) if self._floor.fitted else self._default_floor_y
        elevation = (floor_y - support_y) / s

        v_descent = self._windowed_velocity(frame.t, s)
        motion_energy = self._motion_energy(frame.t, s)

        vis_frac = sum(1 for p in lm if p[3] > VIS_THRESHOLD) / N_LANDMARKS

        xs = [p[0] for p in lm if p[3] > VIS_THRESHOLD]
        ys = [p[1] for p in lm if p[3] > VIS_THRESHOLD]
        if len(xs) >= 2:
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            aspect = h / max(w, 1e-4)
        else:
            aspect = 1.0

        return SignalFrame(
            t=frame.t,
            present=True,
            x=hx,
            hip_y=hy,
            torso_angle=torso_angle,
            support_y=support_y,
            elevation=elevation,
            v_descent=v_descent,
            motion_energy=motion_energy,
            vis_frac=vis_frac,
            aspect=aspect,
            scale=s,
        )

    # ------------------------------------------------------------------ internals
    # Median windows are FRAME-COUNT based so they stay robust at any fps
    # (a 0.2 s time window is a single frame at 5 fps — noise would swamp the
    # STILL_MOTION threshold). Kepler-style low-rate operation must still work.

    def _recent(self, k: int) -> list[tuple[float, Landmarks]]:
        return list(self._history)[-k:]

    def _past(self, now: float, min_age: float, k: int) -> list[tuple[float, Landmarks]]:
        older = [(t, lm) for (t, lm) in self._history if t <= now - min_age]
        return older[-k:]

    @staticmethod
    def _median_t_hip(frames: list[tuple[float, Landmarks]]) -> tuple[float, float]:
        ts = [t for (t, _) in frames]
        hys = [_mid(lm, L_HIP, R_HIP)[1] for (_, lm) in frames]
        return statistics.median(ts), statistics.median(hys)

    def _windowed_velocity(self, now: float, s: float) -> float:
        """Δ(median hip_y)/Δt/S across a ≥0.2 s baseline (positive = down)."""
        recent = self._recent(_V_K)
        past = self._past(now, _V_BASELINE_S, _V_K)
        if not recent or not past:
            return 0.0
        t_r, hy_r = self._median_t_hip(recent)
        t_p, hy_p = self._median_t_hip(past)
        if t_r - t_p < 1e-3:
            return 0.0
        return (hy_r - hy_p) / (t_r - t_p) / s

    def _motion_energy(self, now: float, s: float) -> float:
        """Mean landmark displacement between median windows ≥0.5 s apart, /S/Δt."""
        recent = self._recent(_MOTION_K)
        past = self._past(now, _MOTION_BASELINE_S, _MOTION_K)
        if not recent or not past:
            return 0.0
        t_r = statistics.median(t for (t, _) in recent)
        t_p = statistics.median(t for (t, _) in past)
        dt = t_r - t_p
        if dt < 1e-3:
            return 0.0
        total = 0.0
        for i in range(N_LANDMARKS):
            rx = statistics.median(lm[i][0] for (_, lm) in recent)
            ry = statistics.median(lm[i][1] for (_, lm) in recent)
            px = statistics.median(lm[i][0] for (_, lm) in past)
            py = statistics.median(lm[i][1] for (_, lm) in past)
            total += math.hypot(rx - px, ry - py)
        return (total / N_LANDMARKS) / (s * dt)
