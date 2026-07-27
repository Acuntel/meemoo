"""Onboarding API: record round-trip, pairing codes, room photos, zones,
and the A3 auto-purge rule (audit row per deleted item, chain intact)."""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from meemoo.core.models import AuditLog, Event, RoomCapture, verify_audit_chain

PNG_1PX = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQAB"
        "h6FO1AAAAABJRU5ErkJggg=="
    )
).decode()


# ------------------------------------------------------------------- record
def test_onboarding_round_trip(api_client: TestClient) -> None:
    fresh = api_client.get("/api/v1/devices/1/onboarding").json()
    assert fresh == {
        "exists": False,
        "completed": False,
        "dwelling_type": None,
        "step": "place",
        "paired": False,
    }

    saved = api_client.put(
        "/api/v1/devices/1/onboarding",
        json={"dwelling_type": "senior_room", "step": "rooms"},
    ).json()
    assert saved["exists"] is True
    assert saved["dwelling_type"] == "senior_room"
    assert saved["step"] == "rooms"
    assert saved["completed"] is False

    done = api_client.post("/api/v1/devices/1/onboarding/complete").json()
    assert done["completed"] is True
    assert api_client.get("/api/v1/devices/1/onboarding").json()["completed"] is True


def test_onboarding_rejects_unknown_values(api_client: TestClient) -> None:
    assert (
        api_client.put(
            "/api/v1/devices/1/onboarding", json={"dwelling_type": "castle"}
        ).status_code
        == 400
    )
    assert (
        api_client.put("/api/v1/devices/1/onboarding", json={"step": "warp"}).status_code
        == 400
    )


# ------------------------------------------------------------------ pairing
def test_pairing_code_validation(api_client: TestClient) -> None:
    for bad in ("", "MEEMOO", "MEEMOO-12-3456", "DRIFT-1234-5678", "MEEMOO-12345678"):
        response = api_client.post("/api/v1/devices/1/pair", json={"code": bad})
        assert response.status_code in (400, 422), bad

    ok = api_client.post("/api/v1/devices/1/pair", json={"code": "meemoo-ab12-cd34"})
    assert ok.status_code == 200
    assert ok.json() == {"paired": True, "code": "MEEMOO-AB12-CD34"}
    assert api_client.get("/api/v1/devices/1/onboarding").json()["paired"] is True


# ------------------------------------------------------------- room capture
def test_photo_round_trip_and_retake(api_client: TestClient) -> None:
    for _ in range(2):
        created = api_client.post(
            "/api/v1/devices/1/rooms/living room/photos",
            json={"image_base64": PNG_1PX, "content_type": "image/png"},
        )
        assert created.status_code == 201

    rooms = api_client.get("/api/v1/devices/1/rooms").json()
    assert rooms == [
        {
            "room": "living room",
            "photo_count": 2,
            "target": 20,
            "last_captured_at": rooms[0]["last_captured_at"],
        }
    ]

    photos = api_client.get("/api/v1/devices/1/rooms/living room/photos").json()
    assert len(photos) == 2
    served = api_client.get(f"/api/v1/photos/{photos[0]['id']}")
    assert served.status_code == 200
    assert len(served.content) > 0

    assert api_client.delete(f"/api/v1/photos/{photos[0]['id']}").status_code == 204
    retaken = api_client.delete("/api/v1/devices/1/rooms/living room/photos").json()
    assert retaken["deleted"] == 1
    assert api_client.get("/api/v1/devices/1/rooms").json() == []


def test_photo_rejects_garbage(api_client: TestClient) -> None:
    bad = api_client.post(
        "/api/v1/devices/1/rooms/kitchen/photos",
        json={"image_base64": "not-base64!!!", "content_type": "image/png"},
    )
    assert bad.status_code == 400


def test_upload_into_off_limit_room_refused(api_client: TestClient) -> None:
    zone = api_client.post(
        "/api/v1/devices/1/zones",
        json={"name": "the bathroom", "x": 7.0, "y": 0.0, "w": 2.0, "h": 3.0,
              "reason": "bathroom"},
    )
    assert zone.status_code == 201
    refused = api_client.post(
        "/api/v1/devices/1/rooms/bathroom/photos",
        json={"image_base64": PNG_1PX, "content_type": "image/png"},
    )
    assert refused.status_code == 403
    assert "off limits" in refused.json()["detail"]


# ------------------------------------------------------------------ zones
def test_zone_crud(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/devices/1/zones",
        json={"name": "the bathroom", "x": 7.0, "y": 0.0, "w": 2.0, "h": 3.0,
              "reason": "bathroom"},
    ).json()
    assert created["purged"] == 0
    zones = api_client.get("/api/v1/devices/1/zones").json()
    assert len(zones) == 1 and zones[0]["name"] == "the bathroom"
    assert api_client.delete(f"/api/v1/zones/{zones[0]['id']}").status_code == 204
    assert api_client.get("/api/v1/devices/1/zones").json() == []


def test_zone_creation_auto_purges_with_audit_rows(
    api_client: TestClient, db_factory: sessionmaker[Session], tmp_path: Path
) -> None:
    room_file = tmp_path / "bathroom-photo.jpg"
    room_file.write_bytes(b"jpeg-bytes")
    thumb_file = tmp_path / "event-thumb.jpg"
    thumb_file.write_bytes(b"jpeg-bytes")
    with db_factory() as db:
        db.add(RoomCapture(device_id=1, room="bathroom", path=str(room_file), x=8.0, y=1.5))
        db.add(Event(
            device_id=1, type="person.detected",
            payload={"x": 8.0, "y": 1.5}, thumbnail_path=str(thumb_file),
        ))
        db.add(Event(
            device_id=1, type="person.detected",
            payload={"x": 2.0, "y": 2.0}, thumbnail_path="unrelated.jpg",
        ))
        db.commit()

    created = api_client.post(
        "/api/v1/devices/1/zones",
        json={"name": "the bathroom", "x": 7.0, "y": 0.0, "w": 2.0, "h": 3.0,
              "reason": "bathroom"},
    ).json()
    assert created["purged"] == 2
    assert not room_file.exists()
    assert not thumb_file.exists()

    with db_factory() as db:
        assert db.query(RoomCapture).count() == 0
        purge_rows = (
            db.query(AuditLog).filter(AuditLog.action == "media.auto_purged").all()
        )
        assert len(purge_rows) == 2
        assert all("Amendment A3" in (r.detail or "") for r in purge_rows)
        ok, bad_id = verify_audit_chain(db)
        assert ok, f"audit chain broken at {bad_id}"


# ------------------------------------------------------------------- goto
def test_goto_api_honest_without_runtime(api_client: TestClient) -> None:
    quiet = api_client.post("/api/v1/devices/1/goto", json={"x": 2.0, "y": 2.0}).json()
    assert quiet == {
        "started": False,
        "refused": False,
        "reason": "Meemoo isn't flying right now",
    }
    api_client.post(
        "/api/v1/devices/1/zones",
        json={"name": "the bathroom", "x": 7.0, "y": 0.0, "w": 2.0, "h": 3.0,
              "reason": "bathroom"},
    )
    refused = api_client.post("/api/v1/devices/1/goto", json={"x": 8.0, "y": 1.5}).json()
    assert refused["refused"] is True
    assert "off limits" in refused["reason"]
