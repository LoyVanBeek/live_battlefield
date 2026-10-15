"""add location quiz mode

Adds a per-location visit mode plus location-scoped quiz questions/answers, so a
location can be proved by answering a multiple-choice question instead of (or in
addition to) the printed code.

Revision ID: 014
Revises: 013
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "ALTER TABLE locations "
        "ADD COLUMN IF NOT EXISTS quiz_mode VARCHAR(10) NOT NULL DEFAULT 'code'"
    ))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS location_quiz_questions (
            id SERIAL NOT NULL,
            game_id UUID NOT NULL REFERENCES games(id),
            location_number INTEGER NOT NULL,
            question_text VARCHAR(500) NOT NULL,
            "order" INTEGER NOT NULL DEFAULT 0,
            source_url VARCHAR(1000),
            PRIMARY KEY (id)
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS location_quiz_answers (
            id SERIAL NOT NULL,
            question_id INTEGER NOT NULL REFERENCES location_quiz_questions(id),
            answer_text VARCHAR(500) NOT NULL,
            bomb_value INTEGER NOT NULL DEFAULT 0,
            is_correct BOOLEAN NOT NULL DEFAULT false,
            PRIMARY KEY (id)
        )
    """))
    conn.execute(sa.text(
        "ALTER TYPE eventtype ADD VALUE IF NOT EXISTS 'LOCATION_QUIZ_ANSWERED'"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS location_quiz_answers"))
    conn.execute(sa.text("DROP TABLE IF EXISTS location_quiz_questions"))
    conn.execute(sa.text("ALTER TABLE locations DROP COLUMN IF EXISTS quiz_mode"))
    # PostgreSQL does not support removing values from an enum type.
