"""SimulatedDock: funnel truth + TWO-SIGNAL capture (Art. II §3)."""

from __future__ import annotations

import math

import pytest

from meemoo.flight.constants import DockConfig, PhysicsConfig
from meemoo.flight.floorplan import load_plan
from meemoo.flight.physics import BlimpPhysics
from meemoo.flight.sim_dock import SimulatedDock
from meemoo.flight.types import CaptureTelemetry, ThrustCommand

PLAN = load_plan("apartment")


def make_pair(seed: int = 0) -> tuple[BlimpPhysics, SimulatedDock]:
    phys = BlimpPhysics(PhysicsConfig(), PLAN, seed=seed, buoyancy_gf=0.0,
                        drafts_enabled=False)
    dock = SimulatedDock(PLAN.dock, DockConfig(), seed=seed)
    return phys, dock


def aim_at_mouth(phys: BlimpPhysics, dock: SimulatedDock,
                 *, lateral_m: float, speed_mps: float, start_m: float = 0.5) -> None:
    """Place the blimp on the approach axis flying INTO the mouth."""
    ax, ay = dock.pose.axis
    heading = math.atan2(-ay, -ax)
    phys.heading = heading
    arm = phys.cfg.nose_arm_m
    nose_x = dock.pose.x + ax * start_m - ay * lateral_m  # + l_hat·lateral
    nose_y = dock.pose.y + ay * start_m + ax * lateral_m
    phys.x = nose_x - arm * math.cos(heading)
    phys.y = nose_y - arm * math.sin(heading)
    phys.z = dock.pose.z
    phys.vx = -ax * speed_mps
    phys.vy = -ay * speed_mps
    phys.frozen = False


def fly(phys: BlimpPhysics, dock: SimulatedDock, seconds: float,
        forward_gf: float = 0.0) -> None:
    for _ in range(int(seconds / 0.02)):
        phys.command(ThrustCommand(forward_gf=forward_gf))
        phys.step(0.02)
        dock.interact(phys, 0.02)


def first_contact(phys: BlimpPhysics, dock: SimulatedDock, seconds: float,
                  forward_gf: float = 0.0) -> str | None:
    """Fly until the FIRST mouth contact; returns the funnel's verdict."""
    for _ in range(int(seconds / 0.02)):
        phys.command(ThrustCommand(forward_gf=forward_gf))
        phys.step(0.02)
        dock.interact(phys, 0.02)
        if dock.last_rejected is not None:
            return dock.last_rejected
        if dock.in_funnel:
            return "entered"
    return None


class TestTwoSignalCapture:
    """Never vision, never a single channel — Constitution Art. II §3."""

    @pytest.mark.parametrize(("retention", "contact", "switch"), [
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),   # contact but not seated: NOT captured
        (True, False, True),   # switch glitch without continuity: NOT captured
    ])
    def test_single_or_mismatched_signals_never_confirm(
        self, retention: bool, contact: bool, switch: bool
    ) -> None:
        t = CaptureTelemetry(retention_engaged=retention,
                             contact_continuity=contact, capture_switch=switch)
        assert not t.confirmed

    def test_both_electrical_signals_confirm(self) -> None:
        t = CaptureTelemetry(retention_engaged=False,
                             contact_continuity=True, capture_switch=True)
        assert t.confirmed

    def test_dock_partial_progress_is_not_captured(self) -> None:
        phys, dock = make_pair()
        dock.set_retention(True)
        dock.in_funnel = True
        dock.progress = 0.9  # contact continuity yes, hall switch no
        cap = dock.capture()
        assert cap.contact_continuity and not cap.capture_switch
        assert not cap.confirmed


