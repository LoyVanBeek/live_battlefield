"""add location libraries (reusable location quizzes and location sets)

Adds two game-agnostic libraries so location setup can be reused across games:

* a location-quiz library (named location-scoped question sets), mirroring the
  existing quiz templates, and
* location sets: a named snapshot of a game's locations (position, code, bomb
  value, mode) plus each location's quiz, so a whole layout can be re-applied.

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
    # --- Location-quiz library (game-agnostic, mirrors quiz_templates) ---
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS location_quiz_templates ("
        "id SERIAL NOT NULL, "
        "name VARCHAR(200) NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
        "PRIMARY KEY (id), "
        "UNIQUE (name)"
        ")"
    ))
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS location_quiz_template_questions ("
        "id SERIAL NOT NULL, "
        "template_id INTEGER NOT NULL REFERENCES location_quiz_templates(id), "
        "question_text VARCHAR(500) NOT NULL, "
        "\"order\" INTEGER NOT NULL DEFAULT 0, "
        "source_url VARCHAR(1000), "
        "PRIMARY KEY (id)"
        ")"
    ))
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS location_quiz_template_answers ("
        "id SERIAL NOT NULL, "
        "question_id INTEGER NOT NULL REFERENCES location_quiz_template_questions(id), "
        "answer_text VARCHAR(500) NOT NULL, "
        "bomb_value INTEGER NOT NULL DEFAULT 0, "
        "is_correct BOOLEAN NOT NULL DEFAULT false, "
        "PRIMARY KEY (id)"
        ")"
    ))
    # --- Location sets (a saved layout: positions, codes, bombs, modes + quiz) ---
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
        "quiz_json TEXT, "
        "PRIMARY KEY (id)"
        ")"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS location_set_locations"))
    conn.execute(sa.text("DROP TABLE IF EXISTS location_sets"))
    conn.execute(sa.text("DROP TABLE IF EXISTS location_quiz_template_answers"))
    conn.execute(sa.text("DROP TABLE IF EXISTS location_quiz_template_questions"))
    conn.execute(sa.text("DROP TABLE IF EXISTS location_quiz_templates"))
