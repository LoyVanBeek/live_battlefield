from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON, Text
from datetime import datetime
import enum

from app.config import settings


_engine: AsyncEngine = None
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

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20), nullable=False, unique=True)
    chat_id = Column(Integer, nullable=True)  # Nullable for AI players
    role = Column(Enum(Role), nullable=False, default=Role.TEAM)
    created_at = Column(DateTime, default=datetime.utcnow)


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

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(Enum(EventType), nullable=False)
    payload = Column(JSON, nullable=False)
    player_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, nullable=False, unique=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    code = Column(String(20), nullable=False)
    bomb_value = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class GameStatus(str, enum.Enum):
    WAITING = "waiting"
    STARTED = "started"
    ENDED = "ended"


class GameSettings(Base):
    __tablename__ = "game_settings"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(GameStatus), nullable=False, default=GameStatus.WAITING)
    total_locations_needed = Column(Integer, nullable=False, default=33)
    started_at = Column(DateTime, nullable=True)


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
