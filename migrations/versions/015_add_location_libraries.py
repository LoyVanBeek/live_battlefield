"""add reusable location sets (a location library)

Adds one game-agnostic library so a whole location layout can be reused across
games. A set is a named snapshot of locations (position, code, bomb value, mode)
and each location's check-in quiz. Quizzes are stored relationally, exactly like
the in-game location quiz and the normal quiz templates, rather than as a JSON
column.

Revision ID: 015
Revises: 014
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # --- Location sets (a named, reusable layout) ---
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS location_sets ("
        "id SERIAL NOT NULL, "
        "name VARCHAR(200) NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
        "PRIMARY KEY (id), "
        "UNIQUE (name)"
        ")"
    ))
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS location_set_locations ("
        "id SERIAL NOT NULL, "
        "set_id INTEGER NOT NULL REFERENCES location_sets(id), "
        "number INTEGER NOT NULL, "
        "latitude FLOAT NOT NULL, "
        "longitude FLOAT NOT NULL, "
        "code VARCHAR(20) NOT NULL, "
        "bomb_value INTEGER NOT NULL DEFAULT 1, "
        "quiz_mode VARCHAR(10) NOT NULL DEFAULT 'code', "
        "PRIMARY KEY (id)"
        ")"
    ))
    # A location's check-in quiz, stored exactly like location_quiz_questions.
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS location_set_questions ("
        "id SERIAL NOT NULL, "
        "set_location_id INTEGER NOT NULL REFERENCES location_set_locations(id), "
        "question_text VARCHAR(500) NOT NULL, "
        "\"order\" INTEGER NOT NULL DEFAULT 0, "
        "source_url VARCHAR(1000), "
        "PRIMARY KEY (id)"
        ")"
    ))
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS location_set_answers ("
        "id SERIAL NOT NULL, "
        "question_id INTEGER NOT NULL REFERENCES location_set_questions(id), "
        "answer_text VARCHAR(500) NOT NULL, "
        "bomb_value INTEGER NOT NULL DEFAULT 0, "
        "is_correct BOOLEAN NOT NULL DEFAULT false, "
        "PRIMARY KEY (id)"
        ")"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS location_set_answers"))
    conn.execute(sa.text("DROP TABLE IF EXISTS location_set_questions"))
    conn.execute(sa.text("DROP TABLE IF EXISTS location_set_locations"))
    conn.execute(sa.text("DROP TABLE IF EXISTS location_sets"))
