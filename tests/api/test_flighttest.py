"""Flight Test API: honest without a sim, drives the sim when present."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from meemoo.api.flighttest_routes import router
from meemoo.flight.registry import set_active_sim
from meemoo.flight.sim_blimp import FlightMode, SimulatedBlimp


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c
    set_active_sim(None)


def flying_sim() -> SimulatedBlimp:
    return SimulatedBlimp(
        "apartment", seed=3, drafts_enabled=False, start_docked=False,
        pose_noise_m=0.0,
    )


class TestWithoutSim:
    def test_state_is_honest(self, client: TestClient) -> None:
        set_active_sim(None)
        assert client.get("/api/v1/flight-test/state").json() == {"ready": False}

    @pytest.mark.parametrize("path", ["control", "stop", "takeoff", "dock"])
    def test_posts_answer_503_with_a_reason(self, client: TestClient, path: str) -> None:
        set_active_sim(None)
        response = client.post(f"/api/v1/flight-test/{path}", json={})
        assert response.status_code == 503
        assert "aircraft" in response.json()["detail"].lower()


class TestControl:
    def test_slider_frame_enters_manual(self, client: TestClient) -> None:
        sim = flying_sim()
        set_active_sim(sim)
        body = client.post(
            "/api/v1/flight-test/control",
            json={"forward": 0.6, "vertical": 0.1, "yaw": 0.0},
        ).json()
        assert body == {"accepted": True, "reason": None}
        assert sim.mode is FlightMode.MANUAL

    def test_docked_control_refused_with_plain_reason(self, client: TestClient) -> None:
        set_active_sim(SimulatedBlimp("apartment", seed=1, drafts_enabled=False))
        body = client.post(
            "/api/v1/flight-test/control", json={"forward": 1.0}
        ).json()
        assert body["accepted"] is False
        assert "lift off" in body["reason"].lower()

    def test_out_of_range_slider_is_a_422(self, client: TestClient) -> None:
        set_active_sim(flying_sim())
        response = client.post("/api/v1/flight-test/control", json={"forward": 3.0})
        assert response.status_code == 422

    def test_stop_halts_manual(self, client: TestClient) -> None:
        sim = flying_sim()
        set_active_sim(sim)
        client.post("/api/v1/flight-test/control", json={"forward": 1.0})
        for _ in range(20):
            sim.tick(0.02)
        body = client.post("/api/v1/flight-test/stop").json()
        assert body["accepted"] is True
        assert sim.mode is FlightMode.HOLD


class TestTakeoffAndDock:
    def test_takeoff_from_dock_then_control_accepted(self, client: TestClient) -> None:
        sim = SimulatedBlimp("apartment", seed=1, drafts_enabled=False)
        set_active_sim(sim)
        assert client.post("/api/v1/flight-test/takeoff").json()["accepted"] is True
        # run the undock until the aircraft is free-flying
        for _ in range(int(30.0 / 0.02)):
            sim.tick(0.02)
            if sim.mode not in (FlightMode.DOCKED, FlightMode.UNDOCKING):
                break
        assert sim.mode not in (FlightMode.DOCKED, FlightMode.UNDOCKING)
        body = client.post("/api/v1/flight-test/control", json={"forward": 0.5}).json()
        assert body["accepted"] is True

    def test_takeoff_in_the_air_is_refused(self, client: TestClient) -> None:
        set_active_sim(flying_sim())
        body = client.post("/api/v1/flight-test/takeoff").json()
        assert body["accepted"] is False
        assert "air" in body["reason"].lower()

    def test_dock_command_accepted_in_flight(self, client: TestClient) -> None:
        sim = flying_sim()
        set_active_sim(sim)
        body = client.post("/api/v1/flight-test/dock").json()
        assert body["accepted"] is True
        assert sim.mode is FlightMode.RETURNING


class TestState:
    def test_state_reports_cap_and_telemetry(self, client: TestClient) -> None:
        sim = flying_sim()
        set_active_sim(sim)
        body = client.get("/api/v1/flight-test/state").json()
        assert body["ready"] is True
        assert body["speed_cap_mps"] == pytest.approx(1.3)
        assert body["cap_engaged"] is False
        for key in (
            "speed_mps", "altitude_m", "heading_deg", "battery_pct",
            "net_buoyancy_gf", "mode", "manual_active", "docked",
        ):
            assert key in body
