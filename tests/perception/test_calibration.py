"""Floor-line fit, zone grid, learning phase, placement check, YOLO seeding."""

from __future__ import annotations

import random
import time

from meemoo.perception.calibration import (
    REST_ZONE_MIN_HITS,
    CalibrationState,
    FloorCalibration,
    ZoneGrid,
)
from meemoo.perception.yolo_bootstrap import FurnitureBox, seed_zones_from_boxes
from tests.fixtures.synth.body import FLOOR_Y, SIT_CHAIR, STAND, make_frame
from tests.perception.harness import sf


def test_floor_fit_recovers_line() -> None:
    rng = random.Random(1)
    floor = FloorCalibration()
    for _ in range(60):
        x = rng.uniform(0.1, 0.9)
        y = 0.02 * x + 0.90 + rng.gauss(0.0, 0.002)
        floor.add_upright_sample(x, y, 0.17)
    assert floor.fitted
    assert abs(floor.floor_y(0.5) - 0.91) < 0.01
    assert floor.scale_prior(0.90) is not None


def test_floor_fit_degenerate_single_column() -> None:
    floor = FloorCalibration()
    for _ in range(40):
        floor.add_upright_sample(0.5, 0.9, 0.17)
    assert floor.fitted and abs(floor.floor_y(0.2) - 0.9) < 0.01


def test_zone_grid_learns_and_answers() -> None:
    grid = ZoneGrid()
    for _ in range(REST_ZONE_MIN_HITS):
        grid.add_rest_observation(0.7, 0.8)
    assert grid.is_rest_zone(0.7, 0.8)
    assert not grid.is_rest_zone(0.2, 0.3)


def test_yolo_seeding_rest_classes_only() -> None:
    grid = ZoneGrid()
    seeded = seed_zones_from_boxes(
        grid,
        [
            FurnitureBox("bed", 0.3, 0.5, 0.9, 0.85),
            FurnitureBox("tv", 0.0, 0.0, 0.2, 0.2),
        ],
    )
    assert seeded == 1
    assert grid.is_rest_zone(0.6, 0.80)  # lower half of the bed box
    assert not grid.is_rest_zone(0.1, 0.1)  # tv is not a rest surface


def test_placement_check_refuses_high_floor() -> None:
    calib = CalibrationState()
    assert not calib.can_arm()  # unfitted
    calib.floor = FloorCalibration.from_line(0.0, 0.5)  # floor not in lower third
    assert not calib.can_arm()
    calib.floor = FloorCalibration.from_line(0.0, 0.9)
    assert calib.can_arm()


def test_learning_phase_window() -> None:
    calib = CalibrationState()
    assert calib.in_learning()
    calib.started_at = time.time() - calib.learning_days * 86400.0 - 1.0
    assert not calib.in_learning()


def test_observe_accumulates_floor_and_zones() -> None:
    rng = random.Random(2)
    calib = CalibrationState()
    upright = make_frame(STAND, 0.5, FLOOR_Y, 1, rng, 1.0)
    calib.observe(sf(1.0, torso_angle=5.0, vis_frac=1.0), upright)
    assert len(calib.floor.samples) == 1

    sitting = make_frame(SIT_CHAIR, 0.3, 0.80, 1, rng, 2.0)
    sig = sf(2.0, torso_angle=40.0, elevation=0.5, motion_energy=0.01, x=0.3, support_y=0.82)
    for _ in range(REST_ZONE_MIN_HITS):
        calib.observe(sig, sitting)
    assert calib.zones.is_rest_zone(0.3, 0.82)


def test_status_fields_shape() -> None:
    fields = CalibrationState().status_fields()
    assert set(fields) == {"floor_fitted", "floor_samples", "learning", "armable"}
