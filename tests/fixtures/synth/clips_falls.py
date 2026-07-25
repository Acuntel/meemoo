"""Fall-clip specs: ballistic, seated-end, out-of-bed, vanished, long-lie."""

from __future__ import annotations

from tests.fixtures.synth.body import LIE, SEATED_FLOOR, STAND
from tests.fixtures.synth.compiler import ClipSpec, Seg
from tests.fixtures.synth.scene import BED, BED_ZONE, FALL, FLOOR, OTTOMAN


def _hard_fall(name: str, seed: int, **overrides: object) -> ClipSpec:
    """Walk → ballistic fall (~0.55 s) → still on the floor for 18 s."""
    spec = ClipSpec(
        name=name,
        fps=15.0,
        label="fall",
        seed=seed,
        segments=[
            Seg(1.5, STAND, hip_x=0.30),
            Seg(3.0, STAND, hip_x=0.52, swing=0.15),
            Seg(0.55, LIE, hip_x=0.62, ease="accel"),
            Seg(18.0, LIE, hip_x=0.62),
        ],
        expect=dict(FALL),
        t_impact=5.05,
    )
    for key, value in overrides.items():
        setattr(spec, key, value)
    return spec


def build_fall_specs() -> list[ClipSpec]:
    return [
        _hard_fall("fall_forward_ballistic", seed=11),
        ClipSpec(
            name="fall_backward",
            fps=15.0,
            label="fall",
            seed=12,
            segments=[
                Seg(1.5, STAND, hip_x=0.50),
                Seg(3.0, STAND, hip_x=0.42, swing=0.15),
                Seg(0.55, LIE, hip_x=0.36, direction=-1, ease="accel"),
                Seg(18.0, LIE, hip_x=0.36, direction=-1),
            ],
            expect=dict(FALL),
            t_impact=5.05,
        ),
        ClipSpec(
            name="fall_lateral",
            fps=15.0,
            label="fall",
            seed=13,
            segments=[
                Seg(1.0, STAND, hip_x=0.35),
                Seg(2.5, STAND, hip_x=0.48, swing=0.15),
                Seg(0.50, LIE, hip_x=0.55, ease="accel"),
                Seg(18.0, LIE, hip_x=0.55),
            ],
            expect=dict(FALL),
            t_impact=4.0,
        ),
        ClipSpec(
            name="fall_end_seated",
            fps=15.0,
            label="fall",
            seed=14,
            segments=[
                Seg(1.5, STAND, hip_x=0.30),
                Seg(2.5, STAND, hip_x=0.45, swing=0.15),
                Seg(0.55, SEATED_FLOOR, hip_x=0.50, ease="accel"),
                Seg(18.0, SEATED_FLOOR, hip_x=0.50),
            ],
            expect=dict(FALL),
            t_impact=4.55,
            notes="fall ending seated against furniture — torso never horizontal "
            "(AltumView hard case); triggers on LOW HIP ELEVATION, not angle",
        ),
        ClipSpec(
            name="fall_out_of_bed",
            fps=15.0,
            label="fall",
            seed=15,
            segments=[
                Seg(6.0, LIE, support=BED, hip_x=0.65),
                Seg(0.45, LIE, support=FLOOR, hip_x=0.58, ease="accel"),
                Seg(19.0, LIE, support=FLOOR, hip_x=0.58),
            ],
            expect=dict(FALL),
            rest_zones=[BED_ZONE],
            t_impact=6.45,
            notes="ballistic override of furniture suppression — velocity ALWAYS "
            "beats zone suppression (research 05 §A.5)",
        ),
        _hard_fall(
            "fall_night_lowvis", seed=16, vis_base=0.68, vis_sigma=0.10, jitter=0.004
        ),
        _hard_fall("fall_occluded_legs", seed=17, occlude_legs=True),
        ClipSpec(
            name="fall_slow_collapse",
            fps=10.0,
            label="fall",
            seed=18,
            segments=[
                Seg(1.5, STAND, hip_x=0.30),
                Seg(2.0, STAND, hip_x=0.40, swing=0.15),
                Seg(2.6, LIE, hip_x=0.48),
                Seg(46.0, LIE, hip_x=0.48),
            ],
            expect={
                "candidate": True,
                "person_down": False,
                "recovered": False,
                "escalate": False,
                "soft_only": True,
            },
            notes="slow non-ballistic collapse — recall comes from the persistence "
            "path (CANDIDATE_SOFT at 40 s), the class descent-AND-persistence "
            "logic would MISS",
        ),
        ClipSpec(
            name="fall_vanish_bottom",
            fps=15.0,
            label="fall",
            seed=19,
            segments=[
                Seg(1.0, STAND, hip_x=0.50),
                Seg(2.0, STAND, hip_x=0.68, swing=0.15),
                Seg(0.50, LIE, hip_x=0.74, ease="accel"),
                Seg(18.0, LIE, hip_x=0.74, absent=True),
            ],
            expect=dict(FALL),
            t_impact=3.5,
            notes="VANISHED_DOWN parallel path: pose exits bottom of frame with "
            "ballistic v_descent; timers keep running while absent",
        ),
        ClipSpec(
            name="fall_longlie_unmapped",
            fps=5.0,
            label="fall",
            seed=20,
            segments=[
                Seg(2.0, STAND, hip_x=0.55),
                Seg(2.0, LIE, support=OTTOMAN, hip_x=0.60),
                Seg(100.0, LIE, support=OTTOMAN, hip_x=0.60),
            ],
            expect={
                "candidate": True,
                "person_down": False,
                "recovered": False,
                "escalate": False,
            },
            notes="LONG_LIE backstop: horizontal + still at mid elevation on "
            "UNMAPPED furniture — no rest zone, no ballistic descent; the 90 s "
            "persistence path is the only way in",
        ),
        ClipSpec(
            name="fall_no_response",
            fps=10.0,
            label="fall",
            seed=21,
            segments=[
                Seg(1.0, STAND, hip_x=0.30),
                Seg(2.0, STAND, hip_x=0.45, swing=0.15),
                Seg(0.55, LIE, hip_x=0.55, ease="accel"),
                Seg(57.0, LIE, hip_x=0.55),
            ],
            expect={
                "candidate": True,
                "person_down": True,
                "recovered": False,
                "escalate": True,
            },
            t_impact=3.55,
            notes="full ladder: candidate → person.down → 2 voice prompts → "
            "escalate at T_ESCALATE with no voice response",
        ),
    ]
