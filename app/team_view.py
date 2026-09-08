import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import lookup_team_token, get_game_events, get_game
from app.game.state import GameState
from app.game.ships import BOARD_SIZE, SHIP_COUNTS


async def get_team_view(team_token: str, db: AsyncSession) -> dict:
    result = await lookup_team_token(db, team_token)
    if result is None:
        return {"error": True}

    game_id_str, color = result
    game_id = uuid.UUID(game_id_str)
    events = await get_game_events(db, game_id)
    state = GameState.from_events(events)

    game = await get_game(db, game_id)

    own_team = state.teams[color]
    radar_ship = _find_radar_ship(own_team)
    radar_radius = 0
    if game:
        from app.game.specials import SpecialsConfig

        radar_radius = int(SpecialsConfig(game.specials).value("radar_ship", "radius_cells", 3))

    result: dict[str, Any] = {
        "s": state.status.value,
        "ec": len(events),
        "t": _serialize_team(own_team, private=True, status=state.status.value),
        "ts": [
            _serialize_team(
                t,
                private=False,
                status=state.status.value,
                radar_origin=radar_ship.cells if radar_ship and radar_radius > 0 else None,
                radar_radius=radar_radius,
            )
            for t in state.teams.values()
        ],
    }
    if game:
        result["te"] = game.trickle_enabled
        result["ti"] = game.trickle_interval_minutes
        result["tb"] = game.trickle_bombs_per_interval
        result["tl"] = game.last_trickle_at.isoformat() if game.last_trickle_at else ""
        result["mb"] = game.max_bombs
        result["qe"] = game.quiz_enabled
        result["ss"] = game.scheduled_start_at.isoformat() if game.scheduled_start_at else ""
        from app.game.specials import GRANTABLE_SPECIALS, SpecialsConfig

        config = SpecialsConfig(game.specials)
        enabled_specials: list[str] = [bt for bt in GRANTABLE_SPECIALS if config.is_enabled(bt)]
        result["sb"] = enabled_specials
        from datetime import datetime, timezone
        result["pu"] = game.paused_until.isoformat() if game.paused_until and game.paused_until > datetime.now(timezone.utc) else ""
    winner = state.get_winner()
    if winner and state.status.value == "ended":
        result["w"] = winner.name
    return result


def _find_radar_ship(team):
    """The team's alive radar-trait ship, if any."""
    return next((s for s in team.ships if s.has_trait("radar") and not s.is_sunk()), None)


def _serialize_team(
    team,
    private: bool,
    status: str = "preparing",
    radar_origin: list[tuple[int, int]] | None = None,
    radar_radius: int = 0,
) -> dict:
    result: dict = {
        "n": team.name,
        "c": team.color,
        "b": team.bombs,
        "sp": sum(team.placed_ship_types.values()) if status == "preparing" else sum(SHIP_COUNTS.values()) - len(team.get_sunk_ships()),
        "sk": len(team.get_sunk_ships()),
    }
    if private:
        result["sa"] = dict(team.special_ammo)
        result["su"] = team.shielded_until.isoformat() if team.shielded_until else ""
        result["du"] = team.deactivated_until.isoformat() if team.deactivated_until else ""
    elif _find_radar_ship(team):
        # Public badge: opponents know a live radar ship exists — not which one.
        result["rs"] = 1
    result["g"] = _serialize_grid(team, include_ships=private, radar_origin=radar_origin, radar_radius=radar_radius)
    if status == "preparing":
        result["pt"] = dict(team.placed_ship_types)
    return result


def _serialize_grid(
    team,
    include_ships: bool,
    radar_origin: list[tuple[int, int]] | None = None,
    radar_radius: int = 0,
) -> list[list[dict]]:
    grid: list[list[dict]] = []
    for row in range(BOARD_SIZE):
        grid_row: list[dict] = []
        for col in range(BOARD_SIZE):
            cell: dict = {}

            ship = team.get_ship_at(row, col) if team.private_board[row][col] else None
            if include_ships and team.private_board[row][col]:
                cell["p"] = 1
                if ship and ship.is_sunk():
                    cell["k"] = 1
            elif not include_ships and ship and ship.is_sunk():
                # Sunk ships are public: reveal their cells (with sunk flag) to everyone
                cell["p"] = 1
                cell["k"] = 1
            elif (
                not include_ships
                and radar_origin
                and ship is not None
                and _within_radar_range((row, col), radar_origin, radar_radius)
            ):
                # Radar reveal: enemy ships near the viewer's radar ship
                cell["p"] = 1

            entry = team.public_board[row][col]
            if entry:
                attacker_color, is_hit = entry
                cell["s"] = "h" if is_hit else "m"
                cell["a"] = attacker_color

            grid_row.append(cell)
        grid.append(grid_row)
    return grid


def _within_radar_range(cell: tuple[int, int], origin_cells: list[tuple[int, int]], radius: int) -> bool:
    """True when the cell is within `radius` (Chebyshev) of any radar-ship cell."""
    return any(
        max(abs(cell[0] - r), abs(cell[1] - c)) <= radius
        for r, c in origin_cells
    )
