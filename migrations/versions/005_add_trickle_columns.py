"""add missing trickle bomb columns to games table

Revision ID: 005
Revises: 004
Create Date: 2024-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS trickle_enabled BOOLEAN NOT NULL DEFAULT false"
    ))
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS trickle_bombs_per_interval INTEGER NOT NULL DEFAULT 1"
    ))
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS trickle_interval_minutes INTEGER NOT NULL DEFAULT 10"
    ))
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS last_trickle_at TIMESTAMP WITH TIME ZONE"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS trickle_enabled"))
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS trickle_bombs_per_interval"))
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS trickle_interval_minutes"))
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS last_trickle_at"))