class TestFunnel:
    def test_centered_slow_entry_captures(self) -> None:
        phys, dock = make_pair()
        aim_at_mouth(phys, dock, lateral_m=0.0, speed_mps=0.08)
        dock.set_retention(True)
        fly(phys, dock, 20.0, forward_gf=6.0)
        assert dock.capture().confirmed
        assert phys.frozen  # magnet carries the airframe

    def test_off_axis_entry_bounces(self) -> None:
        phys, dock = make_pair()
        aim_at_mouth(phys, dock, lateral_m=0.10, speed_mps=0.08)
        assert first_contact(phys, dock, 10.0, forward_gf=4.0) == "radial_error"
        assert not dock.in_funnel

    def test_fast_entry_bounces(self) -> None:
        phys, dock = make_pair()
        aim_at_mouth(phys, dock, lateral_m=0.0, speed_mps=0.30)
        assert first_contact(phys, dock, 4.0, forward_gf=4.0) == "too_fast"
        assert not dock.in_funnel

    def test_no_tunnelling_through_the_dock_face(self) -> None:
        """A fast miss must not fly through the mouth plane untested."""
        phys, dock = make_pair()
        aim_at_mouth(phys, dock, lateral_m=0.05, speed_mps=0.40)
        assert first_contact(phys, dock, 3.0, forward_gf=8.0) == "too_fast"

    def test_slide_needs_held_thrust(self) -> None:
        """research/06 §B.1: a funnel does not passively centre a
        neutrally-buoyant vehicle — drop the thrust and it stalls out."""
        phys, dock = make_pair()
        aim_at_mouth(phys, dock, lateral_m=0.0, speed_mps=0.10, start_m=0.04)
        assert first_contact(phys, dock, 2.0, forward_gf=4.0) == "entered"
        fly(phys, dock, 1.5, forward_gf=6.0)
        p1 = dock.progress
        assert p1 > 0.05  # held thrust slides inward
        fly(phys, dock, 5.0, forward_gf=0.0)  # thrust dropped
        assert dock.progress < p1 or not dock.in_funnel  # slid back out

    def test_magnet_only_seats_the_last_centimetre(self) -> None:
        phys, dock = make_pair()
        dock.set_retention(True)
        dock.in_funnel = True
        dock.progress = 0.5  # far from the throat: magnet must NOT seat
        aim_at_mouth(phys, dock, lateral_m=0.0, speed_mps=0.0)
        fly(phys, dock, 1.0, forward_gf=0.0)
        assert dock.progress < dock.cfg.magnet_seat_progress


class TestChargeAndRelease:
    def _captured(self) -> tuple[BlimpPhysics, SimulatedDock]:
        phys, dock = make_pair()
        dock.force_capture(phys)
        return phys, dock

    def test_charge_needs_confirmation_and_enable(self) -> None:
        phys, dock = self._captured()
        phys.battery_pct = 40.0
        assert dock.charge(40.0).charge_state == "none"  # not enabled yet
        dock.set_charge_enabled(True)
        assert dock.charge(40.0).charge_state == "bulk"
        assert dock.charge(90.0).charge_state == "topping"
        assert dock.charge(100.0).charge_state == "complete"

    def test_release_frees_airframe_after_reverse_pulse(self) -> None:
        phys, dock = self._captured()
        assert bool(phys.frozen)
        dock.set_retention(False)
        fly(phys, dock, 0.3)  # remanence window: still held
        held = phys.frozen
        fly(phys, dock, 0.5)
        freed = not phys.frozen
        assert held and freed
        assert not dock.capture().confirmed

    def test_load_cell_reads_trim(self) -> None:
        phys, dock = self._captured()
        phys.buoyancy_gf = -3.0  # 3 g heavy
        fly(phys, dock, 0.2)
        assert dock.load_cell_g == pytest.approx(3.0, abs=0.5)

    def test_helium_decays_and_tops_off(self) -> None:
        phys, dock = self._captured()
        for _ in range(200):
            dock.interact(phys, 3600.0)  # ~8 days in dock-time steps
        assert dock.helium_level_pct < 100.0
        assert phys.net_buoyancy_true_gf < phys.buoyancy_gf  # heavier trim
        dock.top_off()
        assert dock.helium_level_pct == 100.0


class TestDockCamera:
    def test_rate_limited_with_age(self) -> None:
        phys, dock = make_pair()
        aim_at_mouth(phys, dock, lateral_m=0.0, speed_mps=0.0, start_m=1.0)
        r1 = dock.observe(phys)
        phys.step(0.01)
        r2 = dock.observe(phys)  # within the 20 Hz period: cached + aged
        assert r2.tracking_age_ms >= 9.0
        assert r2.lateral_error_mm == r1.lateral_error_mm

    def test_invalid_outside_fov(self) -> None:
        phys, dock = make_pair()
        aim_at_mouth(phys, dock, lateral_m=2.5, speed_mps=0.0, start_m=1.0)
        assert not dock.observe(phys).tracking_valid

    def test_valid_on_axis(self) -> None:
        phys, dock = make_pair()
        aim_at_mouth(phys, dock, lateral_m=0.0, speed_mps=0.0, start_m=1.5)
        rel = dock.observe(phys)
        assert rel.tracking_valid
        assert abs(rel.lateral_error_mm) < 40.0
        assert rel.range_to_throat_mm == pytest.approx(1500.0, abs=120.0)
