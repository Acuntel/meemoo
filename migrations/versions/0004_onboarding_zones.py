"""Onboarding wizard tables (Amendments A1/A3/A6): onboarding_records,
room_captures, no_go_zones, plus devices.pairing_code — the code printed on
the aircraft that the replacement-unit flow binds to this base station.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("pairing_code", sa.String(length=20), nullable=True))
    op.create_table(
        "onboarding_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("dwelling_type", sa.String(length=30), nullable=True),
        sa.Column("step", sa.String(length=30), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_onboarding_records_device_id"),
        "onboarding_records",
        ["device_id"],
        unique=True,
    )
    op.create_table(
        "room_captures",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("room", sa.String(length=120), nullable=False),
        sa.Column("path", sa.String(length=400), nullable=False),
        sa.Column("x", sa.Float(), nullable=True),
        sa.Column("y", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_room_captures_device_id"), "room_captures", ["device_id"], unique=False
    )
    op.create_table(
        "no_go_zones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("w", sa.Float(), nullable=False),
        sa.Column("h", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_no_go_zones_device_id"), "no_go_zones", ["device_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_no_go_zones_device_id"), table_name="no_go_zones")
    op.drop_table("no_go_zones")
    op.drop_index(op.f("ix_room_captures_device_id"), table_name="room_captures")
    op.drop_table("room_captures")
    op.drop_index(op.f("ix_onboarding_records_device_id"), table_name="onboarding_records")
    op.drop_table("onboarding_records")
    op.drop_column("devices", "pairing_code")
