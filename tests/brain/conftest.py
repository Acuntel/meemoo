"""Brain test fixtures: file-backed DB + seeded device/person, no creds."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.core.config import get_settings
from meemoo.core.db import create_all, make_engine
from meemoo.core.models import Device, Person


@pytest.fixture(autouse=True)
def _isolate_settings_cache() -> Iterator[None]:
    """Brain tests toggle credential env vars — never leak a cached Settings."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_factory(tmp_path: Path) -> sessionmaker[DbSession]:
    engine = make_engine(tmp_path / "brain.db")
    create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def seeded(db_factory: sessionmaker[DbSession]) -> tuple[int, int]:
    """A device + person; returns (device_id, person_id)."""
    with db_factory() as db:
        device = Device(name="test-meemoo")
        db.add(device)
        db.flush()
        person = Person(device_id=device.id, name="Ruth", preferred_name="Ruth")
        db.add(person)
        db.commit()
        return int(device.id), int(person.id)
