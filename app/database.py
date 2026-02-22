from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, JSON, Text
from datetime import datetime
import enum

from app.config import settings


engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    TEAM = "team"
    GAMEMASTER = "gamemaster"


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    color = Column(String(20), nullable=False, unique=True)
    chat_id = Column(Integer, nullable=False, unique=True)
    role = Column(Enum(Role), nullable=False, default=Role.TEAM)
    created_at = Column(DateTime, default=datetime.utcnow)


class EventType(str, enum.Enum):
    TEAM_JOINED = "team_joined"
    SHIP_PLACED = "ship_placed"
    BOMB_THROWN = "bomb_thrown"
    CODE_REDEEMED = "code_redeemed"
    LOCATION_ADDED = "location_added"


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
    created_at = Column(DateTime, default=datetime.utcnow)


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
