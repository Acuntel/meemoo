"""FastAPI application: the full REST + WebSocket surface plus the web bundle.

Lifespan starts the AppRuntime (sim + guardian + scheduler + voice) unless
``MEEMOO_RUNTIME=0``. Startup must ALWAYS succeed — no credentials, no
camera, no mic, no web build required (Constitution Art. IX §3): a runtime
failure logs and leaves the API in honest API-only mode, never a crash.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from meemoo import __version__
from meemoo.api.care_routes import router as care_router
from meemoo.api.events_ws import router as events_ws_router
from meemoo.api.fleet_routes import router as fleet_router
from meemoo.api.guardian_routes import router as guardian_router
from meemoo.api.metrics_routes import router as metrics_router
from meemoo.api.perception_routes import router as perception_router
from meemoo.api.provider_routes import router as provider_router
from meemoo.api.sim_routes import router as sim_router
from meemoo.api.studio_routes import router as studio_router
from meemoo.api.video_ws import router as video_ws_router
from meemoo.api.voice_ws import router as voice_ws_router
from meemoo.core.config import get_settings
from meemoo.core.logging import setup_logging

logger = logging.getLogger(__name__)

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    runtime = None
    if settings.meemoo_runtime:
        from meemoo.api.runtime import AppRuntime

        runtime = AppRuntime(settings)
        try:
            await runtime.start()
        except Exception:
            logger.exception(
                "runtime failed to start — continuing in API-only mode (Art. IX §3)"
            )
            try:
                await runtime.stop()
            except Exception:
                logger.exception("runtime cleanup after failed start also failed")
            runtime = None
    else:
        logger.info("runtime disabled (MEEMOO_RUNTIME=0) — API-only mode")
    app.state.runtime = runtime
    try:
        yield
    finally:
        if runtime is not None:
            await runtime.stop()


def create_app() -> FastAPI:
    """Build the FastAPI app. Never raises on missing optional config."""
    settings = get_settings()
    setup_logging(json_output=settings.log_json, level=settings.log_level)

    app = FastAPI(title="Meemoo", version=__version__, lifespan=_lifespan)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "meemoo", "version": __version__}

    app.include_router(guardian_router)
    app.include_router(sim_router)
    app.include_router(fleet_router)
    app.include_router(care_router)
    app.include_router(provider_router)
    app.include_router(studio_router)
    app.include_router(metrics_router)
    app.include_router(perception_router)
    app.include_router(events_ws_router)
    app.include_router(video_ws_router)
    app.include_router(voice_ws_router)

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    else:
        logger.info(
            "web bundle not built; API only",
            extra={"fields": {"expected_path": str(WEB_DIST)}},
        )

    return app


app = create_app()
