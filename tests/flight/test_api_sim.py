"""/api/v1/sim/state + /ws/sim — honest when no sim is registered."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from meemoo.api.sim_routes import router
from meemoo.flight.registry import get_active_sim, set_active_sim
from meemoo.flight.sim_blimp import SimulatedBlimp


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    set_active_sim(None)


def test_state_without_sim_is_honest(client: TestClient) -> None:
    set_active_sim(None)
    body = client.get("/api/v1/sim/state").json()
    assert body == {"ready": False, "snapshot": None, "plan": None}


def test_state_with_registered_sim(client: TestClient) -> None:
    sim = SimulatedBlimp("apartment", seed=1, drafts_enabled=False)
    set_active_sim(sim)
    assert get_active_sim() is sim
    body = client.get("/api/v1/sim/state").json()
    assert body["ready"] is True
    assert body["snapshot"]["docked"] is True
    assert body["plan"]["name"] == "apartment"


def test_ws_without_sim_closes_honestly(client: TestClient) -> None:
    set_active_sim(None)
    with client.websocket_connect("/ws/sim") as ws:
        assert ws.receive_json() == {"ready": False}


def test_ws_streams_snapshots(client: TestClient) -> None:
    set_active_sim(SimulatedBlimp("apartment", seed=1, drafts_enabled=False))
    with client.websocket_connect("/ws/sim") as ws:
        hello = ws.receive_json()
        assert hello["ready"] is True and "plan" in hello
        snap = ws.receive_json()
        assert "battery_pct" in snap and "phase" in snap
