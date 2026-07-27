"""Voice motion commands executed against the HONEST sim (Amendment A5).

The voice layer publishes typed ``flight.command`` events; these prove the
sim does the right thing with them: stop preempts whatever was in progress,
off-limit zones still win, and the 1.3 m/s cap is enforced by the physics
rather than promised by the controller.
"""

from __future__ import annotations

import asyncio
import contextlib
import math

import pytest

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.flight.capabilities import FlightCommand, MotionKind
from meemoo.flight.commands import SPIN_S
from meemoo.flight.constants import PhysicsConfig
from meemoo.flight.floorplan import load_plan
from meemoo.flight.physics import BlimpPhysics
from meemoo.flight.sim_blimp import FlightMode, SimulatedBlimp
from meemoo.flight.types import ThrustCommand
from meemoo.flight.zones import Zone


def flying_sim(**kwargs: object) -> SimulatedBlimp:
    """A blimp already in the air, holding station (no docking in the way)."""
    sim = SimulatedBlimp(
        "apartment", seed=1, drafts_enabled=False, start_docked=False, **kwargs  # type: ignore[arg-type]
    )
    sim.mode = FlightMode.HOLD
    return sim


def command(kind: MotionKind, **kwargs: object) -> FlightCommand:
    return FlightCommand(command=kind.value, **kwargs)  # type: ignore[arg-type]


def run(
    sim: SimulatedBlimp, seconds: float, dt: float = 0.02
) -> list[tuple[str, dict[str, object]]]:
    out: list[tuple[str, dict[str, object]]] = []
    for _ in range(int(seconds / dt)):
        out.extend(sim.tick(dt))
    return out


def speed(sim: SimulatedBlimp) -> float:
    return math.hypot(sim.phys.vx, sim.phys.vy)


def mode(sim: SimulatedBlimp) -> FlightMode:
    """Read the mode fresh — ticking changes it, so never narrow across a run."""
    return sim.mode


class TestSpeedCap:
    """Art. II §4: the cap lives in the physics, not in a controller promise."""

    def test_full_thrust_never_exceeds_the_cap(self) -> None:
        cfg = PhysicsConfig()
        assert cfg.max_speed_mps == 1.3  # Amendment A5
        phys = BlimpPhysics(cfg, load_plan("apartment"), seed=3,
                            buoyancy_gf=0.0, drafts_enabled=False)
        peak = 0.0
        for _ in range(4000):  # 80 s of pinned forward thrust
            phys.command(ThrustCommand(forward_gf=20.0))
            phys.step(0.02)
            peak = max(peak, math.hypot(phys.vx, phys.vy))
            if phys.x > 6.0 or phys.y > 6.0:  # keep it off the walls
                phys.x, phys.y = 0.5, 0.5
        assert peak <= cfg.max_speed_mps * 1.02

    def test_the_cap_is_what_binds_not_drag(self) -> None:
        """Without the governor the airframe WOULD go faster: the cap bites."""
        plan = load_plan("apartment")
        uncapped = BlimpPhysics(PhysicsConfig(max_speed_mps=99.0), plan, seed=3,
                                buoyancy_gf=0.0, drafts_enabled=False)
        peak = 0.0
        for _ in range(4000):
            uncapped.command(ThrustCommand(forward_gf=20.0))
            uncapped.step(0.02)
            peak = max(peak, math.hypot(uncapped.vx, uncapped.vy))
            if uncapped.x > 6.0 or uncapped.y > 6.0:
                uncapped.x, uncapped.y = 0.5, 0.5
        assert peak > 1.3  # drag alone would let it run to ~1.4 m/s

    def test_a_real_flight_stays_under_the_cap(self) -> None:
        sim = flying_sim()
        sim.goto(6.6, 4.6, label="Ruth's chair")
        for _ in range(2000):
            sim.tick(0.02)
            assert speed(sim) <= sim.cfg.max_speed_mps * 1.02


