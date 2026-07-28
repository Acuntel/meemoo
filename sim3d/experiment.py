"""The cross-validation experiment: the UNMODIFIED 2D docking controller
flown against the MuJoCo rig.

Usage (see sim3d/README.md; `make physics3d` runs the full set):

    uv run --group physics3d python -m sim3d.experiment \
        --episodes 200 --bumps 50 --out docs/assets

DO NOT tune the controller here. If it fails in MuJoCo, the failure modes
and numbers ARE the deliverable (docs/PHYSICS_VALIDATION.md).
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any

from meemoo.flight.docking import DockingController
from meemoo.flight.nav import NavGains, WorldNav
from meemoo.flight.types import DockPhase
from sim3d.adapter import Blimp3DAdapter, controller_physics_config, dock_pose
from sim3d.spec import (
    BumpResult,
    Episode3DResult,
    Rig3DConfig,
    failure_histogram,
    success_rates,
)
from sim3d.world import MjWorld

Trace = list[tuple[float, float, float, float, str]]  # t, x, y, z, phase


def run_episode3d(
    seed: int,
    *,
    control_hz: float = 10.0,
    drafts: bool = True,
    max_sim_s: float = 340.0,
    max_attempts: int = 6,
    rig: Rig3DConfig | None = None,
    trace: Trace | None = None,
) -> Episode3DResult:
    """One randomized docking episode: start within 3 m, buoyancy +-5 gf
    both signs, drafts on — the same contract as the 2D gate runner."""
    rig = rig or Rig3DConfig()
    rng = random.Random(seed)
    buoy = rng.uniform(-rig.buoyancy_range_gf, rig.buoyancy_range_gf)
    world = MjWorld(rig, seed=seed, buoyancy_gf=buoy, drafts_enabled=drafts)
    adapter = Blimp3DAdapter(world, seed=seed)
    dist = rng.uniform(1.0, 3.0)
    ang = rng.uniform(-1.05, 1.05)  # within +-60 deg of the dock axis
    x = max(0.8, dist * math.cos(ang))
    y = max(-2.6, min(2.6, dist * math.sin(ang)))
    world.reset_pose(x, y, rng.uniform(0.6, 1.8), rng.uniform(-math.pi, math.pi))
    ctl = DockingController(
        controller_physics_config(rig), adapter.dcfg, dock_pose(rig),
        max_attempts=max_attempts,
    )
    ctl.request_dock()
    dt = 1.0 / control_hz
    t = 0.0
    aborts: dict[str, int] = {}
    while t < max_sim_s:
        out = ctl.drive(
            adapter.pose(), adapter.observe(), adapter.capture(), 80.0, dt,
            buoyancy_est_gf=adapter.net_buoyancy_est_gf,
        )
        for prev, new in out.transitions:
            if new is DockPhase.ABORT:
                aborts[str(prev)] = aborts.get(str(prev), 0) + 1
        adapter.set_retention(out.retention)
        adapter.set_charge_enabled(out.charge_enabled)
        adapter.command(out.cmd)
        adapter.step(dt)
        t += dt
        if trace is not None:
            cx, cy, cz = world.center_pos
            trace.append((t, cx, cy, cz, str(ctl.phase)))
        if ctl.docked or ctl.phase is DockPhase.DOCK_FAILED:
            break
    return Episode3DResult(
        seed=seed, ok=ctl.docked, retries=ctl.retries, sim_time_s=t,
        buoyancy_gf=buoy, end_phase=str(ctl.phase),
        mouth_entries=world.mouth_entries,
        contact_speed_mps=world.last_entry_speed,
        min_tip_throat_m=world.min_tip_throat, aborts_from=aborts,
    )


def run_bump(
    seed: int,
    *,
    damper: bool,
    control_hz: float = 50.0,
    rig: Rig3DConfig | None = None,
    trace: list[tuple[float, float]] | None = None,
) -> BumpResult:
    """Hover, shove 1 N for 0.2 s, measure pendulum settle (drafts off,
    neutral trim, so the pendulum is isolated)."""
    rig = rig or Rig3DConfig()
    rng = random.Random(seed)
    world = MjWorld(rig, seed=seed, buoyancy_gf=0.0, drafts_enabled=False)
    world.buoyancy_gf = 0.0
    adapter = Blimp3DAdapter(world, seed=seed)
    world.reset_pose(2.0, 0.0, 1.2, 0.0)
    gains = NavGains() if damper else NavGains(swing_damp_gf=0.0)
    nav = WorldNav(controller_physics_config(rig), gains=gains)
    az = rng.uniform(0.0, 2.0 * math.pi)
    shove = (math.cos(az), math.sin(az), 0.0)
    dt = 1.0 / control_hz
    warmup_s, shove_s, window_s = 8.0, 0.2, 60.0
    t = 0.0
    max_tilt = 0.0
    settled_since: float | None = None
    settle_at: float | None = None
    while t < warmup_s + shove_s + window_s:
        cmd = nav.hover_command(adapter.pose(), 2.0, 0.0, 1.2, dt)
        adapter.command(cmd)
        shoving = warmup_s <= t < warmup_s + shove_s
        adapter.step(dt, external_force_n=shove if shoving else None)
        t += dt
        rot = world.rotation()
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, float(rot[2, 2])))))
        if trace is not None and t >= warmup_s - 1.0:
            trace.append((t - warmup_s, tilt))
        if t < warmup_s + shove_s:
            continue
        max_tilt = max(max_tilt, tilt)
        if tilt < 2.0:
            settled_since = settled_since if settled_since is not None else t
            if t - settled_since >= 3.0 and settle_at is None:
                settle_at = settled_since - (warmup_s + shove_s)
                break
        else:
            settled_since = None
    return BumpResult(seed=seed, damper=damper, settle_s=settle_at,
                      max_tilt_deg=max_tilt)


# ---------------------------------------------------------------- summaries
def _episode_summary(results: list[Episode3DResult]) -> dict[str, Any]:
    ok_times = sorted(r.sim_time_s for r in results if r.ok)
    speeds = sorted(
        r.contact_speed_mps for r in results if r.ok and r.contact_speed_mps
    )

    def med(xs: list[float]) -> float | None:
        return round(xs[len(xs) // 2], 3) if xs else None

    return {
        "rates": success_rates(results),
        "failure_modes": failure_histogram(results),
        "time_to_dock_s": {
            "median": med(ok_times),
            "p90": round(ok_times[int(0.9 * (len(ok_times) - 1))], 1)
            if ok_times else None,
        },
        "contact_speed_mps": {
            "median": med(speeds),
            "max": round(speeds[-1], 3) if speeds else None,
        },
        "episodes": [asdict(r) for r in results],
    }


def _bump_summary(results: list[BumpResult]) -> dict[str, Any]:
    def side(damper: bool) -> dict[str, Any]:
        rs = [r for r in results if r.damper is damper]
        settled = sorted(r.settle_s for r in rs if r.settle_s is not None)
        return {
            "episodes": len(rs),
            "settled": len(settled),
            "median_settle_s": round(settled[len(settled) // 2], 2)
            if settled else None,
            "max_tilt_deg_median": round(
                sorted(r.max_tilt_deg for r in rs)[len(rs) // 2], 1
            ) if rs else None,
        }

    return {"damper_on": side(True), "damper_off": side(False)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--bumps", type=int, default=50)
    ap.add_argument("--out", type=Path, default=Path("docs/assets"))
    ap.add_argument("--plots", action="store_true", help="write trajectory PNGs")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    # Two control rates: 50 Hz is what the 2D gate actually ran (sim tick
    # 0.02 s), 10 Hz is the interface spec. Both reported side by side.
    payload: dict[str, Any] = {"docking": {}, "bump": {}}
    results_50: list[Episode3DResult] = []
    for hz in (50.0, 10.0):
        results = []
        for seed in range(args.episodes):
            results.append(run_episode3d(seed, control_hz=hz))
            if (seed + 1) % 25 == 0:
                rates = success_rates(results)
                print(  # noqa: T201 - CLI progress is this tool's UI
                    f"[{hz:.0f} Hz {seed + 1}/{args.episodes}] "
                    f"first={rates['first_attempt']:.0%} "
                    f"any={rates['within_max_attempts']:.0%}"
                )
        payload["docking"][f"hz{hz:.0f}"] = _episode_summary(results)
        if hz == 50.0:
            results_50 = results
    for hz in (50.0, 10.0):
        bumps = []
        for seed in range(args.bumps):
            bumps.append(run_bump(seed, damper=True, control_hz=hz))
            bumps.append(run_bump(seed, damper=False, control_hz=hz))
        payload["bump"][f"hz{hz:.0f}"] = _bump_summary(bumps)
    out_json = args.out / "physics3d_results.json"
    out_json.write_text(json.dumps(payload, indent=2))
    brief = {
        "docking": {
            k: {"rates": v["rates"], "failure_modes": v["failure_modes"],
                "time_to_dock_s": v["time_to_dock_s"],
                "contact_speed_mps": v["contact_speed_mps"]}
            for k, v in payload["docking"].items()
        },
        "bump": payload["bump"],
    }
    print(json.dumps(brief, indent=2))  # noqa: T201
    print(f"wrote {out_json}")  # noqa: T201
    if args.plots:
        from sim3d.plots import write_plots

        write_plots(args.out, results_50)


if __name__ == "__main__":
    main()
