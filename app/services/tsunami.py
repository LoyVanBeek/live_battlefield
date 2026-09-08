import logging
import random
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.game.state import GameState, maybe_revive_zombie
from app.events.models import TsunamiEvent
from app.events.saver import save_event

logger = logging.getLogger(__name__)


def pick_tsunami_victims(state: GameState, count: int) -> list[dict]:
    """Randomly pick up to `count` distinct alive ships across all teams."""
    pool = []
    for color, team in state.teams.items():
        for ship in team.ships:
            if not ship.is_sunk():
                pool.append(
                    {"color": color, "ship_type": ship.ship_type, "cells": [list(c) for c in ship.cells]}
                )
    if not pool:
        return []
    return random.sample(pool, min(count, len(pool)))


def apply_tsunami_live(state: GameState, destroyed: list[dict]) -> list[str]:
    """Sink the recorded victims on the live state.

    Mirrors TsunamiEvent.apply (including zombie revivals). Returns human
    readable descriptions of what was washed away.
    """
    descriptions = []
    for entry in destroyed:
        color = entry.get("color")
        if color not in state.teams:
            continue
        team = state.teams[color]
        cells = [tuple(c) for c in entry.get("cells", [])]
        ship = next(
            (
                s
                for s in team.ships
                if s.ship_type == entry.get("ship_type") and s.cells == cells
            ),
            None,
        )
        if ship is None or ship.is_sunk():
            continue
        ship.hits = len(ship.cells)
        if maybe_revive_zombie(team, ship):
            descriptions.append(f"{color} {ship.ship_type} (🧟 it rose again!)")
        else:
            descriptions.append(f"{color} {ship.ship_type}")
    return descriptions


async def trigger_tsunami_for_game(db: AsyncSession, game, config) -> dict:
    """Trigger one tsunami for a game. Shared by the GM endpoint and the
    scheduler loop. Returns {success, message}."""
    from app.models import get_game_events

    if not config.is_enabled("tsunami"):
        return {"success": False, "message": "Tsunami is not enabled for this game!"}

    if game.status.value != "started":
        return {"success": False, "message": "Tsunamis only strike during a game!"}

    events = await get_game_events(db, game.id)
    state = GameState.from_events(events)

    count = int(config.value("tsunami", "ships_destroyed", 1))
    destroyed = pick_tsunami_victims(state, count)
    if not destroyed:
        return {"success": False, "message": "No ships to wash away!"}

    now = datetime.now(timezone.utc)
    game.last_tsunami_at = now

    event = TsunamiEvent(destroyed=destroyed, success=True)
    descriptions = apply_tsunami_live(state, destroyed)
    await save_event(db, event, game_id=game.id)

    return {
        "success": True,
        "message": "🌊 Tsunami! Washed away: " + ", ".join(descriptions),
        "destroyed": destroyed,
    }
