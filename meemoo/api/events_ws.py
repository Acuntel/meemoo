"""``/ws/events`` — the live event stream for the dashboard.

Forwards every bus event as JSON ``{topic, payload, seq, ts}``. Late
subscribers get the replay-last snapshot per topic (bus feature), so a
freshly opened dashboard immediately knows battery, dock state, guardian
state. With no runtime bus it answers ``{"ready": false}`` and closes
honestly (Art. IX §3).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from meemoo.core.bus_registry import get_active_bus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket) -> None:
    await ws.accept()
    bus = get_active_bus()
    if bus is None:
        await ws.send_json({"ready": False})
        await ws.close()
        return
    # Subscribe BEFORE announcing ready: a client that fires an action the
    # moment it sees {"ready": true} must not race past the subscription.
    sub = bus.subscribe("*", replay_last=True)
    await ws.send_json({"ready": True})
    try:
        async for event in sub:
            await ws.send_json({
                "topic": event.topic,
                "payload": event.payload,
                "seq": event.seq,
                "ts": event.ts,
            })
    except WebSocketDisconnect:
        logger.debug("/ws/events client disconnected")
    finally:
        sub.close()
