"""FastAPI application: REST under /api/v1 plus the built web bundle.

Startup must always succeed — no credentials, no camera, no web build required
(Constitution Art. IX §3).
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from meemoo import __version__
from meemoo.api.guardian_routes import router as guardian_router
from meemoo.core.config import get_settings
from meemoo.core.logging import setup_logging

logger = logging.getLogger(__name__)

WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app() -> FastAPI:
    """Build the FastAPI app. Never raises on missing optional config."""
    settings = get_settings()
    setup_logging(json_output=settings.log_json, level=settings.log_level)

    app = FastAPI(title="Meemoo", version=__version__)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "meemoo", "version": __version__}

    app.include_router(guardian_router)

    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    else:
        logger.info(
            "web bundle not built; API only",
            extra={"fields": {"expected_path": str(WEB_DIST)}},
        )

    return app


app = create_app()
