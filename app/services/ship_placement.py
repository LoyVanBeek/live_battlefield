import random
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import get_game_events
from app.game.state import GameState, GameStatusField, _copy_team
from app.game.ships import SHIP_COUNTS
from app.events import ShipPlacedEvent, save_event


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

    placements = []
    team_copy = _copy_team(team)

    for ship_type in ships_to_place:
        found = False
        for _ in range(5000):
            row = random.randint(0, 9)
            col = random.randint(0, 9)
            direction = random.choice(["horizontal", "vertical"])

            success, updated_team = team_copy.place_ship(ship_type, row, col, direction)
            if success:
                placements.append((ship_type, row, col, direction))
                team_copy = updated_team
                found = True
                break

        if not found:
            return False, f"Could not find placement for {ship_type}"

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
