"""Compile keyframe segments into landmark PoseFrames for one clip."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from meemoo.perception.types import PoseFrame
from tests.fixtures.synth.body import FLOOR_Y, Template, blend, make_frame


@dataclass(slots=True)
class Seg:
    """Interpolate from the previous segment's end state to this target."""

    dur: float
    pose: Template
    support: float = FLOOR_Y
    hip_x: float = 0.5
    direction: int = 1
    ease: str = "linear"  # "accel" = quadratic-in (falls accelerate)
    swing: float = 0.0  # gait limb swing amplitude (torso units)
    sway: float = 0.0  # purposeful whole-body movement (image units)
    absent: bool = False  # emit lm=None frames (person out of frame)
    hold: bool = False  # no interpolation: hold this segment's own targets


@dataclass(slots=True)
class ClipSpec:
    name: str
    fps: float
    label: str  # fall | adl | recovery
    segments: list[Seg]
    expect: dict[str, Any]
    seed: int = 7
    jitter: float = 0.0015
    vis_base: float = 0.95
    vis_sigma: float = 0.02
    occlude_legs: bool = False
    rest_zones: list[tuple[float, float, float, float]] | None = None
    t_impact: float | None = None
    notes: str = ""


def _ease(u: float, kind: str) -> float:
    return u * u if kind == "accel" else u


def compile_clip(spec: ClipSpec) -> tuple[dict[str, Any], list[PoseFrame]]:
    """Build (header, frames) for a clip spec. Deterministic per seed."""
    rng = random.Random(spec.seed)
    frames: list[PoseFrame] = []
    dt = 1.0 / spec.fps
    t = 0.0
    first = spec.segments[0]
    prev_pose, prev_support, prev_x = first.pose, first.support, first.hip_x
    for seg in spec.segments:
        n = max(1, round(seg.dur * spec.fps))
        for k in range(n):
            t += dt
            u = _ease((k + 1) / n, seg.ease)
            if seg.hold:
                u = 1.0
            if seg.absent:
                frames.append(PoseFrame(t=t, landmarks=None))
                continue
            pose = blend(prev_pose, seg.pose, u)
            support = prev_support + (seg.support - prev_support) * u
            hip_x = prev_x + (seg.hip_x - prev_x) * u
            lm = make_frame(
                pose,
                hip_x,
                support,
                seg.direction,
                rng,
                t,
                jitter=spec.jitter,
                vis_base=spec.vis_base,
                vis_sigma=spec.vis_sigma,
                swing=seg.swing,
                sway=seg.sway,
                occlude_legs=spec.occlude_legs,
            )
            frames.append(PoseFrame(t=t, landmarks=lm))
        prev_pose, prev_support, prev_x = seg.pose, seg.support, seg.hip_x
    header: dict[str, Any] = {
        "clip": spec.name,
        "fps": spec.fps,
        "source": "synthetic",
        "generator": "tests/fixtures/generate_synthetic.py",
        "label": spec.label,
        "floor_line": [0.0, FLOOR_Y],
        "rest_zones": [list(z) for z in (spec.rest_zones or [])],
        "expect": spec.expect,
        "seed": spec.seed,
    }
    if spec.t_impact is not None:
        header["t_impact"] = spec.t_impact
    if spec.notes:
        header["notes"] = spec.notes
    return header, frames
