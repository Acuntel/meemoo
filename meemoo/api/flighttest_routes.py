"""Flight Test API — the sliders that fly the whale (and later the airframe).

The Flight Test page (Studio > Under the hood, or /flight-test directly)
posts normalized slider frames here. Today they drive the registered
SimulatedBlimp through :mod:`meemoo.flight.manual`; at hardware time the
SAME endpoints feed the UDP bridge, which maps each accepted frame onto a
MUP/1 THRUST packet (see meemoo/flight/mup.py + firmware/README.md).

Honesty rules surface here, not in the page: a refused frame (docked, dock
capture finishing, off-limit zone braking) comes back with the plain-words
reason, and /state reports when the 1.3 m/s governor (A5) is binding.
With no sim registered everything answers honestly instead of crashing
(Art. IX §3).
"""

from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from meemoo.flight.registry import get_active_sim
from meemoo.flight.sim_blimp import FlightMode, SimulatedBlimp

router = APIRouter(tags=["flight-test"])

_NO_AIRCRAFT = "No aircraft is running. Start the runtime and try again."


def _sim_or_503() -> SimulatedBlimp:
    sim = get_active_sim()
    if sim is None:
        raise HTTPException(status_code=503, detail=_NO_AIRCRAFT)
    return sim


class ControlFrame(BaseModel):
    """One slider frame; all axes normalized to [-1, 1]."""

    forward: float = Field(0.0, ge=-1.0, le=1.0)
    vertical: float = Field(0.0, ge=-1.0, le=1.0)
    yaw: float = Field(0.0, ge=-1.0, le=1.0)


@router.get("/api/v1/flight-test/state")
def flight_test_state() -> dict[str, object]:
    """Telemetry strip: speed vs the cap, altitude, battery, mode, trim."""
    sim = get_active_sim()
    if sim is None:
        return {"ready": False}
    pose = sim.position()
    speed = math.sqrt(pose.vx**2 + pose.vy**2 + pose.vz**2)
    battery = sim.battery_status()
    return {
        "ready": True,
        "mode": str(sim.mode),
        "manual_active": sim.manual_active(),
        "docked": sim.mode is FlightMode.DOCKED,
        "speed_mps": round(speed, 3),
        "speed_cap_mps": sim.cfg.max_speed_mps,
        "cap_engaged": sim.cap_engaged(),
        "altitude_m": round(pose.z, 2),
        "heading_deg": round(math.degrees(pose.heading_rad), 1),
        "battery_pct": round(battery.pct, 1),
        "charging": battery.charging,
        "net_buoyancy_gf": round(sim.net_buoyancy_gf(), 2),
    }


@router.post("/api/v1/flight-test/control")
def flight_test_control(frame: ControlFrame) -> dict[str, object]:
    """Apply one slider frame. Refusals come back honest, never a 500."""
    sim = _sim_or_503()
    return sim.set_manual_input(frame.forward, frame.vertical, frame.yaw)


@router.post("/api/v1/flight-test/stop")
def flight_test_stop() -> dict[str, object]:
    """STOP: the A5 hard stop — mission and sliders cleared, brake to hold."""
    sim = _sim_or_503()
    sim.halt()
    return {"accepted": True, "reason": None}


@router.post("/api/v1/flight-test/takeoff")
def flight_test_takeoff() -> dict[str, object]:
    """Leave the dock (or the floor) so the sliders have something to fly."""
    sim = _sim_or_503()
    if sim.mode not in (FlightMode.DOCKED, FlightMode.LANDED):
        return {"accepted": False, "reason": "Meemoo is already in the air."}
    sim.takeoff()
    return {"accepted": True, "reason": None}


@router.post("/api/v1/flight-test/dock")
def flight_test_dock() -> dict[str, object]:
    """Send it home: full docking sequence, two-signal capture and all."""
    sim = _sim_or_503()
    if sim.mode is FlightMode.DOCKED:
        return {"accepted": False, "reason": "Meemoo is already on the dock."}
    sim.return_to_dock()
    return {"accepted": True, "reason": None}
