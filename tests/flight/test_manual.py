"""Manual slider control (Flight Test): mapping, stop, cap, zones, expiry."""

from __future__ import annotations

import math

from meemoo.core import topics
from meemoo.flight.manual import MANUAL_TTL_S
from meemoo.flight.mission import FlightMode
from meemoo.flight.sim_blimp import Emission, SimulatedBlimp
from meemoo.flight.zones import Zone


def make_sim(**kw: object) -> SimulatedBlimp:
    kw.setdefault("seed", 3)
    kw.setdefault("drafts_enabled", False)
    kw.setdefault("start_docked", False)
    kw.setdefault("pose_noise_m", 0.0)
    return SimulatedBlimp("apartment", **kw)  # type: ignore[arg-type]


def drive(
    sim: SimulatedBlimp,
    seconds: float,
    *,
    forward: float = 0.0,
    vertical: float = 0.0,
    yaw: float = 0.0,
    resend_every: float = 0.3,
    dt: float = 0.02,
) -> list[Emission]:
    """Hold a slider frame for a while, re-sending like the page does."""
    out: list[Emission] = []
    next_send = 0.0
    for _ in range(int(seconds / dt)):
        if sim.phys.t >= next_send:
            sim.set_manual_input(forward, vertical, yaw)
            next_send = sim.phys.t + resend_every
        out.extend(sim.tick(dt))
    return out


class TestSliderMapping:
    def test_control_enters_manual_and_emits_state(self) -> None:
        sim = make_sim()
        result = sim.set_manual_input(0.5, 0.0, 0.0)
        assert result["accepted"] is True
        assert sim.mode is FlightMode.MANUAL
        emissions = sim.tick(0.02)
        assert (topics.FLIGHT_STATE, {"device_id": 1, "phase": "MANUAL"}) in emissions

    def test_forward_slider_moves_along_heading(self) -> None:
        sim = make_sim()
        hdg = sim.phys.heading
        x0, y0 = sim.phys.x, sim.phys.y
        drive(sim, 4.0, forward=1.0)
        moved = (sim.phys.x - x0) * math.cos(hdg) + (sim.phys.y - y0) * math.sin(hdg)
        assert moved > 0.5, "full forward should travel along the heading"

    def test_vertical_slider_climbs(self) -> None:
        sim = make_sim()
        z0 = sim.phys.z
        drive(sim, 3.0, vertical=1.0)
        assert sim.phys.z > z0 + 0.3

    def test_yaw_slider_turns_and_release_damps(self) -> None:
        sim = make_sim()
        h0 = sim.phys.heading
        drive(sim, 2.0, yaw=1.0)
        assert abs(sim.phys.heading - h0) > 0.4, "turn slider should yaw"
        drive(sim, 2.0)  # sticks at zero: the rate damper spins it down
        assert abs(sim.phys.yaw_rate) < 0.15

    def test_neutral_sticks_sink_gently_on_negative_trim(self) -> None:
        """No fake hover assist: zero input = the honest feather sink."""
        sim = make_sim(buoyancy_gf=-3.0)
        z0 = sim.phys.z
        drive(sim, 5.0)
        assert sim.phys.z < z0, "negative trim must sink with sticks at zero"


class TestRefusals:
    def test_docked_control_is_refused_honestly(self) -> None:
        sim = make_sim(start_docked=True)
        result = sim.set_manual_input(1.0, 0.0, 0.0)
        assert result["accepted"] is False
        assert "dock" in str(result["reason"]).lower()
        assert sim.mode is FlightMode.DOCKED

    def test_landed_control_is_refused(self) -> None:
        sim = make_sim()
        sim.mode = FlightMode.LANDED
        result = sim.set_manual_input(0.5, 0.0, 0.0)
        assert result["accepted"] is False
        assert sim.mode is FlightMode.LANDED


class TestStop:
    def test_halt_clears_manual_and_brakes(self) -> None:
        sim = make_sim()
        drive(sim, 2.0, forward=1.0)
        assert sim.manual_active()
        sim.halt()
        assert sim.mode is FlightMode.HOLD
        assert sim.manual_active() is False
        for _ in range(int(6.0 / 0.02)):
            sim.tick(0.02)
        speed = math.hypot(sim.phys.vx, sim.phys.vy)
        assert speed < 0.12, f"still moving {speed:.2f} m/s after STOP"

    def test_input_expiry_falls_back_to_hold(self) -> None:
        """The HTTP twin of the MUP/1 ttl: no fresh frame, no thrust."""
        sim = make_sim()
        sim.set_manual_input(1.0, 0.0, 0.0)
        for _ in range(int((MANUAL_TTL_S + 1.0) / 0.02)):
            sim.tick(0.02)
        assert sim.mode is FlightMode.HOLD
        assert sim.manual_active() is False


