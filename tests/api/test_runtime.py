"""Full-runtime smoke: zero-config startup wires sim + guardian + scheduler.

Uses the REAL lifespan (MEEMOO_RUNTIME on): migrations run against a tmp DB,
the sim registers and reports docked, a manual round fires through the live
bus, and shutdown is clean. This is Art. IX §3 exercised end-to-end.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meemoo.core.config import get_settings
from meemoo.core.topics import CHECKIN_DUE

_CRED_VARS = [
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "OLLAMA_URL",
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER",
    "MEEMOO_FERNET_KEY",
]


@pytest.fixture
def runtime_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    for var in _CRED_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MEEMOO_RUNTIME", "1")
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    from meemoo.api.app import create_app

    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


def test_runtime_boots_sim_guardian_and_round(runtime_client: TestClient) -> None:
    assert runtime_client.get("/api/v1/health").json()["status"] == "ok"

    state = runtime_client.get("/api/v1/sim/state").json()
    assert state["ready"] is True
    assert state["snapshot"]["docked"] is True
    assert state["plan"]["name"] == "apartment"

    with runtime_client.websocket_connect("/ws/events") as ws:
        assert ws.receive_json()["ready"] is True
        assert runtime_client.post("/api/v1/devices/1/rounds/run").json()["started"]
        seen: list[str] = []
        for _ in range(20):
            seen.append(ws.receive_json()["topic"])
            if CHECKIN_DUE in seen:
                break
        assert CHECKIN_DUE in seen


def test_runtime_off_means_honest_api_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MEEMOO_RUNTIME", "0")
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    from meemoo.api.app import create_app

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/sim/state").json()["ready"] is False
    get_settings.cache_clear()
