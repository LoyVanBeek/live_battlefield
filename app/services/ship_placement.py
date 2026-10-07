import copy
import random
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import get_game_events
from app.game.state import GameState, GameStatusField, TeamState
from app.game.ships import SHIP_COUNTS
from app.events import ShipPlacedEvent, save_event

Placement = tuple[str, int, int, str]  # ship_type, row, col, direction

# Greedy placement paints itself into a corner: under the no-touching rule an
# early ship can leave the board with no legal cell for a later one (measured
# 3.5% of draws dying with the patrol boat still to place). A dead-end draw is
# normal, so redraw the whole board instead of failing the call.
MAX_BOARD_DRAWS = 20
ATTEMPTS_PER_SHIP = 5000


def _draw_placements(team: TeamState, ships_to_place: list[str]) -> list[Placement] | None:
    """One greedy placement attempt on a private copy of the team's board.

    Returns every placement, or None when this draw dead-ends — the caller
    redraws rather than failing.
    """
    board = copy.deepcopy(team)
    placements: list[Placement] = []

    for ship_type in ships_to_place:
        for _ in range(ATTEMPTS_PER_SHIP):
            row = random.randint(0, 9)
            col = random.randint(0, 9)
            direction = random.choice(["horizontal", "vertical"])

            placed, board = board.place_ship(ship_type, row, col, direction)
            if placed:
                placements.append((ship_type, row, col, direction))
                break
        else:
            return None

    return placements


def find_placements(team: TeamState, ships_to_place: list[str]) -> list[Placement] | None:
    """Place every ship, redrawing the board each time a draw dead-ends."""
    for _ in range(MAX_BOARD_DRAWS):
        placements = _draw_placements(team, ships_to_place)
        if placements is not None:
            return placements
    return None


async def place_all_ships_game_scoped(db: AsyncSession, game_id: str, team_color: str) -> tuple[bool, str]:
    """
    Place all ships for a team (game-scoped).

    Returns:
        tuple: (success: bool, message: str)
    """
    game_uuid = uuid.UUID(game_id)
    events = await get_game_events(db, game_uuid)
    state = GameState.from_events(events)

    if state.status == GameStatusField.ENDED:
        return False, "Cannot place ships - game has ended!"

    if team_color not in state.teams:
        return False, f"Team {team_color} doesn't exist!"

    team = state.teams[team_color]

    ships_to_place = []
    for ship_type, count in SHIP_COUNTS.items():
        already_placed = team.placed_ship_types.get(ship_type, 0)
        for i in range(count - already_placed):
            ships_to_place.append(ship_type)

    if not ships_to_place:
        return True, "All ships already placed!"

    placements = find_placements(team, ships_to_place)
    if placements is None:
        return False, "Could not find a valid ship layout - try again"

    for ship_type, row, col, direction in placements:
        event = ShipPlacedEvent(
            color=team_color,
            ship_type=ship_type,
            row=row,
            col=col,
            direction=direction,
        )
        await save_event(db, event, game_uuid)

    return True, f"Placed all {len(placements)} ships successfully!"
