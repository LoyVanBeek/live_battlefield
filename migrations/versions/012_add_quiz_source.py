"""add source_url to quiz questions

Revision ID: 012
Revises: 011
Create Date: 2026-10-11 00:00:00.000000

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
        "ALTER TABLE quiz_questions "
        "ADD COLUMN IF NOT EXISTS source_url VARCHAR(1000)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE quiz_template_questions "
        "ADD COLUMN IF NOT EXISTS source_url VARCHAR(1000)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE quiz_questions DROP COLUMN IF EXISTS source_url"))
    conn.execute(sa.text("ALTER TABLE quiz_template_questions DROP COLUMN IF EXISTS source_url"))
