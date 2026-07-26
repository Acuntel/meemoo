"""Schema tests: migrations build everything; audit tables are append-only."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session, sessionmaker

from meemoo.core import migrate
from meemoo.core.db import create_all, make_engine
from meemoo.core.models import (
    Contact,
    Device,
    Event,
    MemoryFact,
    Person,
    append_audit,
    verify_audit_chain,
)
from meemoo.core.versioning import reset_versions, set_version

EXPECTED_TABLES = {
    "devices",
    "persons",
    "contacts",
    "settings",
    "provider_keys",
    "model_config",
    "usage",
    "checkin_schedule",
    "routes",
    "waypoints",
    "dock_telemetry",
    "events",
    "conversations",
    "messages",
    "consent_records",
    "alerts",
    "memory_facts",
    "audit_log",
}


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Engine:
    """A real file DB built by the Alembic migration chain (not create_all)."""
    engine = make_engine(tmp_path / "test.db")
    applied = migrate.upgrade(engine)
    assert applied == ["0001", "0002", "0003"]
    return engine


@pytest.fixture
def session(migrated_engine: Engine) -> Iterator[Session]:
    sess = sessionmaker(bind=migrated_engine)()
    yield sess
    sess.close()


def _seed_device(session: Session) -> Device:
    device = Device(name="Meemoo One")
    session.add(device)
    session.flush()
    return device


def test_migration_creates_full_schema(migrated_engine: Engine) -> None:
    tables = set(inspect(migrated_engine).get_table_names())
    assert tables >= EXPECTED_TABLES
    assert "alembic_version" in tables


def test_migration_is_idempotent(migrated_engine: Engine) -> None:
    assert migrate.upgrade(migrated_engine) == []  # already at head


@pytest.mark.parametrize("table", ["audit_log", "events"])
def test_append_only_rejects_update_and_delete(
    session: Session, table: str
) -> None:
    device = _seed_device(session)
    if table == "events":
        session.add(Event(device_id=device.id, type="person.detected"))
        session.flush()
    else:
        append_audit(session, device_id=device.id, actor="test", action="seed")
    session.commit()

    with pytest.raises(DatabaseError, match="append-only"):
        session.execute(text(f"UPDATE {table} SET device_id = 999"))  # noqa: S608
    session.rollback()
    with pytest.raises(DatabaseError, match="append-only"):
        session.execute(text(f"DELETE FROM {table}"))  # noqa: S608
    session.rollback()


def test_create_all_also_installs_append_only_triggers(tmp_path: Path) -> None:
    """The tests/dev schema path must carry the same protection as migrations."""
    engine = make_engine(tmp_path / "createall.db")
    create_all(engine)
    session = sessionmaker(bind=engine)()
    device = _seed_device(session)
    session.add(Event(device_id=device.id, type="person.detected"))
    session.commit()
    with pytest.raises(DatabaseError, match="append-only"):
        session.execute(text("DELETE FROM events"))
    session.rollback()


def test_orm_round_trip(session: Session) -> None:
    device = _seed_device(session)
    person = Person(device_id=device.id, name="Ruth", preferred_name="Ruthie", room="bedroom")
    session.add(person)
    session.flush()
    session.add(
        Contact(device_id=device.id, person_id=person.id, order_index=0, name="Brady",
                relationship_label="grandson", phone="+13120000000")
    )
    session.add(
        MemoryFact(device_id=device.id, person_id=person.id, category="preference",
                   key="hobby", value="gardening")
    )
    session.commit()

    loaded = session.query(Person).one()
    assert loaded.name == "Ruth"
    assert loaded.device.name == "Meemoo One"
    assert session.query(MemoryFact).one().value == "gardening"


def test_no_biometric_columns_anywhere(migrated_engine: Engine) -> None:
    """Constitution Art. V §1: a reviewer must find NO template store."""
    forbidden = ("face", "voiceprint", "biometric", "embedding", "template", "fingerprint")
    inspector = inspect(migrated_engine)
    for table in inspector.get_table_names():
        for column in inspector.get_columns(table):
            name = column["name"].lower()
            assert not any(bad in name for bad in forbidden), f"{table}.{name}"


def test_audit_hash_chain_verifies(session: Session) -> None:
    reset_versions()
    set_version("model", "claude-fable-5@2026-07")
    set_version("threshold", "fall-v0")
    try:
        device = _seed_device(session)
        rows = [
            append_audit(session, device_id=device.id, actor="guardian", action="state",
                         from_state="IDLE", to_state="CHECKING", trigger="checkin.due"),
            append_audit(session, device_id=device.id, actor="guardian", action="state",
                         from_state="CHECKING", to_state="CONCERN", trigger="timeout"),
            append_audit(session, device_id=device.id, actor="guardian", action="state",
                         from_state="CONCERN", to_state="ESCALATE_L1", trigger="no_response"),
        ]
        session.commit()

        assert rows[0].prev_hash == "0" * 64
        assert rows[1].prev_hash == rows[0].row_hash
        assert rows[2].prev_hash == rows[1].row_hash
        assert rows[0].model_version == "claude-fable-5@2026-07"
        assert rows[0].threshold_version == "fall-v0"
        ok, bad_id = verify_audit_chain(session)
        assert ok and bad_id is None
    finally:
        reset_versions()


def test_audit_chain_detects_tampering(session: Session) -> None:
    device = _seed_device(session)
    append_audit(session, device_id=device.id, actor="guardian", action="a")
    tampered = append_audit(session, device_id=device.id, actor="guardian", action="b")
    session.commit()

    # Simulate an attacker with DB access: drop the trigger, rewrite history.
    session.execute(text("DROP TRIGGER audit_log_no_update"))
    session.execute(
        text("UPDATE audit_log SET action = 'covered-up' WHERE id = :id"),
        {"id": tampered.id},
    )
    session.commit()
    session.expire_all()

    ok, bad_id = verify_audit_chain(session)
    assert not ok
    assert bad_id == tampered.id
