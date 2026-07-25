"""Signal extraction: torso normalization, angles, elevation, velocity, motion."""

from __future__ import annotations

import random

from meemoo.perception.calibration import FloorCalibration
from meemoo.perception.signals import SignalExtractor
from meemoo.perception.types import PoseFrame, SignalFrame
from tests.fixtures.synth.body import FLOOR_Y, LIE, STAND, S, make_frame

FLOOR = FloorCalibration.from_line(0.0, FLOOR_Y)


def _frames(
    template: dict[int, tuple[float, float]],
    n: int,
    fps: float = 15.0,
    support: float = FLOOR_Y,
    jitter: float = 0.0005,
    sway: float = 0.0,
    occlude_legs: bool = False,
    support_drift: float = 0.0,
) -> list[PoseFrame]:
    rng = random.Random(3)
    out: list[PoseFrame] = []
    for i in range(n):
        t = (i + 1) / fps
        lm = make_frame(
            template,
            0.5,
            support + support_drift * t,
            1,
            rng,
            t,
            jitter=jitter,
            sway=sway,
            occlude_legs=occlude_legs,
        )
        out.append(PoseFrame(t=t, landmarks=lm))
    return out


def _run(frames: list[PoseFrame]) -> list[SignalFrame]:
    ex = SignalExtractor(FLOOR)
    return [ex.update(f) for f in frames]


def test_standing_signals() -> None:
    sigs = _run(_frames(STAND, 30))
    last = sigs[-1]
    assert last.present
    assert last.torso_angle < 10.0
    assert 0.6 < last.elevation < 1.2  # knees ~0.9 torso-lengths above floor
    assert abs(last.scale - S) < 0.02
    assert last.vis_frac > 0.9
    assert last.aspect > 2.0


def test_lying_on_floor_signals() -> None:
    sigs = _run(_frames(LIE, 30))
    last = sigs[-1]
    assert last.torso_angle > 80.0
    assert last.elevation < 0.35
    assert last.aspect < 1.0


def test_lying_on_couch_elevation() -> None:
    sigs = _run(_frames(LIE, 30, support=0.80))
    assert sigs[-1].elevation >= 0.35  # the couch/bed discriminator


def test_descent_velocity_sign_and_magnitude() -> None:
    # body translating DOWN at 0.05 image-units/s -> ~0.29 torso-lengths/s
    sigs = _run(_frames(STAND, 45, support_drift=0.05))
    v = sigs[-1].v_descent
    assert 0.15 < v < 0.45


def test_ascent_velocity_negative() -> None:
    sigs = _run(_frames(STAND, 45, support_drift=-0.05))
    assert sigs[-1].v_descent < -0.15


def test_motion_energy_still_below_threshold() -> None:
    # median over the still tail: single noise excursions are absorbed by the
    # state machine's hysteresis, the SUSTAINED level is what must sit under
    # STILL_MOTION
    sigs = _run(_frames(LIE, 45, jitter=0.0015))
    tail = sorted(s.motion_energy for s in sigs[20:])
    assert tail[len(tail) // 2] < 0.02


def test_motion_energy_purposeful_above_threshold() -> None:
    sigs = _run(_frames(LIE, 45, sway=0.03))
    assert max(s.motion_energy for s in sigs[20:]) > 0.10


def test_occluded_legs_keep_torso_scale() -> None:
    """Leg occlusion (the dominant case) must not break normalization."""
    sigs = _run(_frames(STAND, 30, occlude_legs=True))
    last = sigs[-1]
    assert last.vis_frac < 0.9  # legs really are occluded
    assert abs(last.scale - S) < 0.02  # torso scale survives


def test_absent_frame() -> None:
    ex = SignalExtractor(FLOOR)
    sig = ex.update(PoseFrame(t=1.0, landmarks=None))
    assert not sig.present


def test_default_floor_used_when_unfitted() -> None:
    ex = SignalExtractor(FloorCalibration(), default_floor_y=0.95)
    sig = ex.update(_frames(STAND, 1)[0])
    assert sig.present and sig.elevation > 0.5
