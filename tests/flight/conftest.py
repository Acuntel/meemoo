"""Shared flight-test helpers: a full randomized docking episode runner."""

from __future__ import annotations

import random
from dataclasses import dataclass

from meemoo.flight.constants import DockConfig, PhysicsConfig
from meemoo.flight.docking import DockingController
from meemoo.flight.floorplan import FloorPlan, load_plan
from meemoo.flight.physics import BlimpPhysics
from meemoo.flight.sim_dock import SimulatedDock
from meemoo.flight.types import DockPhase


@dataclass(slots=True)
class EpisodeResult:
    ok: bool
    retries: int
    sim_time_s: float
    single_signal_confirms: int  # MUST stay 0 — Art. II §3


def run_episode(
    seed: int,
    *,
    drafts: bool = True,
    cfg: PhysicsConfig | None = None,
    dcfg: DockConfig | None = None,
    plan: FloorPlan | None = None,
    max_attempts: int = 6,
    max_sim_s: float = 340.0,
    dt: float = 0.02,
) -> EpisodeResult:
    """One randomized docking episode (spec: buoyancy ±5 gf both signs,
    drafts on, random start pose) driven exactly like the real system:
    noisy pose + dock camera + two-signal capture telemetry only."""
    rng = random.Random(seed)
    cfg = cfg or PhysicsConfig()
    dcfg = dcfg or DockConfig()
    plan = plan or load_plan("apartment")
    buoy = rng.uniform(-cfg.buoyancy_episode_range_gf, cfg.buoyancy_episode_range_gf)
    phys = BlimpPhysics(cfg, plan, seed=seed, buoyancy_gf=buoy, drafts_enabled=drafts)
    x0, y0, x1, y1 = plan.bounds
    phys.x = rng.uniform(x0 + 0.5, x1 - 0.5)
    phys.y = rng.uniform(y0 + 0.5, y1 - 0.5)
    phys.z = rng.uniform(0.6, 1.8)
    phys.heading = rng.uniform(-3.14, 3.14)
    dock = SimulatedDock(plan.dock, dcfg, seed=seed)
    ctl = DockingController(cfg, dcfg, plan.dock, max_attempts=max_attempts)
    ctl.request_dock()
    pose_rng = random.Random(seed ^ 77)
    t = 0.0
    bad_confirms = 0
    while t < max_sim_s:
        pose = phys.pose(noise_m=0.05, rng=pose_rng)
        rel = dock.observe(phys)
        cap = dock.capture()
        if cap.confirmed and not (cap.contact_continuity and cap.capture_switch):
            bad_confirms += 1
        out = ctl.drive(pose, rel, cap, phys.battery_pct, dt,
                        buoyancy_est_gf=phys.net_buoyancy_est_gf)
        dock.set_retention(out.retention)
        dock.set_charge_enabled(out.charge_enabled)
        phys.command(out.cmd)
        phys.step(dt)
        dock.interact(phys, dt)
        if ctl.docked:
            return EpisodeResult(True, ctl.retries, t, bad_confirms)
        if ctl.phase is DockPhase.DOCK_FAILED:
            return EpisodeResult(False, ctl.retries, t, bad_confirms)
        t += dt
    return EpisodeResult(False, ctl.retries, t, bad_confirms)
