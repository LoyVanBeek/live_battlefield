"""add paused_until column to games table

Revision ID: 006
Revises: 005
Create Date: 2024-01-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS paused_until TIMESTAMP WITH TIME ZONE"
    ))
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'TEAM_RENAMED'"
    ))
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'TEAM_REMOVED'"
    ))
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'GAME_PAUSED'"
    ))
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'GAME_RESUMED'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS paused_until"))
    # Note: PostgreSQL doesn't support removing values from enums without recreating the type
