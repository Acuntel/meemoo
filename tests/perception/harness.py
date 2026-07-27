"""Shared helpers: replay a landmark clip through signals + state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from meemoo.perception.calibration import FloorCalibration, ZoneGrid
from meemoo.perception.landmarks_io import LandmarkClip, load_clip
from meemoo.perception.signals import SignalExtractor
from meemoo.perception.state_machine import FallStateMachine
from meemoo.perception.thresholds import Thresholds, load_thresholds
from meemoo.perception.types import SignalFrame

FIXTURES = Path(__file__).parents[1] / "fixtures"
SYNTHETIC_DIR = FIXTURES / "landmarks" / "synthetic"
REAL_DIR = FIXTURES / "landmarks" / "real"


def synthetic_clips() -> list[Path]:
    return sorted(SYNTHETIC_DIR.glob("*.jsonl"))


def real_clips() -> list[Path]:
    """Committed GMDCSA-24 + CaucaFall landmark fixtures (the primary suite)."""
    return sorted(REAL_DIR.rglob("*.jsonl"))


@dataclass(slots=True)
class ClipRun:
    clip: LandmarkClip
    machine: FallStateMachine
    events: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def named(self, name: str) -> list[dict[str, object]]:
        return [payload for (n, payload) in self.events if n == name]

    @property
    def candidates(self) -> list[dict[str, object]]:
        return self.named("candidate.fall")


def run_clip(
    path: Path,
    thresholds: Thresholds | None = None,
    learning: bool = False,
) -> ClipRun:
    """Replay one committed clip; calibration comes from the clip header."""
    clip = load_clip(path)
    a, b = clip.floor_line()
    floor = FloorCalibration.from_line(a, b)
    zones = ZoneGrid()
    for x0, x1, y0, y1 in clip.rest_zones():
        zones.seed_rect(x0, x1, y0, y1)
    th = thresholds or load_thresholds()
    events: list[tuple[str, dict[str, object]]] = []
    machine = FallStateMachine(
        th,
        zones,
        on_event=lambda name, payload: events.append((name, payload)),
        learning=lambda: learning,
    )
    extractor = SignalExtractor(floor)
    for frame in clip.frames:
        machine.tick(extractor.update(frame))
    return ClipRun(clip=clip, machine=machine, events=events)


def sf(t: float, **kw: float | bool) -> SignalFrame:
    """Hand-built SignalFrame with sane upright defaults (unit tests)."""
    defaults: dict[str, float | bool] = {
        "present": True,
        "x": 0.5,
        "hip_y": 0.6,
        "torso_angle": 5.0,
        "support_y": 0.75,
        "elevation": 0.9,
        "v_descent": 0.0,
        "motion_energy": 0.01,
        "vis_frac": 1.0,
        "aspect": 3.0,
        "scale": 0.17,
    }
    defaults.update(kw)
    return SignalFrame(t=t, **defaults)  # type: ignore[arg-type]
