"""SimulatedBlimp: rounds, battery auto-return, bus contract, MQTT stub."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.flight.mqtt_blimp import MqttBlimp
from meemoo.flight.sim_blimp import Emission, FlightMode, SimulatedBlimp
from meemoo.flight.types import DockPhase

# Deterministic full-round seed (verified: undock → person waypoint →
# return → first-attempt capture, calm air). All RNG is seeded, so this
# is pinned, not flaky.
ROUND_SEED = 9


def make_sim(**kw: object) -> SimulatedBlimp:
    kw.setdefault("seed", ROUND_SEED)
    kw.setdefault("drafts_enabled", False)
    kw.setdefault("person_hold_s", 2.0)
    kw.setdefault("area_hold_s", 1.0)
    return SimulatedBlimp("apartment", **kw)  # type: ignore[arg-type]


def run_until(
    sim: SimulatedBlimp,
    pred: Callable[[SimulatedBlimp, list[Emission]], bool],
    *,
    max_sim_s: float,
    dt: float = 0.02,
) -> list[Emission]:
    events: list[Emission] = []
    while sim.phys.t < max_sim_s:
        events.extend(sim.tick(dt))
        if pred(sim, events):
            return events
    raise AssertionError(
        f"condition not reached by t={max_sim_s}s (mode={sim.mode}, "
        f"phase={sim.docking.phase})"
    )


class TestStartDocked:
    def test_starts_captured_two_signal(self) -> None:
        sim = make_sim()
        assert sim.mode is FlightMode.DOCKED
        cap = sim.dock.capture()
        assert cap.contact_continuity and cap.capture_switch and cap.confirmed

    def test_charges_on_dock(self) -> None:
        sim = make_sim()
        sim.phys.battery_pct = 50.0
        run_until(sim, lambda s, e: s.phys.battery_pct > 51.0, max_sim_s=60.0)
        assert sim.battery_status().charging

    def test_snapshot_shape(self) -> None:
        snap = make_sim().snapshot()
        d = snap.to_dict()
        for key in ("t", "x", "y", "phase", "battery_pct", "docked",
                    "net_buoyancy_gf", "helium_level_pct", "plan_name"):
            assert key in d
        assert d["docked"] is True


class TestFullRound:
    def test_dispatch_flies_the_round_and_redocks(self) -> None:
        """Undock → person waypoint (Guardian runs the REAL check-in while
        the sim holds) → return → two-signal capture → charging."""
        sim = make_sim()
        sim.dispatch("checkin")
        events = run_until(
            sim,
            lambda s, e: s.mode is FlightMode.DOCKED and s.phys.t > 20.0,
            max_sim_s=300.0,
        )
        names = [t for t, _ in events]
        assert topics.DOCK_RELEASED in names
        assert topics.FLIGHT_TAKEOFF in names
        wps = [p for t, p in events if t == topics.FLIGHT_WAYPOINT_REACHED]
        assert any(p["kind"] == "person" for p in wps)
        assert topics.DOCK_CAPTURED in names
        assert topics.FLIGHT_LANDED in names
        assert sim.dock.capture().confirmed

    def test_flight_state_transitions_published(self) -> None:
        sim = make_sim()
        sim.dispatch("verify")
        events = run_until(
            sim, lambda s, e: s.mode is FlightMode.ROUND, max_sim_s=60.0
        )
        phases = [p["phase"] for t, p in events if t == topics.FLIGHT_STATE]
        assert str(DockPhase.RELEASE) in phases


class TestBattery:
    def test_auto_return_below_threshold(self) -> None:
        sim = make_sim()
        sim.dispatch("checkin")
        run_until(sim, lambda s, e: s.mode is FlightMode.ROUND, max_sim_s=60.0)
        sim.phys.battery_pct = 24.0  # under the 25% line mid-round
        events = run_until(
            sim, lambda s, e: s.mode is FlightMode.RETURNING, max_sim_s=30.0
        )
        assert any(
            t == topics.FLIGHT_STATE and p.get("phase") == "AUTO_RETURN"
            for t, p in events
        )

    def test_battery_telemetry_emitted(self) -> None:
        sim = make_sim()
        events: list[Emission] = []
        for _ in range(int(12.0 / 0.02)):
            events.extend(sim.tick(0.02))
        assert any(t == topics.FLIGHT_BATTERY for t, _ in events)


class TestBusIntegration:
    async def test_consumes_flight_dispatch_and_publishes_round(self) -> None:
        """The Phase-5 SimWhale stand-in is retired: the REAL sim answers
        guardian dispatches with waypoint_reached events."""
        bus = EventBus()
        sim = make_sim()
        sub = bus.subscribe(topics.FLIGHT_WAYPOINT_REACHED, replay_last=False)
        runner = asyncio.create_task(sim.run(bus, dt=0.02, time_scale=2000.0))
        await asyncio.sleep(0.05)  # let the dispatch consumer subscribe
        await bus.publish(topics.FLIGHT_DISPATCH, {
            "device_id": 1, "reason": "verify", "target": "person",
        })
        try:
            event = await asyncio.wait_for(sub.get(), timeout=30.0)
            assert event.payload["kind"] == "person"
        finally:
            runner.cancel()
            with pytest.raises(asyncio.CancelledError):
                await runner
            sub.close()


class TestMqttStub:
    def test_every_method_raises_with_spec_pointer(self) -> None:
        blimp = MqttBlimp()
        calls = [
            blimp.takeoff, blimp.land, blimp.hold, blimp.return_to_dock,
            blimp.request_dock, blimp.abort_dock, blimp.request_undock,
            blimp.battery_status, blimp.position, blimp.net_buoyancy_gf,
        ]
        for call in calls:
            with pytest.raises(NotImplementedError, match="mqtt_blimp"):
                call()
        with pytest.raises(NotImplementedError, match="mqtt_blimp"):
            blimp.goto(1.0, 2.0)
        with pytest.raises(NotImplementedError, match="mqtt_blimp"):
            blimp.patrol([("a", "area", 1.0, 2.0)])

    def test_protocol_spec_is_in_the_docstring(self) -> None:
        import meemoo.flight.mqtt_blimp as m

        doc = m.__doc__ or ""
        for needle in ("ESP32-S3", "65 g", "120 L", "cmd/thrust", "tele/imu",
                       "video/announce", "negative", "mjpeg_url"):
            assert needle in doc, f"MQTT spec docstring missing {needle!r}"
