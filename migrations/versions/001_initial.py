"""initial migration — squashed schema matching current ORM models

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("DO $$ BEGIN CREATE TYPE role AS ENUM ('TEAM', 'GAMEMASTER', 'AI'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    conn.execute(sa.text("DO $$ BEGIN CREATE TYPE eventtype AS ENUM ('TEAM_JOINED', 'SHIP_PLACED', 'SHIP_REMOVED', 'BOMB_THROWN', 'CODE_REDEEMED', 'LOCATION_ADDED', 'LOCATION_REMOVED', 'GAME_STARTED', 'GAME_ENDED', 'BOMBS_ADDED', 'TEAM_RESET'); EXCEPTION WHEN duplicate_object THEN null; END $$"))
    # DB enum uses WAITING (Python member name); app-layer GameStatusField uses PREPARING = "preparing".
    # These are distinct: DB stores WAITING, state reconstruction translates to PREPARING.
    conn.execute(sa.text("DO $$ BEGIN CREATE TYPE gamestatus AS ENUM ('WAITING', 'STARTED', 'ENDED'); EXCEPTION WHEN duplicate_object THEN null; END $$"))

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS admins ("
            "id SERIAL NOT NULL, "
            "token VARCHAR(20) NOT NULL, "
            "PRIMARY KEY (id), "
            "UNIQUE (token)"
            ")"
        )
    )

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS games ("
            "id UUID NOT NULL, "
            "name VARCHAR(100), "
            "status GAMESTATUS NOT NULL DEFAULT 'WAITING', "
            "gm_token VARCHAR(20) NOT NULL, "
            "total_locations_needed INTEGER NOT NULL DEFAULT 33, "
            "started_at TIMESTAMP WITH TIME ZONE, "
            "ended_at TIMESTAMP WITH TIME ZONE, "
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
            "PRIMARY KEY (id), "
            "UNIQUE (gm_token)"
            ")"
        )
    )

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS team_tokens ("
            "id SERIAL NOT NULL, "
            "game_id UUID NOT NULL REFERENCES games(id), "
            "token VARCHAR(20) NOT NULL, "
            "color VARCHAR(20) NOT NULL, "
            "PRIMARY KEY (id), "
            "UNIQUE (token)"
            ")"
        )
    )

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS players ("
            "id SERIAL NOT NULL, "
            "game_id UUID NOT NULL REFERENCES games(id), "
            "name VARCHAR(100) NOT NULL, "
            "color VARCHAR(20) NOT NULL, "
            "chat_id BIGINT, "
            "role ROLE NOT NULL DEFAULT 'TEAM', "
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
            "PRIMARY KEY (id), "
            "UNIQUE (game_id, color)"
            ")"
        )
    )

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS game_events ("
            "id SERIAL NOT NULL, "
            "game_id UUID NOT NULL REFERENCES games(id), "
            "event_type EVENTTYPE NOT NULL, "
            "payload JSON NOT NULL, "
            "player_id INTEGER, "
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
            "PRIMARY KEY (id)"
            ")"
        )
    )

    conn.execute(
        sa.text(
            "CREATE TABLE IF NOT EXISTS locations ("
            "id SERIAL NOT NULL, "
            "game_id UUID NOT NULL REFERENCES games(id), "
            "number INTEGER NOT NULL, "
            "latitude FLOAT NOT NULL, "
            "longitude FLOAT NOT NULL, "
            "code VARCHAR(20) NOT NULL, "
            "bomb_value INTEGER NOT NULL DEFAULT 1, "
            "created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), "
            "PRIMARY KEY (id), "
            "UNIQUE (game_id, number)"
            ")"
        )
    )

    # Seed default admin if none exists
    existing_admin = conn.execute(
        sa.text("SELECT id FROM admins LIMIT 1")
    ).fetchone()
    if not existing_admin:
        conn.execute(
            sa.text("INSERT INTO admins (token) VALUES (:token)"),
            {"token": "admin"},
        )


def downgrade() -> None:
    op.drop_table("locations")
    op.drop_table("game_events")
    op.drop_table("players")
    op.drop_table("team_tokens")
    op.drop_table("games")
    op.drop_table("admins")
    conn = op.get_bind()
    conn.execute(sa.text("DROP TYPE IF EXISTS role"))
    conn.execute(sa.text("DROP TYPE IF EXISTS eventtype"))
    conn.execute(sa.text("DROP TYPE IF EXISTS gamestatus"))
