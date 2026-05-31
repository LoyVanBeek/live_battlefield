import asyncio
import logging
from datetime import datetime, timezone

from app.database import async_session_maker
from app.models import get_active_trickle_games, get_game_events
from app.game.state import GameState
from app.events.models import BombsAddedEvent
from app.events.saver import save_event

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 30


async def _deliver_trickle() -> None:
    try:
        async with async_session_maker() as db:
            games = await get_active_trickle_games(db)
            for game in games:
                now = datetime.now(timezone.utc)
                elapsed_minutes = 0
                if game.last_trickle_at:
                    elapsed_minutes = (now - game.last_trickle_at).total_seconds() / 60

                if game.last_trickle_at is None or elapsed_minutes >= game.trickle_interval_minutes:
                    events = await get_game_events(db, game.id)
                    state = GameState.from_events(events)

                    game.last_trickle_at = now
                    await db.commit()

                    for color in state.teams:
                        event = BombsAddedEvent(
                            color=color,
                            count=game.trickle_bombs_per_interval,
                        )
                        _, updated_event = event.apply(state)
                        await save_event(db, updated_event, game.id)

                    logger.info(
                        "Trickle delivered to game=%s: %d bombs each to %d teams",
                        game.id,
                        game.trickle_bombs_per_interval,
                        len(state.teams),
                    )
    except Exception:
        logger.exception("Trickle scheduler error")


async def trickle_loop(stop_event: asyncio.Event) -> None:
    logger.info("Trickle scheduler started")
    while not stop_event.is_set():
        await _deliver_trickle()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL)
        except asyncio.TimeoutError:
            pass
    logger.info("Trickle scheduler stopped")
