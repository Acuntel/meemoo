"""ADL + recovery clip specs: the precision side of the suite."""

from __future__ import annotations

from tests.fixtures.synth.body import BEND, LIE, SEATED_FLOOR, SIT_CHAIR, STAND
from tests.fixtures.synth.compiler import ClipSpec, Seg
from tests.fixtures.synth.scene import (
    ADL,
    BED,
    BED_ZONE,
    CHAIR,
    CHAIR_ZONE,
    COUCH,
    COUCH_ZONE,
)


def build_daily_specs() -> list[ClipSpec]:
    return [
        # ----------------------------------------------------------------- ADLs
        ClipSpec(
            name="adl_walk",
            fps=15.0,
            label="adl",
            seed=31,
            segments=[
                Seg(1.0, STAND, hip_x=0.25),
                Seg(6.0, STAND, hip_x=0.70, swing=0.15),
                Seg(6.0, STAND, hip_x=0.30, swing=0.15),
                Seg(6.0, STAND, hip_x=0.60, swing=0.15),
            ],
            expect=dict(ADL),
        ),
        ClipSpec(
            name="adl_sit_chair",
            fps=15.0,
            label="adl",
            seed=32,
            segments=[
                Seg(2.5, STAND, hip_x=0.50),
                Seg(2.0, STAND, hip_x=0.30, swing=0.15),
                Seg(1.5, SIT_CHAIR, support=CHAIR, hip_x=0.30),
                Seg(25.0, SIT_CHAIR, support=CHAIR, hip_x=0.30),
                Seg(1.5, STAND, hip_x=0.32),
                Seg(2.0, STAND, hip_x=0.50, swing=0.15),
            ],
            expect=dict(ADL),
            rest_zones=[CHAIR_ZONE],
        ),
        ClipSpec(
            name="adl_lie_couch",
            fps=15.0,
            label="adl",
            seed=33,
            segments=[
                Seg(2.5, STAND, hip_x=0.40),
                Seg(2.0, STAND, hip_x=0.72, swing=0.15),
                Seg(3.2, LIE, support=COUCH, hip_x=0.72),
                Seg(30.0, LIE, support=COUCH, hip_x=0.72),
                Seg(2.0, SIT_CHAIR, support=COUCH, hip_x=0.70),
                Seg(1.5, STAND, hip_x=0.68),
                Seg(2.0, STAND, hip_x=0.45, swing=0.15),
            ],
            expect=dict(ADL),
            rest_zones=[COUCH_ZONE],
            notes="intentional couch lie-down (>3 s controlled descent, "
            "PMC8321307) — suppressed by the learned zone grid, zero events",
        ),
        ClipSpec(
            name="adl_lie_bed",
            fps=10.0,
            label="adl",
            seed=34,
            segments=[
                Seg(2.0, STAND, hip_x=0.40),
                Seg(2.0, STAND, hip_x=0.62, swing=0.15),
                Seg(3.5, LIE, support=BED, hip_x=0.65),
                Seg(40.0, LIE, support=BED, hip_x=0.65),
                Seg(2.0, SIT_CHAIR, support=BED, hip_x=0.63),
                Seg(1.5, STAND, hip_x=0.60),
                Seg(2.0, STAND, hip_x=0.45, swing=0.15),
            ],
            expect=dict(ADL),
            rest_zones=[BED_ZONE],
        ),
        ClipSpec(
            name="adl_yoga_floor",
            fps=5.0,
            label="adl",
            seed=35,
            segments=[
                Seg(2.0, STAND, hip_x=0.45),
                Seg(2.5, SEATED_FLOOR, hip_x=0.50),
                Seg(30.0, SEATED_FLOOR, hip_x=0.50),
                Seg(6.0, SEATED_FLOOR, hip_x=0.50, sway=0.02, hold=True),
                Seg(46.0, SEATED_FLOOR, hip_x=0.50),
                Seg(5.0, SEATED_FLOOR, hip_x=0.50, sway=0.02, hold=True),
                Seg(2.0, STAND, hip_x=0.48),
                Seg(3.0, STAND, hip_x=0.35, swing=0.15),
            ],
            expect={
                "candidate": True,
                "person_down": False,
                "recovered": True,
                "escalate": False,
                "soft_only": True,
                "max_candidates": 1,
            },
            notes="deliberate floor-sitter: at most ONE gentle CANDIDATE_SOFT "
            "question (~40 s), never person.down — §A.5's key concession",
        ),
        ClipSpec(
            name="adl_pickup_floor",
            fps=15.0,
            label="adl",
            seed=36,
            segments=[
                Seg(2.0, STAND, hip_x=0.35),
                Seg(2.0, STAND, hip_x=0.50, swing=0.15),
                Seg(1.2, BEND, hip_x=0.50),
                Seg(0.8, BEND, hip_x=0.50),
                Seg(1.2, STAND, hip_x=0.50),
                Seg(2.0, STAND, hip_x=0.35, swing=0.15),
            ],
            expect=dict(ADL),
        ),
        ClipSpec(
            name="adl_sit_floor_short",
            fps=15.0,
            label="adl",
            seed=37,
            segments=[
                Seg(2.0, STAND, hip_x=0.45),
                Seg(2.2, SEATED_FLOOR, hip_x=0.50),
                Seg(20.0, SEATED_FLOOR, hip_x=0.50),
                Seg(2.0, STAND, hip_x=0.48),
                Seg(2.0, STAND, hip_x=0.35, swing=0.15),
            ],
            expect=dict(ADL),
            notes="20 s floor sit exits SILENTLY — below every candidate timer",
        ),
        # ------------------------------------------------------------- recovery
        ClipSpec(
            name="recovery_fall_standup",
            fps=15.0,
            label="recovery",
            seed=41,
            segments=[
                Seg(1.0, STAND, hip_x=0.30),
                Seg(2.5, STAND, hip_x=0.50, swing=0.15),
                Seg(0.55, LIE, hip_x=0.60, ease="accel"),
                Seg(7.0, LIE, hip_x=0.60),
                Seg(1.5, STAND, hip_x=0.58),
                Seg(5.0, STAND, hip_x=0.40, swing=0.15),
            ],
            expect={
                "candidate": True,
                "person_down": False,
                "recovered": True,
                "escalate": False,
            },
            t_impact=4.05,
            notes="fall → candidate.fall → stands up before 15 s → "
            "person.recovered, near-miss logged, no person.down",
        ),
        ClipSpec(
            name="recovery_after_down",
            fps=15.0,
            label="recovery",
            seed=42,
            segments=[
                Seg(1.0, STAND, hip_x=0.30),
                Seg(2.5, STAND, hip_x=0.50, swing=0.15),
                Seg(0.55, LIE, hip_x=0.60, ease="accel"),
                Seg(24.0, LIE, hip_x=0.60),
                Seg(1.5, STAND, hip_x=0.58),
                Seg(4.0, STAND, hip_x=0.40, swing=0.15),
            ],
            expect={
                "candidate": True,
                "person_down": True,
                "recovered": True,
                "escalate": False,
            },
            t_impact=4.05,
            notes="recovers during VERIFYING — person.down then person.recovered, "
            "no escalation",
        ),
    ]
