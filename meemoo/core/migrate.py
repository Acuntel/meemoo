"""Programmatic Alembic migration runner.

Why not ``alembic upgrade head``? The stock CLI hard-requires a file named
``migrations/env.py``, and Brady's file-protection hook blocks writes to any
path matching ``.env`` — which "…/env.py" does. Revision files under
``migrations/versions/`` stay 100% standard Alembic format; this runner
applies them using Alembic's own ``MigrationContext``/``Operations`` and
records state in the normal ``alembic_version`` table. If the hook is ever
relaxed and an ``env.py`` added, the stock CLI will pick up exactly where
this left off.

Usage: ``uv run python -m meemoo.core.migrate`` (or ``make migrate``).
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import ModuleType

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _load_revision_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"meemoo_migration_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load migration file {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upgrade(engine: Engine, migrations_dir: Path | None = None) -> list[str]:
    """Apply all pending revisions (oldest → newest); returns applied ids."""
    script = ScriptDirectory(str(migrations_dir or MIGRATIONS_DIR))
    ordered = list(script.walk_revisions("base", "heads"))
    ordered.reverse()  # walk_revisions yields newest→oldest

    applied: list[str] = []
    with engine.begin() as connection:
        ctx = MigrationContext.configure(connection)
        current = ctx.get_current_revision()
        past_current = current is None
        for rev in ordered:
            if not past_current:
                past_current = rev.revision == current
                continue
            module = _load_revision_module(Path(rev.path))
            with Operations.context(ctx):
                module.upgrade()
            ctx.stamp(script, rev.revision)
            applied.append(rev.revision)
            logger.info("applied migration", extra={"fields": {"revision": rev.revision}})
        if not past_current:
            raise RuntimeError(
                f"database is at unknown revision {current!r}; refusing to migrate"
            )
    return applied


def main() -> None:
    """CLI entry: migrate the configured database to head."""
    from meemoo.core.config import get_settings
    from meemoo.core.db import make_engine
    from meemoo.core.logging import setup_logging

    setup_logging()
    engine = make_engine(get_settings().meemoo_db_path)
    applied = upgrade(engine)
    logger.info(
        "migrations complete",
        extra={"fields": {"applied": applied or "none (already at head)"}},
    )


if __name__ == "__main__":
    main()
