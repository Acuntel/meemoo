"""SimulatedBlimp — the v1 FlightController against honest physics.

The 2D floor-plan aircraft the rest of Meemoo flies until hardware exists.
Composition (never conflated, Art. II §3): :class:`BlimpPhysics` (airframe
truth), :class:`SimulatedDock` (the dock device), :class:`DockingController`
(base-station brain), :class:`WorldNav` (round flying with floaty easing).

Bus contract (Art. II §2): consumes ``flight.dispatch``; emits
``flight.takeoff`` / ``flight.waypoint_reached`` / ``flight.battery`` /
``flight.landed`` / ``flight.state`` and ``dock.captured`` / ``dock.released``
/ ``dock.charging``. During a person waypoint the sim only HOLDS position —
the Guardian runs the REAL voice check-in (the sim is fake; the check-in is
real).

``tick()`` is synchronous and returns the emissions it would publish, so
tests and the Monte-Carlo gate run faster than real time; ``run()`` is the
real-time async loop that actually publishes them.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random

from meemoo.core import topics
from meemoo.core.bus import EventBus
from meemoo.flight.constants import DockConfig, PhysicsConfig
from meemoo.flight.controller import FlightController
from meemoo.flight.docking import DockingController
from meemoo.flight.floorplan import FloorPlan, load_plan
from meemoo.flight.mission import Emission as Emission  # re-export
from meemoo.flight.mission import FlightMode as FlightMode  # re-export
from meemoo.flight.mission import MissionMixin
from meemoo.flight.nav import WorldNav
from meemoo.flight.physics import BlimpPhysics
from meemoo.flight.sim_dock import SimulatedDock
from meemoo.flight.types import BatteryStatus, DockPhase, Pose, SimSnapshot
from meemoo.flight.zones import Zone, refusal_payload, split_route, zone_containing

logger = logging.getLogger(__name__)


class SimulatedBlimp(MissionMixin, FlightController):
    """One simulated aircraft + its dock on one floor plan."""

    def __init__(
        self,
        plan: FloorPlan | str = "apartment",
        *,
        physics: PhysicsConfig | None = None,
        dock_config: DockConfig | None = None,
        seed: int = 0,
        buoyancy_gf: float | None = None,
        drafts_enabled: bool = True,
        start_docked: bool = True,
        person_hold_s: float = 12.0,
        area_hold_s: float = 2.0,
        pose_noise_m: float = 0.05,
        device_id: int = 1,
    ) -> None:
        self.plan = plan if isinstance(plan, FloorPlan) else load_plan(plan)
        self.cfg = physics or PhysicsConfig()
        self.phys = BlimpPhysics(
            self.cfg, self.plan, seed=seed,
            buoyancy_gf=buoyancy_gf, drafts_enabled=drafts_enabled,
        )
        self.dock = SimulatedDock(self.plan.dock, dock_config, seed=seed)
        self.nav = WorldNav(self.cfg)
        self.docking = DockingController(self.cfg, self.dock.cfg, self.plan.dock)
        self.device_id = device_id
        self.person_hold_s = person_hold_s
        self.area_hold_s = area_hold_s
        self._pose_rng = random.Random(seed ^ 0xA11CE)
        self._pose_noise_m = pose_noise_m
        self.mode = FlightMode.HOLD
        self.no_go_zones: list[Zone] = []
        self._pending_emissions: list[Emission] = []
        self._route: list[tuple[str, str, float, float]] = []
        self._route_idx = 0
        self._hold_until = 0.0
        self._hold_target: tuple[float, float, float] = (self.phys.x, self.phys.y, self.phys.z)
        self._pending_round: list[tuple[str, str, float, float]] | None = None
        self._last_battery_emit = -1e9
        self._low_battery_fired = False
        if start_docked:
            self.dock.force_capture(self.phys)
            self.docking.phase = DockPhase.CHARGING
            self.mode = FlightMode.DOCKED

    # ------------------------------------------------ FlightController API
    def takeoff(self) -> None:
        if self.mode is FlightMode.DOCKED:
            self._pending_round = []
            self.docking.request_undock()
            self.mode = FlightMode.UNDOCKING
        elif self.mode is FlightMode.LANDED:
            self.phys.motors_on = True
            self._hold_target = (self.phys.x, self.phys.y, 1.2)
            self.mode = FlightMode.HOLD

    def land(self) -> None:
        self._hold_target = (self.phys.x, self.phys.y, 0.12)
        self.mode = FlightMode.GOTO
        self._route = [("land", "land", self.phys.x, self.phys.y)]
        self._route_idx = 0

    def goto(self, x: float, y: float, *, label: str | None = None) -> bool:
        """Fly to a point; refused (False + flight.refused event) in a zone."""
        zone = zone_containing(self.no_go_zones, x, y)
        if zone is not None:
            logger.info("flight: goto refused — %s is off limits", zone.name)
            self._pending_emissions.append((topics.FLIGHT_REFUSED, refusal_payload(
                self.device_id, zone, label=label or "goto", x=x, y=y,
            )))
            return False
        self._route = [(label or "goto", "area", x, y)]
        self._route_idx = 0
        self._start_flying(FlightMode.GOTO)
        return True

    def patrol(self, waypoints: list[tuple[str, str, float, float]]) -> None:
        allowed, refusals = split_route(self.no_go_zones, self.device_id, waypoints)
        for payload in refusals:
            logger.info("flight: waypoint %r dropped — off-limit zone", payload["label"])
            self._pending_emissions.append((topics.FLIGHT_REFUSED, payload))
        if not allowed:
            return
        self._route = allowed
        self._route_idx = 0
        self._start_flying(FlightMode.ROUND)

    def set_no_go_zones(self, zones: list[Zone]) -> None:
        """Replace the active off-limit zone list (Amendment A3)."""
        self.no_go_zones = list(zones)

    def hold(self) -> None:
        self._hold_target = (self.phys.x, self.phys.y, self.phys.z)
        self.mode = FlightMode.HOLD

    def return_to_dock(self) -> None:
        self.request_dock()

    def request_dock(self) -> None:
        if self.mode not in (FlightMode.DOCKED, FlightMode.UNDOCKING):
            self.docking.request_dock()
            self.mode = FlightMode.RETURNING

    def abort_dock(self) -> None:
        self.docking.abort()

    def request_undock(self) -> None:
        if self.mode is FlightMode.DOCKED:
            self.docking.request_undock()
            self.mode = FlightMode.UNDOCKING

    def battery_status(self) -> BatteryStatus:
        pct = self.phys.battery_pct
        charging = self.dock.charge(pct).charge_state in ("bulk", "topping")
        minutes = pct / 100.0 * self.cfg.battery_flight_s / 60.0
        return BatteryStatus(pct=pct, charging=charging, minutes_remaining=minutes)

    def position(self) -> Pose:
        return self.phys.pose(noise_m=self._pose_noise_m, rng=self._pose_rng)

    def net_buoyancy_gf(self) -> float:
        return self.phys.net_buoyancy_est_gf

    # -------------------------------------------------------------- mission
    def _start_flying(self, mode: FlightMode) -> None:
        if self.mode is FlightMode.DOCKED:
            self._pending_round = list(self._route)
            self.docking.request_undock()
            self.mode = FlightMode.UNDOCKING
        else:
            self.mode = mode

    def dispatch(self, reason: str = "checkin") -> None:
        """Fly the round the Guardian asked for: all person waypoints."""
        wps = [
            (w.label, w.kind, w.x, w.y)
            for w in (self.plan.person_waypoints() or self.plan.waypoints)
        ]
        logger.info("flight: dispatch (%s) — %d waypoint(s)", reason, len(wps))
        self.patrol(wps)

    # ------------------------------------------------------------------ tick
    def tick(self, dt: float) -> list[Emission]:
        out: list[Emission] = self._pending_emissions
        self._pending_emissions = []
        pose = self.position()
        relpose = self.dock.observe(self.phys)
        capture = self.dock.capture()

        if self.mode in (FlightMode.DOCKED, FlightMode.UNDOCKING, FlightMode.RETURNING):
            dk = self.docking.drive(
                pose, relpose, capture, self.phys.battery_pct, dt,
                buoyancy_est_gf=self.phys.net_buoyancy_est_gf,
            )
            self.dock.set_retention(dk.retention)
            self.dock.set_charge_enabled(dk.charge_enabled)
            self.phys.command(dk.cmd)
            for prev, new in dk.transitions:
                out.append((topics.FLIGHT_STATE, {
                    "device_id": self.device_id, "phase": str(new),
                    "prev": str(prev), "retries": self.docking.retries,
                }))
                out.extend(self._on_dock_phase(new))
        else:
            self.phys.command(self._fly(pose, dt))

        self.phys.step(dt)
        self.dock.interact(self.phys, dt)
        self._charge_battery(dt)
        out.extend(self._mode_progress())
        out.extend(self._battery_watch(dt))
        return out

    def _on_dock_phase(self, new: DockPhase) -> list[Emission]:
        dev: dict[str, object] = {"device_id": self.device_id}
        if new is DockPhase.CAPTURED:
            self.mode = FlightMode.DOCKED
            return [(topics.DOCK_CAPTURED, dev),
                    (topics.FLIGHT_LANDED, {**dev, "where": "dock"})]
        if new is DockPhase.CHARGING:
            return [(topics.DOCK_CHARGING, dev)]
        if new is DockPhase.FLYING and self.mode is FlightMode.UNDOCKING:
            pending, self._pending_round = self._pending_round, None
            if pending:
                self._route = pending
                self._route_idx = 0
                self.mode = FlightMode.ROUND
            else:
                self.hold()
            return [(topics.DOCK_RELEASED, dev), (topics.FLIGHT_TAKEOFF, dev)]
        if new is DockPhase.DOCK_FAILED:
            self.hold()
            return [(topics.FLIGHT_STATE, {**dev, "phase": "DOCK_FAILED", "terminal": True})]
        return []

    def _charge_battery(self, dt: float) -> None:
        state = self.dock.charge(self.phys.battery_pct).charge_state
        if state in ("bulk", "topping"):
            rate = 100.0 / self.cfg.battery_charge_s
            self.phys.battery_pct = min(100.0, self.phys.battery_pct + rate * dt)

    # ------------------------------------------------------------- snapshot
    def snapshot(self) -> SimSnapshot:
        label = None
        if self.mode in (FlightMode.ROUND, FlightMode.GOTO) and self._route_idx < len(
            self._route
        ):
            label = self._route[self._route_idx][0]
        return SimSnapshot(
            t=self.phys.t, x=self.phys.x, y=self.phys.y, z=self.phys.z,
            heading_deg=self.phys.heading * 57.29578,
            swing_deg=self.phys.swing * 57.29578,
            phase=str(self.docking.phase) if self.mode in (
                FlightMode.DOCKED, FlightMode.UNDOCKING, FlightMode.RETURNING
            ) else str(self.mode),
            battery_pct=self.phys.battery_pct,
            charging=self.battery_status().charging,
            docked=self.docking.docked,
            net_buoyancy_gf=self.phys.net_buoyancy_true_gf,
            helium_level_pct=self.dock.helium_level_pct,
            retries=self.docking.retries,
            plan_name=self.plan.name,
            waypoint_label=label,
        )

    # ------------------------------------------------------------ async run
    async def run(
        self, bus: EventBus, *, dt: float = 0.02, time_scale: float = 1.0
    ) -> None:
        """Real-time loop: step, publish emissions, consume flight.dispatch."""
        sub = bus.subscribe(topics.FLIGHT_DISPATCH, replay_last=False)

        async def _consume() -> None:
            async for event in sub:
                self.dispatch(str(event.payload.get("reason", "checkin")))

        consumer = asyncio.create_task(_consume())
        try:
            while True:
                for topic, payload in self.tick(dt):
                    await bus.publish(topic, payload)
                await asyncio.sleep(dt / time_scale)
        finally:
            consumer.cancel()
            sub.close()
            with contextlib.suppress(asyncio.CancelledError):
                await consumer
