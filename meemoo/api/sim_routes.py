"""Sim state for the web UI (step-07 renders it; step-06 exposes it).

``GET /api/v1/sim/state`` — ready flag + latest snapshot + floor plan.
``WS /ws/sim`` — snapshot stream at ~10 Hz while a sim is registered.

With no sim registered both answer honestly (``ready: False`` / immediate
close) instead of crashing (Art. IX §3).
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from meemoo.flight.registry import get_active_sim

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sim"])


@router.get("/api/v1/sim/state")
def sim_state() -> dict[str, object]:
    sim = get_active_sim()
    if sim is None:
        return {"ready": False, "snapshot": None, "plan": None}
    return {
        "ready": True,
        "snapshot": sim.snapshot().to_dict(),
        "plan": sim.plan.to_dict(),
    }


@router.websocket("/ws/sim")
async def ws_sim(ws: WebSocket) -> None:
    await ws.accept()
    sim = get_active_sim()
    if sim is None:
        await ws.send_json({"ready": False})
        await ws.close()
        return
    await ws.send_json({"ready": True, "plan": sim.plan.to_dict()})
    try:
        while True:
            await ws.send_json(sim.snapshot().to_dict())
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        logger.debug("/ws/sim client disconnected")
