"""add TEAM_DEACTIVATED event type

Revision ID: 013
Revises: 012
Create Date: 2026-09-08 00:00:00.000000

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
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'TEAM_DEACTIVATED'"
    ))


def downgrade() -> None:
    # Postgres cannot remove enum values; the value stays unused.
    pass
