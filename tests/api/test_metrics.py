"""Research-credibility metrics: real calcs, labeled demo mode, CSV export."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from meemoo.core.models import Conversation, Message


def _seed_conversations(factory: sessionmaker[Session]) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    with factory() as db:
        for days_ago, trigger in ((2, "ptt"), (1, "checkin"), (0, "ptt")):
            started = now - timedelta(days=days_ago, hours=2)
            conversation = Conversation(
                device_id=1, trigger=trigger, started_at=started,
                ended_at=started + timedelta(minutes=4),
            )
            db.add(conversation)
            db.flush()
            db.add(Message(conversation_id=conversation.id, role="user", content="hi"))
            db.add(Message(
                conversation_id=conversation.id, role="assistant", content="hello",
            ))
        db.commit()


def test_engagement_series_counts_user_initiated(
    api_client: TestClient, db_factory: sessionmaker[Session]
) -> None:
    _seed_conversations(db_factory)
    body = api_client.get(
        "/api/v1/metrics/engagement", params={"days": 7}
    ).json()
    assert body["synthetic"] is False
    total_sessions = sum(d["sessions"] for d in body["series"])
    total_user = sum(d["user_initiated"] for d in body["series"])
    assert total_sessions == 3
    assert total_user == 2
    today = body["series"][-1]
    assert today["sessions"] == 1
    assert today["minutes"] > 0


def test_demo_mode_is_always_labeled_synthetic(api_client: TestClient) -> None:
    for endpoint in (
        "/api/v1/metrics/engagement",
        "/api/v1/metrics/adherence",
        "/api/v1/metrics/human-contact",
        "/api/v1/metrics/abandonment",
        "/api/v1/metrics/summary",
    ):
        body = api_client.get(endpoint, params={"demo": "true"}).json()
        assert body["synthetic"] is True, endpoint
        real = api_client.get(endpoint).json()
        assert real["synthetic"] is False, endpoint


def test_adherence_is_honestly_empty_without_reminder_events(
    api_client: TestClient,
) -> None:
    body = api_client.get("/api/v1/metrics/adherence").json()
    assert body["has_data"] is False
    assert body["completion_rate"] is None


def test_human_contact_log_and_summary(api_client: TestClient) -> None:
    created = api_client.post(
        "/api/v1/devices/1/human-contact", json={"kind": "call", "note": "called mom"}
    )
    assert created.status_code == 201
    body = api_client.get("/api/v1/metrics/human-contact").json()
    assert body["total"] == 1
    assert body["by_kind"] == {"call": 1}


def test_false_alarm_headline_and_summary(api_client: TestClient) -> None:
    headline = api_client.get("/api/v1/metrics/false-alarms").json()
    assert headline["false_alarms_last_7_days"] == 0
    summary = api_client.get("/api/v1/metrics/summary").json()
    assert summary["false_alarms"]["false_alarms_last_7_days"] == 0
    assert "abandonment" in summary


def test_csv_export(api_client: TestClient, db_factory: sessionmaker[Session]) -> None:
    _seed_conversations(db_factory)
    response = api_client.get("/api/v1/export", params={"table": "conversations"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.strip().splitlines()
    assert lines[0].startswith("id,device_id")
    assert len(lines) == 4  # header + 3 rows
    assert api_client.get("/api/v1/export", params={"table": "nope"}).status_code == 404
