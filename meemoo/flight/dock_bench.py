"""2D docking Monte-Carlo bench — the honest Phase-6 gate measurement.

Runs the SAME episode contract ``sim3d/experiment.py`` flies in MuJoCo, so
the two engines are comparable line for line: random start pose, buoyancy
drawn from ±5 gf (both signs, drifting), HVAC drafts on, σ-5 cm room pose,
20 Hz dock camera, 100 ms command latency, 6 attempts max.

    uv run python -m meemoo.flight.dock_bench --episodes 200   # ~35 s

DO NOT tune the episode contract or the physics to make a controller look
better (Constitution Art. II §4). The numbers ARE the deliverable —
docs/PHYSICS_VALIDATION.md carries them beside the MuJoCo column.

``run_episode`` is the canonical 2D episode; tests/flight imports it.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

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
    seed: int = -1
    buoyancy_gf: float = 0.0
    end_phase: str = ""
    mouth_entries: int = 0
    replans: int = 0  # in-approach corrections (never a retreat to standoff)
    aborts_from: dict[str, int] = field(default_factory=dict)
    abort_reasons: dict[str, int] = field(default_factory=dict)

    @property
    def failure_mode(self) -> str:
        if self.ok:
            return "captured"
        if self.end_phase == "DOCK_FAILED":
            return "max_attempts"
        return f"timeout_{self.end_phase}"


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
    entries = 0
    was_in = False
    aborts: dict[str, int] = {}
    while t < max_sim_s:
        pose = phys.pose(noise_m=0.05, rng=pose_rng)
        rel = dock.observe(phys)
        cap = dock.capture()
        if cap.confirmed and not (cap.contact_continuity and cap.capture_switch):
            bad_confirms += 1
        out = ctl.drive(pose, rel, cap, phys.battery_pct, dt,
                        buoyancy_est_gf=phys.net_buoyancy_est_gf)
        for prev, new in out.transitions:
            if new is DockPhase.ABORT:
                aborts[str(prev)] = aborts.get(str(prev), 0) + 1
        dock.set_retention(out.retention)
        dock.set_charge_enabled(out.charge_enabled)
        phys.command(out.cmd)
        phys.step(dt)
        dock.interact(phys, dt)
        if dock.in_funnel and not was_in:
            entries += 1
        was_in = dock.in_funnel
        if ctl.docked or ctl.phase is DockPhase.DOCK_FAILED:
            break
        t += dt
    return EpisodeResult(
        ok=ctl.docked, retries=ctl.retries, sim_time_s=t,
        single_signal_confirms=bad_confirms, seed=seed, buoyancy_gf=buoy,
        end_phase=str(ctl.phase), mouth_entries=entries,
        replans=ctl.replans, aborts_from=aborts,
        abort_reasons=dict(ctl.abort_reasons),
    )


# ---------------------------------------------------------------- summaries
def success_rates(results: list[EpisodeResult]) -> dict[str, float]:
    n = max(1, len(results))
    first = sum(1 for r in results if r.ok and r.retries == 0)
    within1 = sum(1 for r in results if r.ok and r.retries <= 1)
    any_ok = sum(1 for r in results if r.ok)
    return {
        "episodes": float(len(results)),
        "first_attempt": first / n,
        "within_one_retry": within1 / n,
        "within_max_attempts": any_ok / n,
    }


def summarize(results: list[EpisodeResult]) -> dict[str, Any]:
    ok_times = sorted(r.sim_time_s for r in results if r.ok)
    aborts: dict[str, int] = {}
    for r in results:
        for k, v in r.aborts_from.items():
            aborts[k] = aborts.get(k, 0) + v
    reasons: dict[str, int] = {}
    for r in results:
        for k, v in r.abort_reasons.items():
            reasons[k] = reasons.get(k, 0) + v
    modes: dict[str, int] = {}
    for r in results:
        modes[r.failure_mode] = modes.get(r.failure_mode, 0) + 1
    return {
        "rates": success_rates(results),
        "failure_modes": dict(sorted(modes.items(), key=lambda kv: -kv[1])),
        "aborts_from": dict(sorted(aborts.items(), key=lambda kv: -kv[1])),
        "abort_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        "mouth_entries": sum(r.mouth_entries for r in results),
        "replans": sum(r.replans for r in results),
        "time_to_dock_s": {
            "median": round(ok_times[len(ok_times) // 2], 1) if ok_times else None,
            "p90": round(ok_times[int(0.9 * (len(ok_times) - 1))], 1)
            if ok_times else None,
        },
        "episodes_detail": [asdict(r) for r in results],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--hz", type=float, default=50.0, help="control rate")
    ap.add_argument("--no-drafts", action="store_true", help="calm-air cell")
    ap.add_argument("--out", type=Path, default=Path("docs/assets"))
    args = ap.parse_args()

    results = []
    for seed in range(args.episodes):
        results.append(run_episode(seed, drafts=not args.no_drafts, dt=1.0 / args.hz))
        if (seed + 1) % 25 == 0:
            r = success_rates(results)
            print(  # noqa: T201 - CLI progress is this tool's UI
                f"[2D {args.hz:.0f} Hz {seed + 1}/{args.episodes}] "
                f"first={r['first_attempt']:.0%} any={r['within_max_attempts']:.0%}"
            )
    payload = {f"hz{args.hz:.0f}{'_calm' if args.no_drafts else ''}":
               summarize(results)}
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "physics2d_results.json"
    if path.exists():  # keep the other cells (rates/calm-air) in one file
        payload = {**json.loads(path.read_text()), **payload}
    path.write_text(json.dumps(payload, indent=2))
    brief = {k: {kk: vv for kk, vv in v.items() if kk != "episodes_detail"}
             for k, v in payload.items()}
    print(json.dumps(brief, indent=2))  # noqa: T201
    print(f"wrote {path}")  # noqa: T201


if __name__ == "__main__":
    main()
