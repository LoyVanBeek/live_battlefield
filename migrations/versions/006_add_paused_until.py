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


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS paused_until"))
