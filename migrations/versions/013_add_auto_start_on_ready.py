"""add auto_start_on_ready to games

Revision ID: 013
Revises: 012
Create Date: 2026-10-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE games "
        "ADD COLUMN IF NOT EXISTS auto_start_on_ready BOOLEAN NOT NULL DEFAULT FALSE"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS auto_start_on_ready"))