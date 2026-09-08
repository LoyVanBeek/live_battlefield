"""add TSUNAMI event type and games.last_tsunami_at

Revision ID: 015
Revises: 014
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'TSUNAMI'"
    ))
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS last_tsunami_at TIMESTAMP WITH TIME ZONE"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS last_tsunami_at"))
