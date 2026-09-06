import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.config import settings
from app.database import Game, GameStatus
from app.models import get_game_events, get_game_locations
from app.game.state import GameState, GameStatusField
from app.events.models import GameStartedEvent
from app.events.saver import save_event

logger = logging.getLogger(__name__)

_pending_schedules: dict[str, asyncio.Task] = {}


async def _start_game_if_ready(game_id: str) -> None:
    engine = None
    try:
        engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
        sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with sm() as db:
            from sqlalchemy import select

            result = await db.execute(select(Game).where(Game.id == UUID(game_id)))
            game = result.scalar_one_or_none()
            if not game:
                return
            if game.status != GameStatus.WAITING:
                return
            if not game.scheduled_start_at:
                return

            events = await get_game_events(db, game.id)
            state = GameState.from_events(events)
            locations = await get_game_locations(db, game.id)

            if state.status in (GameStatusField.STARTED, GameStatusField.ENDED):
                return
            if len(state.teams) < 2:
                logger.warning("Scheduled start failed for game %s: need >=2 teams", game.id)
                game.scheduled_start_at = None
                await db.commit()
                return
            teams_without_ships = [t.name for t in state.teams.values() if not t.has_all_ships()]
            if teams_without_ships:
                logger.warning("Scheduled start failed for game %s: ships not placed", game.id)
                game.scheduled_start_at = None
                await db.commit()
                return
            has_bomb_source = len(locations) > 0 or game.quiz_enabled or game.trickle_enabled
            if not has_bomb_source:
                logger.warning("Scheduled start failed for game %s: no bomb source", game.id)
                game.scheduled_start_at = None
                await db.commit()
                return

            event = GameStartedEvent()
            new_state, updated_event = event.apply(state)
            await save_event(db, updated_event, game.id)

            game.status = GameStatus.STARTED
            game.started_at = datetime.now(timezone.utc)
            game.scheduled_start_at = None
            await db.commit()
            logger.info("Scheduled game started: id=%s", game.id)
    except Exception:
        logger.exception("Error starting scheduled game %s", game_id)
    finally:
        if engine is not None:
            await engine.dispose()


async def _sleep_then_start(game_id: str, delay: float) -> None:
    try:
        await asyncio.sleep(delay)
        await _start_game_if_ready(game_id)
    except asyncio.CancelledError:
        logger.debug("Scheduled start cancelled for game %s", game_id)
    except Exception:
        logger.exception("Unexpected error in scheduled start for game %s", game_id)
    finally:
        _pending_schedules.pop(game_id, None)


def schedule_game_start(game_id: str, dt: datetime) -> None:
    cancel_scheduled_start(game_id)
    now = datetime.now(timezone.utc)
    delay = (dt - now).total_seconds()
    if delay <= 0:
        task = asyncio.create_task(_start_game_if_ready(game_id))
    else:
        task = asyncio.create_task(_sleep_then_start(game_id, delay))
    _pending_schedules[game_id] = task


def cancel_scheduled_start(game_id: str) -> None:
    task = _pending_schedules.pop(game_id, None)
    if task is not None and not task.done():
        task.cancel()


async def resume_scheduled_starts() -> None:
    engine = None
    try:
        engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
        sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with sm() as db:
            from sqlalchemy import select

            result = await db.execute(
                select(Game).where(
                    Game.scheduled_start_at.isnot(None),
                    Game.status == GameStatus.WAITING,
                )
            )
            games = list(result.scalars().all())

        for game in games:
            if game.scheduled_start_at is None:
                continue
            schedule_game_start(str(game.id), game.scheduled_start_at)
            logger.info("Resumed schedule for game %s: due at %s", game.id, game.scheduled_start_at)
    except Exception:
        logger.exception("Error resuming scheduled starts")
    finally:
        if engine is not None:
            await engine.dispose()


async def shutdown_schedules() -> None:
    tasks = list(_pending_schedules.values())
    _pending_schedules.clear()
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
