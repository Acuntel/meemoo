"""Core fleet/provider/flight tables — devices, persons, contacts, settings,
provider_keys, model_config, usage, checkin_schedule, routes, waypoints,
dock_telemetry. All keyed by device_id (fleet-ready from day one).

Revision ID: 0001
Revises:
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("store_transcripts", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("preferred_name", sa.String(length=120), nullable=True),
        sa.Column("room", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_persons_device_id"), "persons", ["device_id"], unique=False)
    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("relationship_label", sa.String(length=60), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("notify_sms", sa.Boolean(), nullable=False),
        sa.Column("notify_call", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_contacts_device_id"), "contacts", ["device_id"], unique=False)
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "key", name="uq_settings_device_key"),
    )
    op.create_index(op.f("ix_settings_device_id"), "settings", ["device_id"], unique=False)
    op.create_table(
        "provider_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "provider", name="uq_provider_keys_device_provider"),
    )
    op.create_index(op.f("ix_provider_keys_device_id"), "provider_keys", ["device_id"])
    op.create_table(
        "model_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "tier", name="uq_model_config_device_tier"),
    )
    op.create_index(op.f("ix_model_config_device_id"), "model_config", ["device_id"], unique=False)
    op.create_table(
        "usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_usage_device_id"), "usage", ["device_id"], unique=False)
    op.create_index(op.f("ix_usage_ts"), "usage", ["ts"], unique=False)
    op.create_table(
        "checkin_schedule",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("time_of_day", sa.String(length=5), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_checkin_schedule_device_id"), "checkin_schedule", ["device_id"], unique=False
    )
    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_routes_device_id"), "routes", ["device_id"], unique=False)
    op.create_table(
        "waypoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_waypoints_route_id"), "waypoints", ["route_id"], unique=False)
    op.create_table(
        "dock_telemetry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("net_buoyancy_gf", sa.Float(), nullable=True),
        sa.Column("load_cell_g", sa.Float(), nullable=True),
        sa.Column("helium_level_pct", sa.Float(), nullable=True),
        sa.Column("charging", sa.Boolean(), nullable=False),
        sa.Column("battery_pct", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dock_telemetry_device_id"), "dock_telemetry", ["device_id"])
    op.create_index(op.f("ix_dock_telemetry_ts"), "dock_telemetry", ["ts"])


def downgrade() -> None:
    for table in (
        "dock_telemetry",
        "waypoints",
        "routes",
        "checkin_schedule",
        "usage",
        "model_config",
        "provider_keys",
        "settings",
        "contacts",
        "persons",
        "devices",
    ):
        op.drop_table(table)
