"""Engine + session factory for the SQLite store.

Production schema comes from Alembic migrations (``migrations/``); tests may
use :func:`create_all` directly — both paths produce the append-only triggers
because they hang off SQLAlchemy DDL events (see models/audit.py).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from meemoo.core.config import get_settings
from meemoo.core.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def make_engine(db_path: str | Path) -> Engine:
    """Engine for a SQLite file (or ':memory:'), foreign keys enforced."""
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn: object, _record: object) -> None:
        cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def get_engine() -> Engine:
    """Process-wide engine, path from settings."""
    global _engine
    if _engine is None:
        _engine = make_engine(get_settings().meemoo_db_path)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Process-wide session factory bound to :func:`get_engine`."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


def create_all(engine: Engine) -> None:
    """Create the full schema (incl. append-only triggers) — tests/dev only."""
    Base.metadata.create_all(engine)


def reset_db() -> None:
    """Dispose the process-wide engine/factory (tests that re-root the cwd).

    The engine binds a *relative* SQLite path at connect time; a test that
    boots the runtime in a fresh tmp cwd must drop the previous test's pooled
    connections or reads silently hit the old file.
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
