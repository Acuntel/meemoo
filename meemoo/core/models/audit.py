"""Append-only tables: events + audit_log (the flight recorder).

Constitution Art. II §6: every check-in, detection, escalation, flight, and
config change is logged; the audit log is append-only. Enforcement is IN THE
DATABASE — SQLite triggers abort any UPDATE or DELETE on these tables — and
the triggers are attached via SQLAlchemy DDL events so both
``metadata.create_all`` (tests) and Alembic migrations produce them.

``audit_log`` is additionally tamper-evident: each row carries
``row_hash = sha256(prev_hash | canonical-row-content)``, a hash chain that
:func:`verify_audit_chain` can walk. Escalation-relevant rows carry
model/prompt/threshold version stamps (see :mod:`meemoo.core.versioning`).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import DDL, ForeignKey, Index, String, Text, event
from sqlalchemy.orm import Mapped, Session, mapped_column

from meemoo.core.models.base import Base, utcnow
from meemoo.core.versioning import get_versions

_GENESIS_HASH = "0" * 64


class Event(Base):
    """Append-only typed system event (detections, transitions, flights)."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_device_ts", "device_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    type: Mapped[str] = mapped_column(String(80), nullable=False)  # bus topic string
    payload: Mapped[dict[str, object]] = mapped_column(nullable=False, default=dict)
    thumbnail_path: Mapped[str | None] = mapped_column(String(400))


class AuditLog(Base):
    """Append-only, hash-chained audit row — the liability record."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_device_ts", "device_id", "ts"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(nullable=False, default=utcnow)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)  # module/user id
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(40))
    to_state: Mapped[str | None] = mapped_column(String(40))
    trigger: Mapped[str | None] = mapped_column(String(200))
    evidence_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    detail: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    threshold_version: Mapped[str | None] = mapped_column(String(80))
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)


APPEND_ONLY_TABLES = ("events", "audit_log")


def _append_only_ddl(table: str) -> list[DDL]:
    return [
        DDL(  # type: ignore[no-untyped-call]  # sqlalchemy stubs gap
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_update "
            f"BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        ),
        DDL(  # type: ignore[no-untyped-call]  # sqlalchemy stubs gap
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete "
            f"BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        ),
    ]


for _table, _model in (("events", Event), ("audit_log", AuditLog)):
    for _ddl in _append_only_ddl(_table):
        event.listen(_model.__table__, "after_create", _ddl)


def _canonical_ts(ts: datetime) -> str:
    """Naive-UTC isoformat — identical before and after a SQLite round trip."""
    if ts.tzinfo is not None:
        ts = ts.astimezone(UTC).replace(tzinfo=None)
    return ts.isoformat()


def _content_hash(prev_hash: str, row: AuditLog) -> str:
    content = json.dumps(
        {
            "device_id": row.device_id,
            "ts": _canonical_ts(row.ts),
            "actor": row.actor,
            "action": row.action,
            "from_state": row.from_state,
            "to_state": row.to_state,
            "trigger": row.trigger,
            "evidence_event_id": row.evidence_event_id,
            "detail": row.detail,
            "model_version": row.model_version,
            "prompt_version": row.prompt_version,
            "threshold_version": row.threshold_version,
        },
        sort_keys=True,
    )
    return hashlib.sha256(f"{prev_hash}|{content}".encode()).hexdigest()


def append_audit(
    session: Session,
    *,
    device_id: int,
    actor: str,
    action: str,
    from_state: str | None = None,
    to_state: str | None = None,
    trigger: str | None = None,
    evidence_event_id: int | None = None,
    detail: str | None = None,
) -> AuditLog:
    """Append one hash-chained audit row, stamped with current versions.

    The caller owns the transaction; this flushes so the row gets its id and
    the chain stays ordered even with several appends per transaction.
    """
    versions = get_versions()
    last = session.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last.row_hash if last is not None else _GENESIS_HASH
    row = AuditLog(
        device_id=device_id,
        ts=utcnow(),
        actor=actor,
        action=action,
        from_state=from_state,
        to_state=to_state,
        trigger=trigger,
        evidence_event_id=evidence_event_id,
        detail=detail,
        model_version=versions.get("model"),
        prompt_version=versions.get("prompt"),
        threshold_version=versions.get("threshold"),
        prev_hash=prev_hash,
    )
    row.row_hash = _content_hash(prev_hash, row)
    session.add(row)
    session.flush()
    return row


def verify_audit_chain(session: Session) -> tuple[bool, int | None]:
    """Walk the whole chain; returns (ok, first_bad_row_id)."""
    prev_hash = _GENESIS_HASH
    for row in session.query(AuditLog).order_by(AuditLog.id.asc()):
        if row.prev_hash != prev_hash or row.row_hash != _content_hash(prev_hash, row):
            return False, row.id
        prev_hash = row.row_hash
    return True, None
