"""Add multi-game support: Game, SuperAdmin, TeamToken tables + game_id on existing tables

Revision ID: 005
Revises: 004
Create Date: 2026-05-24

"""

from alembic import op
import sqlalchemy as sa
import uuid

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create new tables idempotently
    conn.execute(sa.text("CREATE TABLE IF NOT EXISTS super_admins (id SERIAL NOT NULL, token VARCHAR(20) NOT NULL, PRIMARY KEY (id), UNIQUE (token))"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS games (
            id UUID NOT NULL,
            name VARCHAR(100),
            status VARCHAR(20) NOT NULL DEFAULT 'waiting',
            gm_token VARCHAR(20) NOT NULL,
            total_locations_needed INTEGER NOT NULL DEFAULT 33,
            started_at TIMESTAMP WITH TIME ZONE,
            ended_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            UNIQUE (gm_token)
        )
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS team_tokens (
            id SERIAL NOT NULL,
            game_id UUID NOT NULL REFERENCES games(id),
            token VARCHAR(20) NOT NULL,
            color VARCHAR(20) NOT NULL,
            PRIMARY KEY (id),
            UNIQUE (token)
        )
    """))

    # 2. Add game_id columns idempotently
    for table in ("game_events", "players", "locations"):
        conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS game_id UUID"))

    # 3. Create or find the legacy game
    result = conn.execute(sa.text("SELECT id FROM games ORDER BY created_at ASC LIMIT 1")).fetchone()
    if result:
        legacy_game_id = result[0]
    else:
        legacy_game_id = str(uuid.uuid4())
        # Check if GameSettings has data to use as gm_token
        settings = conn.execute(sa.text("SELECT admin_token, status, total_locations_needed, started_at FROM game_settings LIMIT 1")).fetchone()
        gm_token = settings[0] if settings and settings[0] else "legacy-admin"
        status = settings[1] if settings else "waiting"
        total_locations_needed = settings[2] if settings else 33
        started_at = settings[3] if settings else None

        if conn.dialect.name == "postgresql":
            conn.execute(
                sa.text(
                    "INSERT INTO games (id, name, status, gm_token, total_locations_needed, started_at, created_at) "
                    "VALUES (:id, :name, :status, :gm_token, :total_locations_needed, :started_at, now())"
                ),
                {
                    "id": legacy_game_id,
                    "name": "Legacy Game",
                    "status": status,
                    "gm_token": gm_token,
                    "total_locations_needed": total_locations_needed,
                    "started_at": started_at,
                },
            )

    # 4. Backfill game_id on existing rows
    for table in ("game_events", "players", "locations"):
        conn.execute(
            sa.text(f"UPDATE {table} SET game_id = :game_id WHERE game_id IS NULL"),
            {"game_id": legacy_game_id},
        )

    # 5. Create SuperAdmin if none exists
    existing_admin = conn.execute(sa.text("SELECT id FROM super_admins LIMIT 1")).fetchone()
    if not existing_admin:
        settings = conn.execute(sa.text("SELECT admin_token FROM game_settings LIMIT 1")).fetchone()
        token = settings[0] if settings and settings[0] else str(uuid.uuid4()).replace("-", "")[:9]
        conn.execute(sa.text("INSERT INTO super_admins (token) VALUES (:token)"), {"token": token})

    # 6. Make game_id non-nullable
    for table in ("game_events", "players", "locations"):
        conn.execute(sa.text(f"ALTER TABLE {table} ALTER COLUMN game_id SET NOT NULL"))

    # 7. Constraint changes for players
    conn.execute(sa.text("ALTER TABLE players DROP CONSTRAINT IF EXISTS players_color_key"))
    conn.execute(sa.text("ALTER TABLE players DROP CONSTRAINT IF EXISTS uq_player_game_color"))
    conn.execute(sa.text("ALTER TABLE players ADD CONSTRAINT uq_player_game_color UNIQUE (game_id, color)"))

    # 8. Constraint changes for locations
    conn.execute(sa.text("ALTER TABLE locations DROP CONSTRAINT IF EXISTS locations_number_key"))
    conn.execute(sa.text("ALTER TABLE locations DROP CONSTRAINT IF EXISTS uq_location_game_number"))
    conn.execute(sa.text("ALTER TABLE locations ADD CONSTRAINT uq_location_game_number UNIQUE (game_id, number)"))

    # 9. Drop old GameSettings table
    conn.execute(sa.text("DROP TABLE IF EXISTS game_settings"))


def downgrade() -> None:
    conn = op.get_bind()

    # 1. Recreate GameSettings
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS game_settings (
            id SERIAL NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'waiting',
            total_locations_needed INTEGER NOT NULL DEFAULT 33,
            started_at TIMESTAMP WITHOUT TIME ZONE,
            admin_token VARCHAR(20) NOT NULL DEFAULT '',
            PRIMARY KEY (id)
        )
    """))

    # Restore settings from the legacy game
    legacy_game = conn.execute(
        sa.text("SELECT status, gm_token, total_locations_needed, started_at FROM games ORDER BY created_at ASC LIMIT 1")
    ).fetchone()

    if legacy_game and not conn.execute(sa.text("SELECT id FROM game_settings LIMIT 1")).fetchone():
        conn.execute(
            sa.text(
                "INSERT INTO game_settings (status, total_locations_needed, started_at, admin_token) "
                "VALUES (:status, :total_locations_needed, :started_at, :admin_token)"
            ),
            {
                "status": legacy_game[0],
                "total_locations_needed": legacy_game[1],
                "started_at": legacy_game[3],
                "admin_token": legacy_game[1],  # gm_token as admin_token
            },
        )

    # 2. Drop composite unique constraints
    conn.execute(sa.text("ALTER TABLE players DROP CONSTRAINT IF EXISTS uq_player_game_color"))
    conn.execute(sa.text("ALTER TABLE locations DROP CONSTRAINT IF EXISTS uq_location_game_number"))

    # 3. Restore simple unique constraints
    conn.execute(sa.text("ALTER TABLE players ADD CONSTRAINT players_color_key UNIQUE (color)"))
    conn.execute(sa.text("ALTER TABLE locations ADD CONSTRAINT locations_number_key UNIQUE (number)"))

    # 4. Drop game_id columns
    for table in ("game_events", "players", "locations"):
        conn.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS game_id"))

    # 5. Drop new tables
    conn.execute(sa.text("DROP TABLE IF EXISTS team_tokens"))
    conn.execute(sa.text("DROP TABLE IF EXISTS games"))
    conn.execute(sa.text("DROP TABLE IF EXISTS super_admins"))
