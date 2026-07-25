"""FastAPI dependencies. Tests override ``get_db`` via dependency_overrides."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from meemoo.core.db import get_session_factory


def get_db() -> Iterator[Session]:
    """One DB session per request, bound to the process-wide engine."""
    factory = get_session_factory()
    with factory() as session:
        yield session
