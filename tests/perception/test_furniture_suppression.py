"""classify_grounded unit tests — research 05 §A.5 verbatim behavior."""

from __future__ import annotations

from meemoo.perception.suppression import GroundedContext, classify_grounded
from meemoo.perception.thresholds import load_thresholds

TH = load_thresholds()


class _Zones:
    def __init__(self, rest: bool) -> None:
        self._rest = rest

    def is_rest_zone(self, x: float, y: float) -> bool:
        return self._rest


def _ctx(**kw: float | bool) -> GroundedContext:
    defaults: dict[str, float | bool] = {
        "x": 0.5,
        "support_y": 0.8,
        "elevation": 0.1,
        "v_peak": 0.3,
        "hip_drop_0_8s": 0.2,
        "motion_energy": 0.01,
        "still_duration": 10.0,
        "slid_toward_floor": False,
        "habitual_rest_time": False,
    }
    defaults.update(kw)
    return GroundedContext(**defaults)  # type: ignore[arg-type]


def test_ballistic_velocity_always_overrides_furniture() -> None:
    ctx = _ctx(elevation=0.6, v_peak=2.0)
    assert classify_grounded(ctx, _Zones(True), TH) == "CANDIDATE"


def test_ballistic_hip_drop_always_overrides_furniture() -> None:
    ctx = _ctx(elevation=0.6, v_peak=0.5, hip_drop_0_8s=1.8)
    assert classify_grounded(ctx, _Zones(True), TH) == "CANDIDATE"


def test_rest_zone_suppresses_controlled_lie() -> None:
    ctx = _ctx(elevation=0.6)
    assert classify_grounded(ctx, _Zones(True), TH) == "SUPPRESSED_FURNITURE"


def test_elevated_but_unmapped_is_monitor_not_suppressed() -> None:
    """Elevation alone never suppresses — the zone must be LEARNED."""
    ctx = _ctx(elevation=0.6)
    assert classify_grounded(ctx, _Zones(False), TH) == "MONITOR"


def test_slid_toward_floor_escapes_suppression() -> None:
    ctx = _ctx(elevation=0.6, slid_toward_floor=True)
    assert classify_grounded(ctx, _Zones(True), TH) == "CANDIDATE"


def test_thirty_minute_still_escape_non_habitual() -> None:
    ctx = _ctx(elevation=0.6, motion_energy=0.005, still_duration=TH.furniture_still_escape_s + 1)
    assert classify_grounded(ctx, _Zones(True), TH) == "CANDIDATE"


def test_habitual_rest_time_keeps_suppression() -> None:
    ctx = _ctx(
        elevation=0.6,
        motion_energy=0.005,
        still_duration=TH.furniture_still_escape_s + 1,
        habitual_rest_time=True,
    )
    assert classify_grounded(ctx, _Zones(True), TH) == "SUPPRESSED_FURNITURE"


def test_floor_controlled_descent_is_soft_never_suppressed() -> None:
    """Recall-over-precision: floor rest gets a QUESTION, not silence."""
    ctx = _ctx(elevation=0.1)
    assert classify_grounded(ctx, _Zones(False), TH) == "CANDIDATE_SOFT"
