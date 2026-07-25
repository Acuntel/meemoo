"""App startup + health endpoint: must work with zero configuration."""

from __future__ import annotations

from fastapi.testclient import TestClient

from meemoo import __version__
from meemoo.api.app import create_app
from meemoo.core.config import Settings


def test_app_starts_and_health_ok_without_credentials(bare_settings: Settings) -> None:
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "meemoo"
    assert body["version"] == __version__
