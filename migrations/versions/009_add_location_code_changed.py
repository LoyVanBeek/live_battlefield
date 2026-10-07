"""add location_code_changed event type

Revision ID: 009
Revises: 008
Create Date: 2026-10-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'LOCATION_CODE_CHANGED'"
    ))


def downgrade() -> None:
    # PostgreSQL does not support removing values from an enum type.
    pass
