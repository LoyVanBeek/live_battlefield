"""Initialize the test database for e2e tests.

Creates all ORM tables, creates the admin token, and stamps
the alembic revision to avoid migration errors on app startup.
"""
import asyncio
import subprocess
import os

from app.database import create_async_engine, Base, async_session_maker
from app.config import settings
from app.models import get_or_create_admin


async def init():
    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    async with async_session_maker() as db:
        await get_or_create_admin(db)
        await db.commit()

    subprocess.run(
        ["alembic", "-c", "migrations.ini", "stamp", "head"],
        cwd="/app",
        env={**os.environ, "PYTHONPATH": "/app"},
        check=True,
    )


asyncio.run(init())
