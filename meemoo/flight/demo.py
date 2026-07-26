"""Flight + dock demo: watch the whale fly a round, dock, charge, depart.

Headless debug view (Phase-6 manual gate): a top-down ASCII floor plan with
the blimp (``@``), dock (``D``), waypoints (``.``/``P``), plus a state line
per second. The real web UI lands in step 07 — this proves the loop.

    uv run python -m meemoo.flight.demo             # apartment round
    uv run python -m meemoo.flight.demo --plan facility_wing
    uv run python -m meemoo.flight.demo --fast      # no wall-clock pacing
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from meemoo.core.logging import setup_logging
from meemoo.flight.sim_blimp import FlightMode, SimulatedBlimp

logger = logging.getLogger(__name__)


def _ascii_map(sim: SimulatedBlimp, cols: int = 48, rows: int = 14) -> str:
    x0, y0, x1, y1 = sim.plan.bounds
    grid = [[" "] * cols for _ in range(rows)]

    def put(x: float, y: float, ch: str) -> None:
        c = int((x - x0) / (x1 - x0) * (cols - 1))
        r = int((y - y0) / (y1 - y0) * (rows - 1))
        grid[max(0, min(rows - 1, r))][max(0, min(cols - 1, c))] = ch

    for w in sim.plan.waypoints:
        put(w.x, w.y, "P" if w.kind == "person" else ".")
    put(sim.plan.dock.x, sim.plan.dock.y, "D")
    put(sim.phys.x, sim.phys.y, "@")
    border = "+" + "-" * cols + "+"
    return "\n".join([border] + ["|" + "".join(r) + "|" for r in grid] + [border])


async def run_demo(plan: str, *, fast: bool, seed: int, max_sim_s: float) -> int:
    sim = SimulatedBlimp(plan, seed=seed, person_hold_s=4.0, area_hold_s=1.5)
    logger.info("demo: starting docked on %r, battery %.0f%%", sim.plan.name,
                sim.phys.battery_pct)
    sim.dispatch("demo-round")
    dt = 0.02  # the controller is tuned/measured at 50 Hz — keep it
    last_print = -5.0
    departed = False
    while sim.phys.t < max_sim_s:
        for topic, payload in sim.tick(dt):
            logger.info("bus %-24s %s", topic, payload)
        if sim.phys.t - last_print >= 1.0:
            last_print = sim.phys.t
            snap = sim.snapshot()
            print(  # noqa: T201 — demo UI
                f"t={snap.t:6.1f}s {snap.phase:15s} pos=({snap.x:4.1f},{snap.y:4.1f}) "
                f"batt={snap.battery_pct:5.1f}% docked={snap.docked} "
                f"buoy={snap.net_buoyancy_gf:+.1f}gf he={snap.helium_level_pct:.1f}%"
            )
            if int(sim.phys.t) % 5 == 0:
                print(_ascii_map(sim))  # noqa: T201 — demo UI
        if (
            not departed
            and sim.mode is FlightMode.DOCKED
            and sim.docking.docked
            and sim.phys.t > 20.0
            and sim.phys.battery_pct > 99.0
        ):
            logger.info("demo: charged — releasing to prove the departure path")
            departed = True
            sim.takeoff()
        elif departed and sim.mode is FlightMode.HOLD:
            logger.info("demo: round + dock + charge + depart complete")
            return 0
        if not fast:
            await asyncio.sleep(dt)
    logger.warning("demo: sim time limit reached in mode %s / phase %s",
                   sim.mode, sim.docking.phase)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", default="apartment")
    ap.add_argument("--fast", action="store_true", help="run without wall-clock pacing")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--max-sim-s", type=float, default=600.0)
    args = ap.parse_args()
    setup_logging(json_output=False, level="INFO")
    return asyncio.run(run_demo(args.plan, fast=args.fast, seed=args.seed,
                                max_sim_s=args.max_sim_s))


if __name__ == "__main__":
    raise SystemExit(main())
