"""The four WebSockets: honest not-ready paths + live voice safety ordering."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from meemoo.core.bus import EventBus
from meemoo.core.bus_registry import set_active_bus
from meemoo.core.topics import CHECKIN_DUE, DISTRESS_HEARD
from meemoo.voice.distress import DISTRESS_ACK


@pytest.fixture
def live_bus() -> Iterator[EventBus]:
    bus = EventBus()
    set_active_bus(bus)
    yield bus
    set_active_bus(None)


def test_ws_events_honest_without_bus(api_client: TestClient) -> None:
    with api_client.websocket_connect("/ws/events") as ws:
        assert ws.receive_json() == {"ready": False}


def test_ws_video_honest_without_perception(api_client: TestClient) -> None:
    with api_client.websocket_connect("/ws/video") as ws:
        assert ws.receive_json()["ready"] is False


def test_ws_events_streams_bus_events(
    api_client: TestClient, live_bus: EventBus
) -> None:
    with api_client.websocket_connect("/ws/events") as ws:
        assert ws.receive_json()["ready"] is True
        fired = api_client.post("/api/v1/devices/1/rounds/run").json()
        assert fired["started"] is True
        message = ws.receive_json()
        assert message["topic"] == CHECKIN_DUE
        assert message["payload"]["time"] == "manual"


def test_ws_voice_text_roundtrip(api_client: TestClient) -> None:
    with api_client.websocket_connect("/ws/voice") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "ready"
        assert hello["stt"] is False  # headless: no STT engine, said honestly
        ws.send_json({"type": "text", "text": "good morning meemoo"})
        reply = ws.receive_json()
        assert reply["type"] == "reply"
        assert reply["distress"] is False
        assert reply["text"]  # scripted/templated brain always answers
        audio = ws.receive_json()
        assert audio["type"] == "audio"
        assert audio["available"] is False  # NullTTS: no fake audio


def test_ws_voice_distress_bypass_reaches_live_bus(
    api_client: TestClient, live_bus: EventBus
) -> None:
    """'help me' from the browser = same bypass as the room mic (Art. IV §4)."""
    with api_client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "text", "text": "help me"})
        reply = ws.receive_json()
        assert reply["distress"] is True
        assert reply["text"] == DISTRESS_ACK
    event = live_bus.last(DISTRESS_HEARD)
    assert event is not None
    assert event.payload["transcript"] == "help me"


def test_ws_voice_audio_without_stt_is_honest(api_client: TestClient) -> None:
    with api_client.websocket_connect("/ws/voice") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(b"\x00\x00" * 1600)
        ws.send_json({"type": "end"})
        error = ws.receive_json()
        assert error["type"] == "error"
        assert error["reason"] == "no_stt"
