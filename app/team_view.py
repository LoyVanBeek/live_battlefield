import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import lookup_team_token, get_game_events
from app.game.state import GameState
from app.game.ships import BOARD_SIZE, SHIP_COUNTS


async def get_team_view(team_token: str, db: AsyncSession) -> dict:
    result = await lookup_team_token(db, team_token)
    if result is None:
        return {"error": True}

    game_id_str, color = result
    events = await get_game_events(db, uuid.UUID(game_id_str))
    state = GameState.from_events(events)

    result = {
        "s": state.status.value,
        "ec": len(events),
        "t": _serialize_team(state.teams[color], private=True, status=state.status.value),
        "ts": [_serialize_team(t, private=False, status=state.status.value) for t in state.teams.values()],
    }
    winner = state.get_winner()
    if winner and state.status.value == "ended":
        result["w"] = winner.name
    return result


def _serialize_team(team, private: bool, status: str = "preparing") -> dict:
    result: dict = {
        "n": team.name,
        "c": team.color,
        "b": team.bombs,
        "sp": sum(team.placed_ship_types.values()) if status == "preparing" else sum(SHIP_COUNTS.values()) - len(team.get_sunk_ships()),
        "sk": len(team.get_sunk_ships()),
    }
    result["g"] = _serialize_grid(team, include_ships=private)
    return result


def _serialize_grid(team, include_ships: bool) -> list[list[dict]]:
    grid: list[list[dict]] = []
    for row in range(BOARD_SIZE):
        grid_row: list[dict] = []
        for col in range(BOARD_SIZE):
            cell: dict = {}

            if include_ships and team.private_board[row][col]:
                cell["p"] = 1
                ship = team.get_ship_at(row, col)
                if ship and ship.is_sunk():
                    cell["k"] = 1

            entry = team.public_board[row][col]
            if entry:
                attacker_color, is_hit = entry
                cell["s"] = "h" if is_hit else "m"
                cell["a"] = attacker_color

            grid_row.append(cell)
        grid.append(grid_row)
    return grid
