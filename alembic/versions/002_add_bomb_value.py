"""add bomb_value to locations

Revision ID: 002
Revises: 001
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE locations ADD COLUMN IF NOT EXISTS bomb_value INTEGER NOT NULL DEFAULT 1"
    )


def downgrade() -> None:
    op.drop_column("locations", "bomb_value")
