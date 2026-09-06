"""add scheduled_start_at column to games table

Revision ID: 008
Revises: 007
Create Date: 2024-01-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS scheduled_start_at TIMESTAMP WITH TIME ZONE"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS scheduled_start_at"))
