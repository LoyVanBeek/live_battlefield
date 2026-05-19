"""initial migration

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.database import Base
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    op.drop_table("game_settings")
    op.drop_table("locations")
    op.drop_table("game_events")
    op.drop_table("players")