class TestStop:
    def test_stop_preempts_an_in_progress_goto(self) -> None:
        sim = flying_sim()
        assert sim.goto(5.0, 3.0, label="kitchen") is True
        run(sim, 4.0)
        assert mode(sim) is FlightMode.GOTO and speed(sim) > 0.15  # really flying

        assert sim.execute_command(command(MotionKind.STOP)) is True
        # one control cycle: the mission is gone and the target is a stop point
        assert mode(sim) is FlightMode.HOLD
        assert sim._route == []  # noqa: SLF001
        assert sim._pending_round is None  # noqa: SLF001

    def test_stop_brings_it_to_rest(self) -> None:
        sim = flying_sim()
        sim.goto(5.0, 3.0, label="kitchen")
        run(sim, 4.0)
        moving = speed(sim)
        sim.execute_command(command(MotionKind.STOP))
        run(sim, 4.0)
        assert speed(sim) < moving / 4.0  # added mass means it coasts, honestly

    def test_stop_aims_ahead_not_backwards(self) -> None:
        """After "stop" Meemoo must not fly BACK to where the word was said."""
        sim = flying_sim()
        sim.goto(6.6, 4.6, label="Ruth's chair")
        run(sim, 4.0)
        heading_x, heading_y = sim.phys.vx, sim.phys.vy
        here = (sim.phys.x, sim.phys.y)
        sim.execute_command(command(MotionKind.STOP))
        tx, ty, _tz = sim._hold_target  # noqa: SLF001
        assert (tx - here[0]) * heading_x + (ty - here[1]) * heading_y >= 0.0

    def test_stop_never_coasts_into_an_off_limit_zone(self) -> None:
        sim = flying_sim()
        sim.set_no_go_zones([Zone("the bathroom", 0.0, 0.0, 10.0, 10.0)])  # everywhere
        sim.goto(5.0, 3.0)  # refused, so drive it by hand
        sim.phys.vx, sim.phys.vy = 0.8, 0.0
        here = (sim.phys.x, sim.phys.y, sim.phys.z)
        sim.execute_command(command(MotionKind.STOP))
        assert sim._hold_target == here  # noqa: SLF001

    def test_stop_cancels_a_spin(self) -> None:
        sim = flying_sim()
        sim.execute_command(command(MotionKind.SPIN))
        run(sim, 1.0)
        sim.execute_command(command(MotionKind.STOP))
        assert sim._spin_until == 0.0  # noqa: SLF001

    def test_stop_lets_a_capture_finish(self) -> None:
        """Art. II §3: a stop may cancel an approach, never a capture."""
        sim = SimulatedBlimp("apartment", seed=1, start_docked=True)
        phase_before = sim.docking.phase
        sim.execute_command(command(MotionKind.STOP))
        assert mode(sim) is FlightMode.DOCKED
        assert sim.docking.phase is phase_before


class TestZonesStillWin:
    def test_voice_goto_into_a_zone_is_refused(self) -> None:
        sim = flying_sim()
        sim.set_no_go_zones([Zone("the bathroom", 4.0, 0.0, 2.0, 2.0)])
        accepted = sim.execute_command(
            command(MotionKind.GOTO, label="bathroom", x=5.0, y=1.0)
        )
        assert accepted is False
        emissions = sim.tick(0.02)
        refusals = [p for t, p in emissions if t == topics.FLIGHT_REFUSED]
        assert len(refusals) == 1
        assert refusals[0]["zone"] == "the bathroom"
        assert refusals[0]["reason"] == "the bathroom is off limits, so Meemoo stays out"
        assert mode(sim) is FlightMode.HOLD  # it never left

    def test_drift_into_a_zone_is_refused(self) -> None:
        sim = flying_sim()
        sim.phys.heading = 0.0
        # a wall of zone immediately to Meemoo's left (+90 deg from heading)
        sim.set_no_go_zones([Zone("the bathroom", 0.0, sim.phys.y + 0.2, 10.0, 5.0)])
        assert sim.execute_command(command(MotionKind.MOVE, direction="left")) is False
        refusals = [p for t, p in sim.tick(0.02) if t == topics.FLIGHT_REFUSED]
        assert len(refusals) == 1 and refusals[0]["label"] == "drift left"