class TestSpeedCap:
    def test_full_forward_never_beats_the_governor(self) -> None:
        """A5: 1.3 m/s is enforced by physics, not by the polite layer."""
        sim = make_sim(buoyancy_gf=0.0)
        cap = sim.cfg.max_speed_mps
        top = 0.0
        dt = 0.02
        next_send = 0.0
        for _ in range(int(20.0 / dt)):
            if sim.phys.t >= next_send:
                sim.set_manual_input(1.0, 0.0, 0.0)
                next_send = sim.phys.t + 0.3
            sim.tick(dt)
            p = sim.phys
            top = max(top, math.sqrt(p.vx**2 + p.vy**2 + p.vz**2))
        assert top <= cap + 0.02, f"hit {top:.3f} m/s, cap {cap}"
        assert top > 1.0, "should actually get near the cap with full thrust"

    def test_cap_engaged_flag_reports_the_governor(self) -> None:
        sim = make_sim(buoyancy_gf=0.0)
        assert sim.cap_engaged() is False
        engaged = False
        dt = 0.02
        next_send = 0.0
        for _ in range(int(15.0 / dt)):
            if sim.phys.t >= next_send:
                sim.set_manual_input(1.0, 0.0, 0.0)
                next_send = sim.phys.t + 0.3
            sim.tick(dt)
            engaged = engaged or sim.cap_engaged()
        assert engaged, "the governor never reported as binding at full thrust"


class TestZones:
    def test_manual_drive_into_zone_brakes_and_refuses(self) -> None:
        sim = make_sim(buoyancy_gf=0.0)
        # A wall-to-wall band ahead of the aircraft on its current heading.
        hdg = sim.phys.heading
        dx, dy = math.cos(hdg), math.sin(hdg)
        zx = sim.phys.x + dx * 2.5
        zy = sim.phys.y + dy * 2.5
        zone = Zone("the bedroom", zx - 1.0, zy - 6.0, 2.0, 12.0)
        sim.set_no_go_zones([zone])
        emissions = drive(sim, 12.0, forward=1.0, vertical=0.4)
        refused = [e for e in emissions if e[0] == topics.FLIGHT_REFUSED]
        assert refused, "driving at an off-limit zone must emit flight.refused"
        assert refused[0][1]["zone"] == "the bedroom"
        assert "off limits" in str(refused[0][1]["reason"])

    def test_manual_drive_never_enters_the_zone(self) -> None:
        sim = make_sim(buoyancy_gf=0.0)
        hdg = sim.phys.heading
        dx, dy = math.cos(hdg), math.sin(hdg)
        zone = Zone(
            "bathroom",
            sim.phys.x + dx * 2.5 - 1.0,
            sim.phys.y + dy * 2.5 - 6.0,
            2.0,
            12.0,
        )
        sim.set_no_go_zones([zone])
        dt = 0.02
        next_send = 0.0
        for _ in range(int(20.0 / dt)):
            if sim.phys.t >= next_send:
                sim.set_manual_input(1.0, 0.0, 0.0)
                next_send = sim.phys.t + 0.3
            sim.tick(dt)
            assert not zone.contains(sim.phys.x, sim.phys.y), (
                f"entered the zone at t={sim.phys.t:.2f}"
            )

    def test_refusals_are_rate_limited(self) -> None:
        sim = make_sim(buoyancy_gf=0.0)
        hdg = sim.phys.heading
        dx, dy = math.cos(hdg), math.sin(hdg)
        zone = Zone(
            "bathroom",
            sim.phys.x + dx * 2.0 - 1.0,
            sim.phys.y + dy * 2.0 - 6.0,
            2.0,
            12.0,
        )
        sim.set_no_go_zones([zone])
        emissions = drive(sim, 10.0, forward=1.0)
        refused = [e for e in emissions if e[0] == topics.FLIGHT_REFUSED]
        assert 1 <= len(refused) <= 5, f"{len(refused)} refusals in 10 s is a firehose"
