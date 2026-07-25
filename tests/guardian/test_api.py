"""Guardian REST: contacts CRUD, alerts, ack, false-alarm metric, SMS webhook."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session, sessionmaker

from meemoo.api.deps import get_db
from meemoo.api.guardian_routes import router
from meemoo.guardian.registry import set_active_service


@pytest.fixture
def app(db_factory: sessionmaker[Session]) -> Iterator[FastAPI]:
    app = FastAPI()
    app.include_router(router)

    def override() -> Iterator[Session]:
        with db_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    yield app
    set_active_service(None)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def test_contacts_crud_roundtrip(client: AsyncClient, seeded: dict[str, int]) -> None:
    device_id = seeded["device_id"]
    # list (seeded two, escalation order)
    listed = (await client.get(f"/api/v1/devices/{device_id}/contacts")).json()
    assert [c["name"] for c in listed] == ["Dana", "Sam"]
    # create
    created = await client.post(
        f"/api/v1/devices/{device_id}/contacts",
        json={"name": "Nurse Kim", "phone": "+13125550102",
              "relationship_label": "nurse", "order_index": 2, "notify_call": False},
    )
    assert created.status_code == 201
    contact_id = created.json()["id"]
    # update
    updated = await client.put(
        f"/api/v1/contacts/{contact_id}",
        json={"name": "Nurse Kim", "phone": "+13125550103", "order_index": 2},
    )
    assert updated.status_code == 200 and updated.json()["phone"] == "+13125550103"
    # delete
    assert (await client.delete(f"/api/v1/contacts/{contact_id}")).status_code == 204
    remaining = (await client.get(f"/api/v1/devices/{device_id}/contacts")).json()
    assert len(remaining) == 2
    # 404s
    assert (await client.delete(f"/api/v1/contacts/{contact_id}")).status_code == 404
    assert (
        await client.put(f"/api/v1/contacts/{contact_id}", json={"name": "x"})
    ).status_code == 404


async def test_alerts_list_ack_and_metric(
    client: AsyncClient, db_factory: sessionmaker[Session], seeded: dict[str, int],
) -> None:
    from meemoo.guardian import escalation

    device_id = seeded["device_id"]
    with db_factory() as db:
        alert = escalation.open_alert(db, device_id=device_id, reason="test episode")
        escalation.record_false_alarm(db, device_id=device_id, detail={"why": "test"})
    listed = (await client.get("/api/v1/alerts", params={"device_id": device_id})).json()
    assert listed and listed[0]["state"] == "open" and listed[0]["level"] == "L1"

    acked = await client.post(
        f"/api/v1/alerts/{alert.id}/ack",
        json={"contact_id": seeded["daughter_id"], "via": "dashboard"},
    )
    assert acked.status_code == 200
    body = acked.json()
    assert body["state"] == "acknowledged:dashboard"
    assert body["latency_s"] is not None and body["latency_s"] >= 0
    assert body["machine_state"] is None  # no live service registered — still fine

    metric = (await client.get("/api/v1/metrics/false-alarms")).json()
    assert metric == {"false_alarms_last_7_days": 1, "window_days": 7}

    assert (await client.post("/api/v1/alerts/99999/ack", json={})).status_code == 404


async def test_sms_webhook_ack_from_known_contact(
    client: AsyncClient, db_factory: sessionmaker[Session], seeded: dict[str, int],
) -> None:
    from meemoo.guardian import escalation

    device_id = seeded["device_id"]
    with db_factory() as db:
        alert = escalation.open_alert(db, device_id=device_id, reason="fall detected")
    response = await client.post(
        "/api/v1/twilio/sms",
        data={"From": "+1 (312) 555-0100", "Body": "ACK"},  # formatted number still matches
    )
    assert response.status_code == 200
    assert "acknowledged by Dana" in response.text
    with db_factory() as db:
        from meemoo.core.models import Alert

        row = db.get(Alert, alert.id)
        assert row is not None and row.state == "acknowledged:sms"
        assert row.acknowledged_by_contact_id == seeded["daughter_id"]


async def test_sms_webhook_ignores_unknown_sender_and_chatter(
    client: AsyncClient, db_factory: sessionmaker[Session], seeded: dict[str, int],
) -> None:
    from meemoo.guardian import escalation

    with db_factory() as db:
        alert = escalation.open_alert(
            db, device_id=seeded["device_id"], reason="fall detected"
        )
    unknown = await client.post(
        "/api/v1/twilio/sms", data={"From": "+19998887777", "Body": "ack"}
    )
    assert unknown.status_code == 200
    chatter = await client.post(
        "/api/v1/twilio/sms", data={"From": "+13125550100", "Body": "how is she?"}
    )
    assert chatter.status_code == 200
    with db_factory() as db:
        from meemoo.core.models import Alert

        row = db.get(Alert, alert.id)
        assert row is not None and row.state == "open"  # nothing acked
