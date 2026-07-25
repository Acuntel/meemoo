"""Floor-line + furniture-zone calibration with a learning phase.

Research 05 §A.2 — "this is the whole ballgame":
1. Floor line fit from confidently-UPRIGHT frames (ankle midpoint vs x).
2. Elevated-support zone grid learned from stable sits/lies (elevation ≥ 0.35).
3. Day-one YOLOv8n COCO bootstrap seeds the zone grid (see yolo_bootstrap.py).
4. Guided placement check — refuse to arm if the floor is not visible in the
   lower third of frame.
Ship a learning phase: reduced sensitivity for the first 7–14 days,
user-visible (Nobi does exactly this).
"""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field

from meemoo.perception.types import (
    L_ANKLE,
    R_ANKLE,
    Landmarks,
    SignalFrame,
)

logger = logging.getLogger(__name__)

GRID_N = 32  # zone grid resolution per axis
REST_ZONE_MIN_HITS = 5  # observations before a cell counts as a rest zone
DEFAULT_LEARNING_DAYS = 10.0  # within the researched 7–14 day band
_MAX_FLOOR_SAMPLES = 2000
_MIN_FLOOR_SAMPLES = 30
_UPRIGHT_MAX_ANGLE = 25.0
_STABLE_REST_MOTION = 0.05  # stable sit/lie accumulation gate


@dataclass(slots=True)
class FloorCalibration:
    """Least-squares fit of floor_y(x) = a·x + b from upright-frame ankle points."""

    a: float = 0.0
    b: float = 0.0
    fitted: bool = False
    samples: list[tuple[float, float, float]] = field(default_factory=list)  # (x, y_ankle, S)

    @classmethod
    def from_line(cls, a: float, b: float) -> FloorCalibration:
        return cls(a=a, b=b, fitted=True)

    def add_upright_sample(self, x: float, y_ankle: float, scale: float) -> None:
        if len(self.samples) >= _MAX_FLOOR_SAMPLES:
            self.samples.pop(0)
        self.samples.append((x, y_ankle, scale))
        if len(self.samples) >= _MIN_FLOOR_SAMPLES:
            self._fit()

    def _fit(self) -> None:
        xs = [s[0] for s in self.samples]
        ys = [s[1] for s in self.samples]
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        var_x = sum((x - mean_x) ** 2 for x in xs)
        if var_x < 1e-6:  # degenerate: person only seen at one column
            self.a, self.b = 0.0, mean_y
        else:
            self.a = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / var_x
            self.b = mean_y - self.a * mean_x
        self.fitted = True

    def floor_y(self, x: float) -> float:
        return self.a * x + self.b

    def scale_prior(self, y_ankle: float) -> float | None:
        """Median torso length observed near this depth (±0.1 in y_ankle)."""
        near = [s for (_, y, s) in self.samples if abs(y - y_ankle) < 0.1]
        return statistics.median(near) if near else None


@dataclass(slots=True)
class ZoneGrid:
    """Occupancy grid over (x, support_y): the learned bed/couch/chair map."""

    counts: list[list[int]] = field(
        default_factory=lambda: [[0] * GRID_N for _ in range(GRID_N)]
    )

    @staticmethod
    def _cell(v: float) -> int:
        return min(GRID_N - 1, max(0, int(v * GRID_N)))

    def add_rest_observation(self, x: float, y: float) -> None:
        self.counts[self._cell(x)][self._cell(y)] += 1

    def seed_rect(self, x0: float, x1: float, y0: float, y1: float) -> None:
        """Mark a rectangle as rest zone (YOLO bootstrap / fixture headers)."""
        for cx in range(self._cell(x0), self._cell(x1) + 1):
            for cy in range(self._cell(y0), self._cell(y1) + 1):
                self.counts[cx][cy] = max(self.counts[cx][cy], REST_ZONE_MIN_HITS)

    def is_rest_zone(self, x: float, y: float) -> bool:
        return self.counts[self._cell(x)][self._cell(y)] >= REST_ZONE_MIN_HITS


@dataclass(slots=True)
class CalibrationState:
    """Everything the perception pipeline knows about this room's geometry."""

    floor: FloorCalibration = field(default_factory=FloorCalibration)
    zones: ZoneGrid = field(default_factory=ZoneGrid)
    started_at: float = field(default_factory=time.time)
    learning_days: float = DEFAULT_LEARNING_DAYS
    furniture_elevation: float = 0.35

    def in_learning(self, now: float | None = None) -> bool:
        """Reduced-sensitivity learning phase, first 7–14 days (user-visible)."""
        now = time.time() if now is None else now
        return (now - self.started_at) < self.learning_days * 86400.0

    def can_arm(self) -> bool:
        """Guided placement check (§A.2.4): floor visible in the lower third."""
        if not self.floor.fitted:
            return False
        mean_floor = (self.floor.floor_y(0.2) + self.floor.floor_y(0.8)) / 2.0
        return mean_floor >= 2.0 / 3.0

    def observe(self, sig: SignalFrame, landmarks: Landmarks | None) -> None:
        """Learn from one frame: floor samples when upright, zones when resting."""
        if not sig.present or landmarks is None:
            return
        if sig.torso_angle < _UPRIGHT_MAX_ANGLE and sig.vis_frac > 0.6:
            la, ra = landmarks[L_ANKLE], landmarks[R_ANKLE]
            if la[3] > 0.5 and ra[3] > 0.5:
                self.floor.add_upright_sample(
                    (la[0] + ra[0]) / 2.0, (la[1] + ra[1]) / 2.0, sig.scale
                )
        elif (
            sig.elevation >= self.furniture_elevation
            and sig.motion_energy < _STABLE_REST_MOTION
        ):
            # stable sit/lie above the floor: this IS the furniture map, learned
            self.zones.add_rest_observation(sig.x, sig.support_y)

    def status_fields(self) -> dict[str, object]:
        return {
            "floor_fitted": self.floor.fitted,
            "floor_samples": len(self.floor.samples),
            "learning": self.in_learning(),
            "armable": self.can_arm(),
        }
