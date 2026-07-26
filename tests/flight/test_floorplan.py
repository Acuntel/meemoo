"""Floor plans: built-ins load, geometry helpers, bad input."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from meemoo.flight.floorplan import BUILTIN_PLANS, load_plan


def test_builtin_plans_load_with_dock_and_person_waypoint() -> None:
    for name in BUILTIN_PLANS:
        plan = load_plan(name)
        x0, y0, x1, y1 = plan.bounds
        assert x0 < plan.dock.x < x1 and y0 < plan.dock.y < y1
        assert plan.person_waypoints(), f"{name} must have a person waypoint"
        assert plan.rooms


def test_standoff_is_out_along_the_axis() -> None:
    plan = load_plan("apartment")
    sx, sy = plan.standoff(1.5)
    assert sx == pytest.approx(plan.dock.x + 1.5)  # heading_deg = 0
    assert sy == pytest.approx(plan.dock.y)


def test_unknown_plan_raises() -> None:
    with pytest.raises(ValueError, match="unknown floor plan"):
        load_plan("penthouse")


def test_custom_json_path_loads(tmp_path: Path) -> None:
    p = tmp_path / "studio.json"
    p.write_text(json.dumps({
        "bounds": [0, 0, 5, 4],
        "dock": {"x": 0.5, "y": 2.0, "heading_deg": 0.0},
        "waypoints": [{"label": "bed", "kind": "person", "x": 4.0, "y": 2.0}],
    }), encoding="utf-8")
    plan = load_plan(str(p))
    assert plan.name == "studio"
    assert plan.person_waypoints()[0].label == "bed"


def test_to_dict_is_json_serializable() -> None:
    json.dumps(load_plan("facility_wing").to_dict())
