"""Couch/bed suppression logic — research 05 §A.5, implemented EXACTLY.

The bright line: a ballistic descent ALWAYS overrides furniture suppression.
Falls out of bed and off chairs are real and common. Do not invert this.

`CANDIDATE_SOFT` is the recall-over-precision concession: a deliberate
floor-sitter gets asked a friendly question after ~40 s rather than 15 s, and
never gets escalated if they answer. The cost of the wrong guess is one
question; the cost of hard-suppressing is a missed fall.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from meemoo.perception.thresholds import Thresholds
from meemoo.perception.types import RestZoneOracle

GroundedClass = Literal["CANDIDATE", "CANDIDATE_SOFT", "SUPPRESSED_FURNITURE", "MONITOR"]


@dataclass(frozen=True, slots=True)
class GroundedContext:
    """Everything classify_grounded needs to know about the settled person."""

    x: float
    support_y: float
    elevation: float  # torso-lengths above the floor line
    v_peak: float  # peak descent velocity during this episode (tl/s)
    hip_drop_0_8s: float  # max hip drop within any 0.8 s window (tl)
    motion_energy: float
    still_duration: float  # seconds of continuous stillness in this position
    slid_toward_floor: bool  # was on furniture, support point migrated floorward
    habitual_rest_time: bool  # schedule hook: is this a normal nap time/place?


def classify_grounded(
    st: GroundedContext, zones: RestZoneOracle, th: Thresholds
) -> GroundedClass:
    """Classify a settled (post-descent) person. Research 05 §A.5 verbatim."""
    on_furniture = st.elevation >= th.furniture_elevation and zones.is_rest_zone(
        st.x, st.support_y
    )

    ballistic = st.v_peak > th.ballistic_v or st.hip_drop_0_8s > th.ballistic_drop

    # A ballistic descent ALWAYS overrides furniture suppression.
    if ballistic:
        return "CANDIDATE"

    if on_furniture:
        # still tracked, not alarmed — but three escapes remain
        if st.slid_toward_floor:
            return "CANDIDATE"
        if (
            not st.habitual_rest_time
            and st.motion_energy < th.still_motion
            and st.still_duration > th.furniture_still_escape_s
        ):
            return "CANDIDATE"
        return "SUPPRESSED_FURNITURE"

    if st.elevation < th.near_floor_elevation:
        # on the floor after a controlled descent: yoga / prayer / reaching /
        # napping. Recall-over-precision: do NOT hard-suppress. Ask, later,
        # gently.
        return "CANDIDATE_SOFT"

    return "MONITOR"
