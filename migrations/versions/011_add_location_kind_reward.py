"""add kind and reward columns to locations table

Revision ID: 011
Revises: 010
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE locations ADD COLUMN IF NOT EXISTS kind VARCHAR(20)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE locations ADD COLUMN IF NOT EXISTS reward JSONB NOT NULL DEFAULT '{}'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE locations DROP COLUMN IF EXISTS reward"))
    conn.execute(sa.text("ALTER TABLE locations DROP COLUMN IF EXISTS kind"))
