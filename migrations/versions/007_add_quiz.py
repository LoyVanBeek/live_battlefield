"""add quiz mode tables and columns

Revision ID: 007
Revises: 006
Create Date: 2024-01-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS quiz_enabled BOOLEAN NOT NULL DEFAULT false"
    ))
    conn.execute(sa.text(
        "ALTER TABLE games ADD COLUMN IF NOT EXISTS quiz_total_bombs INTEGER NOT NULL DEFAULT 100"
    ))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id SERIAL NOT NULL,
            game_id UUID NOT NULL REFERENCES games(id),
            question_text VARCHAR(500) NOT NULL,
            "order" INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (id)
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS quiz_answers (
            id SERIAL NOT NULL,
            question_id INTEGER NOT NULL REFERENCES quiz_questions(id),
            answer_text VARCHAR(500) NOT NULL,
            bomb_value INTEGER NOT NULL DEFAULT 0,
            is_correct BOOLEAN NOT NULL DEFAULT false,
            PRIMARY KEY (id)
        )
    """))
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'QUIZ_ANSWERED'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS quiz_answers"))
    conn.execute(sa.text("DROP TABLE IF EXISTS quiz_questions"))
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS quiz_enabled"))
    conn.execute(sa.text("ALTER TABLE games DROP COLUMN IF EXISTS quiz_total_bombs"))
