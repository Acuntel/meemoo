"""``/ws/video`` — annotated camera frames for the dashboard's Live View.

Streams the perception pipeline's FrameHub as binary JPEG messages after a
JSON hello. Perception is optional (cv2 + a camera); with no pipeline
registered the endpoint answers ``{"ready": false}`` and closes honestly
(Art. IX §3) — the UI shows a friendly "camera not running" card instead.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from meemoo.perception.registry import get_active_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["video"])


@router.websocket("/ws/video")
async def ws_video(ws: WebSocket) -> None:
    await ws.accept()
    pipeline = get_active_pipeline()
    if pipeline is None:
        await ws.send_json({"ready": False, "reason": "perception not running"})
        await ws.close()
        return
    await ws.send_json({"ready": True})
    hub = pipeline.hub
    try:
        if hub.latest_jpeg is not None:  # immediate first frame for late joiners
            await ws.send_bytes(hub.latest_jpeg)
        while True:
            frame = await hub.wait_frame()
            if frame is not None:
                await ws.send_bytes(frame)
    except WebSocketDisconnect:
        logger.debug("/ws/video client disconnected")
