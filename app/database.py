from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float, DateTime, Enum, JSON
from collections.abc import AsyncIterator
from datetime import datetime, timezone
import enum

from app.config import settings


_engine: AsyncEngine | None = None
_async_session_maker = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, echo=False)
    return _engine


def get_async_session_maker():
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_maker


engine = get_engine()
async_session_maker = get_async_session_maker()


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    TEAM = "team"
    GAMEMASTER = "gamemaster"
    AI = "ai"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    chat_id: Mapped[int | None] = mapped_column(nullable=True)  # Nullable for AI players
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.TEAM)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EventType(str, enum.Enum):
    TEAM_JOINED = "team_joined"
    SHIP_PLACED = "ship_placed"
    SHIP_REMOVED = "ship_removed"
    BOMB_THROWN = "bomb_thrown"
    CODE_REDEEMED = "code_redeemed"
    LOCATION_ADDED = "location_added"
    LOCATION_REMOVED = "location_removed"
    GAME_STARTED = "game_started"
    GAME_ENDED = "game_ended"
    BOMBS_ADDED = "bombs_added"
    TEAM_RESET = "team_reset"


class GameEvent(Base):
    __tablename__ = "game_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    player_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    bomb_value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GameStatus(str, enum.Enum):
    WAITING = "waiting"
    STARTED = "started"
    ENDED = "ended"


class GameSettings(Base):
    __tablename__ = "game_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[GameStatus] = mapped_column(Enum(GameStatus), nullable=False, default=GameStatus.WAITING)
    total_locations_needed: Mapped[int] = mapped_column(Integer, nullable=False, default=33)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    admin_token: Mapped[str] = mapped_column(String(20), default="")


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
