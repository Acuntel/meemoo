"""Care + audit tables: events, conversations, messages, consent_records,
alerts, memory_facts, audit_log — plus the append-only SQLite triggers that
make events/audit_log reject UPDATE and DELETE (Constitution Art. II §6).

memory_facts carries NO biometric columns by design (Art. V §1).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_APPEND_ONLY = ("events", "audit_log")


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("thumbnail_path", sa.String(length=400), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_device_ts", "events", ["device_id", "ts"], unique=False)
    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("mood_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_device_id"), "conversations", ["device_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_messages_conversation_id"), "messages", ["conversation_id"])
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("consenting_party", sa.String(length=120), nullable=False),
        sa.Column("is_surrogate", sa.Boolean(), nullable=False),
        sa.Column("surrogate_relationship", sa.String(length=60), nullable=True),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consent_records_device_id"), "consent_records", ["device_id"])
    op.create_index(op.f("ix_consent_records_person_id"), "consent_records", ["person_id"])
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("level", sa.String(length=4), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by_contact_id", sa.Integer(), nullable=True),
        sa.Column("evidence_event_id", sa.Integer(), nullable=True),
        sa.Column("model_version", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("threshold_version", sa.String(length=80), nullable=True),
        sa.ForeignKeyConstraint(["acknowledged_by_contact_id"], ["contacts.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["evidence_event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alerts_device_id"), "alerts", ["device_id"])
    op.create_table(
        "memory_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source_conversation_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.ForeignKeyConstraint(["source_conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_facts_device_id"), "memory_facts", ["device_id"])
    op.create_index(op.f("ix_memory_facts_person_id"), "memory_facts", ["person_id"])
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("from_state", sa.String(length=40), nullable=True),
        sa.Column("to_state", sa.String(length=40), nullable=True),
        sa.Column("trigger", sa.String(length=200), nullable=True),
        sa.Column("evidence_event_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=80), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=True),
        sa.Column("threshold_version", sa.String(length=80), nullable=True),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["evidence_event_id"], ["events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_device_ts", "audit_log", ["device_id", "ts"], unique=False)
    # Append-only enforcement lives IN the database, not just in app code.
    for table in _APPEND_ONLY:
        op.execute(
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_update "
            f"BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER IF NOT EXISTS {table}_no_delete "
            f"BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
        )


def downgrade() -> None:
    for table in _APPEND_ONLY:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_update")
        op.execute(f"DROP TRIGGER IF EXISTS {table}_no_delete")
    for table in (
        "audit_log",
        "memory_facts",
        "alerts",
        "consent_records",
        "messages",
        "conversations",
        "events",
    ):
        op.drop_table(table)
