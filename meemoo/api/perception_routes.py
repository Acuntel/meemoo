"""Perception demo/testing surface: bundled landmark-clip replay.

``GET /api/v1/perception/clips`` — names of the bundled landmark clips.
``POST /api/v1/perception/replay`` — replay one clip onto the LIVE bus so
the guardian reacts as if the camera saw it (demo-script step 4, headless).

Honest degradation (Art. IX §3): API-only mode (no bus) answers
``started: false`` with a reason instead of erroring; only one replay runs
at a time. Construction stays inside meemoo.perception (Art. II §2) — this
module only calls its public functions.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from meemoo.core.bus_registry import get_active_bus
from meemoo.perception.replay import MAX_SPEED, clip_path, list_clips, replay_to_bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/perception", tags=["perception"])

_replay_task: asyncio.Task[dict[str, object]] | None = None


class ReplayBody(BaseModel):
    clip: str = Field(min_length=1, max_length=120)
    speed: float = Field(default=3.0, gt=0.0, le=MAX_SPEED)
    device_id: int = 1


@router.get("/clips")
def get_clips() -> dict[str, object]:
    return {"clips": list_clips()}


@router.post("/replay")
async def post_replay(body: ReplayBody) -> dict[str, object]:
    """Start a background replay of one bundled clip on the live bus."""
    global _replay_task
    path = clip_path(body.clip)
    if path is None:
        raise HTTPException(status_code=404, detail=f"unknown clip {body.clip!r}")
    bus = get_active_bus()
    if bus is None:
        return {"started": False, "reason": "runtime not running (API-only mode)"}
    if _replay_task is not None and not _replay_task.done():
        return {"started": False, "reason": "a replay is already running"}

    task = asyncio.create_task(
        replay_to_bus(bus, path, device_id=body.device_id, speed=body.speed)
    )

    def _log_done(done: asyncio.Task[dict[str, object]]) -> None:
        if done.cancelled():
            logger.info("landmark replay cancelled")
        elif done.exception() is not None:
            logger.error("landmark replay failed",
                         extra={"fields": {"error": repr(done.exception())}})

    task.add_done_callback(_log_done)
    _replay_task = task
    logger.info(
        "landmark replay accepted",
        extra={"fields": {"clip": body.clip, "speed": body.speed}},
    )
    return {"started": True, "clip": body.clip, "speed": body.speed}
