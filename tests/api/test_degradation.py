"""Step-08 degradation matrix: nothing crashes, the safety loop always works.

Axes (demo-script §degradation): no API key / no camera / no mic / no sim /
no Twilio / no network. The headless test environment already has no cv2
(camera), no sounddevice (mic), and the conftest deletes every credential —
so every boot here is ALSO keyless, Twilio-less, and mic-less. Each cell
boots the FULL runtime (real lifespan, real migrations, tmp DB) and proves
the scripted safety loop end-to-end: "help me" over /ws/voice → distress
bypass (no LLM) → guardian L1 → simulated notify → dashboard ack halts the
machine. Art. IX §3 exercised at app level.
"""

from __future__ import annotations

import socket
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from meemoo.core.config import get_settings
from meemoo.core.db import reset_db

_CRED_VARS = [
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY", "OLLAMA_URL",
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER",
    "MEEMOO_FERNET_KEY",
]


def _make_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, env: dict[str, str]
) -> TestClient:
    for var in _CRED_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MEEMOO_RUNTIME", "1")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    reset_db()
    get_settings.cache_clear()
    from meemoo.api.app import create_app

    return TestClient(create_app())


@pytest.fixture
def cleanup() -> Iterator[None]:
    yield
    reset_db()
    get_settings.cache_clear()


def _distress_loop(client: TestClient) -> None:
    """'help me' → distress reply → L1 alert → ack halts. Pure scripted path."""
    with client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "text", "text": "help me please"})
        reply = ws.receive_json()
        assert reply["type"] == "reply"
        assert reply["distress"] is True
    alert_id: int | None = None
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        alerts: list[dict[str, Any]] = client.get("/api/v1/alerts").json()
        active = [a for a in alerts if a["state"] == "open" and a["level"] == "L1"]
        if active:
            alert_id = active[0]["id"]
            break
        time.sleep(0.2)
    assert alert_id is not None, "distress never produced an L1 alert"
    ack = client.post(f"/api/v1/alerts/{alert_id}/ack", json={"via": "dashboard"}).json()
    assert ack["state"] == "acknowledged:dashboard"
    assert ack["machine_state"] == "IDLE"


# One cell per degradation axis the headless env doesn't already force,
# plus the everything-at-once cell (which IS the default headless env).
MATRIX = [
    pytest.param({}, id="all-absent-defaults"),
    pytest.param({"VIDEO_SOURCE": "off"}, id="camera-explicitly-off"),
    pytest.param({"VIDEO_SOURCE": "file"}, id="camera-misconfigured-no-file"),
    pytest.param({"VOICE_TTS": "null", "VOICE_STT": "off"}, id="voice-engines-off"),
    pytest.param({"MEEMOO_PLAN": "facility_wing"}, id="facility-plan"),
]


@pytest.mark.parametrize("env", MATRIX)
def test_matrix_boots_and_safety_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cleanup: None,
    env: dict[str, str],
) -> None:
    with _make_client(monkeypatch, tmp_path, env) as client:
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert client.get("/api/v1/sim/state").json()["ready"] is True
        _distress_loop(client)


def test_no_network_safety_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cleanup: None
) -> None:
    """Kill outbound TCP entirely — the safety loop must not notice."""
    real_connect = socket.socket.connect

    def dead_connect(self: socket.socket, address: Any) -> None:
        # The asyncio self-pipe/socketpair still works — kill the NETWORK,
        # not the event loop (AF_UNIX / localhost pairs used internally).
        if isinstance(address, tuple):
            raise OSError("network dead (degradation matrix)")
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", dead_connect)
    with _make_client(monkeypatch, tmp_path, {}) as client:
        assert client.get("/api/v1/health").json()["status"] == "ok"
        _distress_loop(client)


def test_broken_sim_falls_to_api_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cleanup: None
) -> None:
    """A sim that cannot start degrades the app to honest API-only mode."""
    with _make_client(
        monkeypatch, tmp_path, {"MEEMOO_PLAN": "/nonexistent/plan.json"}
    ) as client:
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert client.get("/api/v1/sim/state").json()["ready"] is False


def test_api_only_mode_honest_everywhere(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cleanup: None
) -> None:
    """MEEMOO_RUNTIME=0: every live surface answers honestly, none crash —
    and the distress DETECTOR still flags even with no runtime at all."""
    for var in _CRED_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MEEMOO_RUNTIME", "0")
    monkeypatch.chdir(tmp_path)
    reset_db()
    get_settings.cache_clear()
    from meemoo.api.app import create_app

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health").json()["status"] == "ok"
        assert client.get("/api/v1/sim/state").json()["ready"] is False
        round_out = client.post("/api/v1/devices/1/rounds/run").json()
        assert round_out["started"] is False and "reason" in round_out
        replay_out = client.post(
            "/api/v1/perception/replay", json={"clip": "fall_no_response"}
        ).json()
        assert replay_out["started"] is False and "reason" in replay_out
        with client.websocket_connect("/ws/video") as ws:
            assert ws.receive_json()["ready"] is False


def test_replay_drives_guardian_like_the_camera(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, cleanup: None
) -> None:
    """Demo step 4 headless: bundled fall clip → person.down → guardian CONCERN.

    (The full CONCERN → verify ×2 → L1 ladder runs on honest wall-clock
    timeouts — its walk is covered by the guardian suite; here we prove the
    replay feeds the LIVE guardian exactly like the camera would.)
    """
    with _make_client(monkeypatch, tmp_path, {}) as client:
        clips = client.get("/api/v1/perception/clips").json()["clips"]
        assert "fall_no_response" in clips
        assert client.post(
            "/api/v1/perception/replay",
            json={"clip": "bogus"},
        ).status_code == 404
        with client.websocket_connect("/ws/events") as ws:
            assert ws.receive_json()["ready"] is True
            out = client.post(
                "/api/v1/perception/replay",
                json={"clip": "fall_no_response", "speed": 50},
            ).json()
            assert out["started"] is True
            seen: list[str] = []
            states: list[str] = []
            deadline = time.monotonic() + 30.0
            while time.monotonic() < deadline:
                msg = ws.receive_json()
                seen.append(msg["topic"])
                if msg["topic"] == "guardian.state":
                    states.append(str(msg["payload"].get("to", "")))
                    if "CONCERN" in states:
                        break
            assert "person.down" in seen
            assert "CONCERN" in states
