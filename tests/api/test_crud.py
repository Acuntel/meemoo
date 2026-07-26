"""REST CRUD across the fleet/care surface + OpenAPI rendering (step-07 §1)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_openapi_renders_and_covers_the_surface(api_client: TestClient) -> None:
    spec = api_client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    for expected in (
        "/api/v1/devices",
        "/api/v1/devices/{device_id}/persons",
        "/api/v1/devices/{device_id}/contacts",
        "/api/v1/devices/{device_id}/keys",
        "/api/v1/devices/{device_id}/schedule",
        "/api/v1/devices/{device_id}/consent",
        "/api/v1/alerts",
        "/api/v1/alerts/{alert_id}/ack",
        "/api/v1/conversations",
        "/api/v1/events",
        "/api/v1/devices/{device_id}/usage",
        "/api/v1/studio/extract",
        "/api/v1/metrics/engagement",
    ):
        assert expected in paths, f"missing {expected}"
    assert api_client.get("/docs").status_code == 200


def test_device_crud(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/devices", json={"name": "Ward B", "mode": "facility"}
    )
    assert created.status_code == 201
    device_id = created.json()["id"]
    patched = api_client.patch(
        f"/api/v1/devices/{device_id}", json={"store_transcripts": False}
    )
    assert patched.json()["store_transcripts"] is False
    listing = api_client.get("/api/v1/devices").json()
    assert {d["id"] for d in listing} >= {1, device_id}
    assert api_client.get("/api/v1/devices/999").status_code == 404


def test_person_crud(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/devices/1/persons",
        json={"name": "Walter", "preferred_name": "Walt", "room": "bedroom"},
    )
    assert created.status_code == 201
    person_id = created.json()["id"]
    updated = api_client.put(
        f"/api/v1/persons/{person_id}",
        json={"name": "Walter", "preferred_name": "Wally", "room": "bedroom",
              "notes": None},
    )
    assert updated.json()["preferred_name"] == "Wally"
    assert api_client.delete(f"/api/v1/persons/{person_id}").status_code == 204
    names = [p["name"] for p in api_client.get("/api/v1/devices/1/persons").json()]
    assert "Walter" not in names


def test_schedule_crud_and_next_checkin(api_client: TestClient) -> None:
    assert api_client.get("/api/v1/devices/1/schedule").json() == []
    nxt = api_client.get("/api/v1/devices/1/next-checkin").json()
    assert nxt["times"] == ["09:00", "13:00", "18:00", "21:00"]  # defaults
    created = api_client.post(
        "/api/v1/devices/1/schedule", json={"time_of_day": "07:30", "label": "morning"}
    )
    assert created.status_code == 201
    row_id = created.json()["id"]
    nxt = api_client.get("/api/v1/devices/1/next-checkin").json()
    assert nxt["times"] == ["07:30"]
    assert api_client.delete(f"/api/v1/schedule/{row_id}").status_code == 204
    bad = api_client.post("/api/v1/devices/1/schedule", json={"time_of_day": "25:99"})
    assert bad.status_code == 422


def test_consent_lifecycle(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/devices/1/consent",
        json={"person_id": 1, "scope": "camera", "consenting_party": "Ruth"},
    )
    assert created.status_code == 201
    consent_id = created.json()["id"]
    assert created.json()["granted"] is True
    revoked = api_client.post(f"/api/v1/consent/{consent_id}/revoke").json()
    assert revoked["granted"] is False
    assert revoked["revoked_at"] is not None


def test_settings_and_privacy_pause(api_client: TestClient) -> None:
    put = api_client.put(
        "/api/v1/devices/1/settings/privacy.permissions",
        json={"value": {"nurse": {"alerts": True}, "son": {"alerts": False}}},
    )
    assert put.status_code == 200
    got = api_client.get("/api/v1/devices/1/settings/privacy.permissions").json()
    assert got["son"]["alerts"] is False
    paused = api_client.post("/api/v1/devices/1/privacy/pause", json={"minutes": 10})
    assert paused.json()["paused_until"]
    resumed = api_client.delete("/api/v1/devices/1/privacy/pause")
    assert resumed.json()["paused_until"] is None


def test_routes_crud(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/devices/1/routes",
        json={
            "name": "morning round",
            "is_default": True,
            "waypoints": [
                {"order_index": 0, "kind": "person", "label": "ruth", "x": 1.0, "y": 2.0},
                {"order_index": 1, "kind": "area", "label": "kitchen", "x": 3.0, "y": 1.0},
            ],
        },
    )
    assert created.status_code == 201
    route = created.json()
    assert [w["kind"] for w in route["waypoints"]] == ["person", "area"]
    assert api_client.delete(f"/api/v1/routes/{route['id']}").status_code == 204


def test_run_round_without_runtime_is_honest(api_client: TestClient) -> None:
    body = api_client.post("/api/v1/devices/1/rounds/run").json()
    assert body["started"] is False
    assert "runtime" in body["reason"]
