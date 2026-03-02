"""add_bomb_value_to_locations

Revision ID: add_bomb_value
Revises:
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa


revision = "add_bomb_value"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "locations",
        sa.Column("bomb_value", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("locations", "bomb_value")
