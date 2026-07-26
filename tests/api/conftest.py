"""API test fixtures: API-only app (runtime off) + isolated in-memory DB."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from meemoo.api.deps import get_db
from meemoo.core.bus_registry import set_active_bus
from meemoo.core.config import get_settings
from meemoo.core.models import Base, Device, Person

_CRED_VARS = [
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "OLLAMA_URL",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_FROM_NUMBER",
    "MEEMOO_FERNET_KEY",
]


@pytest.fixture
def db_factory() -> Iterator[sessionmaker[Session]]:
    """In-memory DB with full schema + a seeded device/person."""
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(Device(id=1, name="Meemoo"))
        db.add(Person(id=1, device_id=1, name="Ruth", room="living room"))
        db.commit()
    yield factory
    engine.dispose()


@pytest.fixture
def api_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: object,
    db_factory: sessionmaker[Session],
) -> Iterator[TestClient]:
    """TestClient against the full app in API-only mode with the test DB."""
    for var in _CRED_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MEEMOO_RUNTIME", "0")
    monkeypatch.chdir(tmp_path)  # type: ignore[arg-type]
    get_settings.cache_clear()

    from meemoo.api.app import create_app

    app = create_app()

    def _get_db() -> Iterator[Session]:
        with db_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as client:
        yield client
    set_active_bus(None)
    get_settings.cache_clear()
