"""Add conversations.trigger — who initiated the session ("ptt"/"wake" =
user, "checkin" = robot). The engagement-trajectory metric (Constitution
Art. VIII §1) is user-initiated share over time; that needs the initiator
stored per session (research 07 §F.1–2).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("trigger", sa.String(length=20), nullable=False, server_default="unknown"),
    )


def downgrade() -> None:
    op.drop_column("conversations", "trigger")
