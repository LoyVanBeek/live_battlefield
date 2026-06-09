import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.database import GameStatus
from app.models import get_game_events, get_game_locations
from app.game.state import GameState, GameStatusField
from app.events.models import GameStartedEvent
from app.events.saver import save_event

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 15


async def _check_and_start_games() -> None:
    engine = None
    try:
        engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
        sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with sm() as db:
            from sqlalchemy import select
            from app.database import Game

            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Game).where(
                    Game.scheduled_start_at <= now,
                    Game.status == GameStatus.WAITING,
                )
            )
            games = list(result.scalars().all())

            for game in games:
                try:
                    events = await get_game_events(db, game.id)
                    state = GameState.from_events(events)
                    locations = await get_game_locations(db, game.id)

                    if state.status == GameStatusField.STARTED:
                        continue
                    if state.status == GameStatusField.ENDED:
                        continue
                    if len(state.teams) < 2:
                        logger.warning("Scheduled start failed for game %s: need ≥2 teams", game.id)
                        continue
                    teams_without_ships = [t.name for t in state.teams.values() if not t.has_all_ships()]
                    if teams_without_ships:
                        logger.warning("Scheduled start failed for game %s: ships not placed", game.id)
                        continue
                    has_bomb_source = len(locations) > 0 or game.quiz_enabled or game.trickle_enabled
                    if not has_bomb_source:
                        logger.warning("Scheduled start failed for game %s: no bomb source", game.id)
                        continue

                    event = GameStartedEvent()
                    new_state, updated_event = event.apply(state)
                    await save_event(db, updated_event, game.id)

                    game.status = GameStatus.STARTED
                    game.started_at = datetime.now(timezone.utc)
                    await db.commit()

                    logger.info("Scheduled game started: id=%s", game.id)
                except Exception as e:
                    logger.exception("Error starting scheduled game %s: %s", game.id, e)
    except Exception:
        logger.exception("Game scheduler error")
    finally:
        if engine is not None:
            await engine.dispose()


async def scheduler_loop(stop_event: asyncio.Event) -> None:
    logger.info("Game scheduler started")
    while not stop_event.is_set():
        await _check_and_start_games()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CHECK_INTERVAL)
        except asyncio.TimeoutError:
            pass
    logger.info("Game scheduler stopped")