class TestTheRestOfTheGrammar:
    @pytest.mark.parametrize("direction", ["left", "right", "up", "down"])
    def test_drift_moves_the_hold_target(self, direction: str) -> None:
        sim = flying_sim()
        before = sim._hold_target  # noqa: SLF001
        assert sim.execute_command(command(MotionKind.MOVE, direction=direction)) is True
        after = sim._hold_target  # noqa: SLF001
        assert after != before
        if direction in ("up", "down"):
            assert after[:2] == before[:2]  # vertical only
            assert (after[2] > before[2]) is (direction == "up")
        else:
            assert after[2] == before[2]  # horizontal only

    def test_an_unknown_direction_is_not_flown(self) -> None:
        sim = flying_sim()
        assert sim.execute_command(command(MotionKind.MOVE, direction="sideways")) is False

    def test_come_here_flies_to_the_nearest_person(self) -> None:
        sim = flying_sim()
        assert sim.execute_command(command(MotionKind.COME_HERE)) is True
        assert mode(sim) is FlightMode.GOTO
        people = {(w.x, w.y) for w in sim.plan.person_waypoints()}
        label, _kind, x, y = sim._route[0]  # noqa: SLF001
        assert (x, y) in people

    def test_spin_turns_in_place_then_resumes(self) -> None:
        sim = flying_sim()
        assert sim.execute_command(command(MotionKind.SPIN)) is True
        anchor = sim._spin_anchor  # noqa: SLF001
        turned = 0.0
        previous = sim.phys.heading
        for _ in range(int(SPIN_S / 0.02)):
            sim.tick(0.02)
            step = sim.phys.heading - previous
            turned += (step + math.pi) % (2.0 * math.pi) - math.pi
            previous = sim.phys.heading
        assert abs(turned) > math.pi  # at least half a turn: it visibly spun
        assert math.hypot(sim.phys.x - anchor[0], sim.phys.y - anchor[1]) < 0.25
        run(sim, 1.0)
        assert sim.phys.t >= sim._spin_until  # noqa: SLF001 — back to the mission

    def test_spin_emits_a_state_event_for_the_ui(self) -> None:
        sim = flying_sim()
        sim.execute_command(command(MotionKind.SPIN))
        phases = [p.get("phase") for t, p in sim.tick(0.02) if t == topics.FLIGHT_STATE]
        assert "TRICK_SPIN" in phases

    def test_dock_command_sends_it_home(self) -> None:
        sim = flying_sim()
        assert sim.execute_command(command(MotionKind.DOCK)) is True
        assert mode(sim) is FlightMode.RETURNING

    def test_docked_meemoo_declines_to_drift_or_spin(self) -> None:
        sim = SimulatedBlimp("apartment", seed=1, start_docked=True)
        assert sim.execute_command(command(MotionKind.MOVE, direction="left")) is False
        assert sim.execute_command(command(MotionKind.SPIN)) is False


class TestBusContract:
    async def test_a_published_command_is_executed(self) -> None:
        """The real wiring: voice publishes, the sim's run loop executes."""
        bus = EventBus()
        sim = flying_sim()
        task = asyncio.create_task(sim.run(bus, dt=0.02))
        try:
            while bus.subscriber_count == 0:  # let the loop subscribe first
                await asyncio.sleep(0.01)
            await bus.publish(
                topics.FLIGHT_COMMAND,
                FlightCommand(command=MotionKind.GOTO.value, label="kitchen",
                              x=5.0, y=1.5).payload(),
            )
            for _ in range(50):
                await asyncio.sleep(0.01)
                if sim.mode is FlightMode.GOTO:
                    break
            assert mode(sim) is FlightMode.GOTO
            assert sim._route[0][0] == "kitchen"  # noqa: SLF001
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    def test_a_malformed_payload_is_ignored_not_raised(self) -> None:
        sim = flying_sim()
        sim.on_command({"command": "explode"})
        sim.on_command({})
        sim.on_command({"command": "goto"})  # no coordinates
        assert mode(sim) is FlightMode.HOLD

    def test_another_devices_command_is_ignored(self) -> None:
        sim = flying_sim()
        sim.on_command({"command": MotionKind.SPIN.value, "device_id": 99})
        assert sim._spin_until == 0.0  # noqa: SLF001
