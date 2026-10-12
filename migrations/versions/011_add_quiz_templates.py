"""add quiz templates (reusable saved quizzes)

Revision ID: 011
Revises: 010
Create Date: 2026-10-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS quiz_templates ("
        "id SERIAL NOT NULL, "
        "name VARCHAR(200) NOT NULL, "
        "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
        "PRIMARY KEY (id), "
        "UNIQUE (name)"
        ")"
    ))
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS quiz_template_questions ("
        "id SERIAL NOT NULL, "
        "template_id INTEGER NOT NULL REFERENCES quiz_templates(id), "
        "question_text VARCHAR(500) NOT NULL, "
        "\"order\" INTEGER NOT NULL DEFAULT 0, "
        "PRIMARY KEY (id)"
        ")"
    ))
    conn.execute(sa.text(
        "CREATE TABLE IF NOT EXISTS quiz_template_answers ("
        "id SERIAL NOT NULL, "
        "question_id INTEGER NOT NULL REFERENCES quiz_template_questions(id), "
        "answer_text VARCHAR(500) NOT NULL, "
        "bomb_value INTEGER NOT NULL DEFAULT 0, "
        "is_correct BOOLEAN NOT NULL DEFAULT false, "
        "PRIMARY KEY (id)"
        ")"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS quiz_template_answers"))
    conn.execute(sa.text("DROP TABLE IF EXISTS quiz_template_questions"))
    conn.execute(sa.text("DROP TABLE IF EXISTS quiz_templates"))
