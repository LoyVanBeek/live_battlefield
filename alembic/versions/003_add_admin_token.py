"""add admin_token to game_settings

Revision ID: 003
Revises: 002
Create Date: 2026-05-19

"""

from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE game_settings ADD COLUMN IF NOT EXISTS admin_token VARCHAR(20) DEFAULT ''"
    )


def downgrade() -> None:
    op.drop_column("game_settings", "admin_token")
