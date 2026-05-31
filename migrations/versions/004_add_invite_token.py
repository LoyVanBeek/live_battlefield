"""add invite_token column to games table

Revision ID: 004
Revises: 003
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import secrets
import string


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def generate_token() -> str:
    raw = "".join(secrets.choice(string.ascii_lowercase) for _ in range(9))
    return f"{raw[:3]}-{raw[3:6]}-{raw[6:]}"


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "ALTER TABLE games ADD COLUMN IF NOT EXISTS invite_token VARCHAR(20)"
        )
    )

    result = conn.execute(sa.text("SELECT id FROM games WHERE invite_token IS NULL"))
    rows = result.fetchall()
    for row in rows:
        token = generate_token()
        while True:
            existing = conn.execute(
                sa.text("SELECT id FROM games WHERE invite_token = :token"),
                {"token": token},
            ).fetchone()
            if not existing:
                break
            token = generate_token()
        conn.execute(
            sa.text("UPDATE games SET invite_token = :token WHERE id = :id"),
            {"token": token, "id": row[0]},
        )

    conn.execute(
        sa.text(
            "ALTER TABLE games ALTER COLUMN invite_token SET NOT NULL"
        )
    )
    conn.execute(
        sa.text(
            "ALTER TABLE games DROP CONSTRAINT IF EXISTS games_invite_token_key"
        )
    )
    conn.execute(
        sa.text(
            "ALTER TABLE games ADD CONSTRAINT games_invite_token_key UNIQUE (invite_token)"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("ALTER TABLE games DROP COLUMN invite_token")
    )
