"""add SHIELD_ACTIVATED event type

Revision ID: 012
Revises: 011
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'SHIELD_ACTIVATED'"
    ))


def downgrade() -> None:
    # Postgres cannot remove enum values; the value stays unused.
    pass
