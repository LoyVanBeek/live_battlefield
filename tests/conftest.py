import os
from unittest.mock import patch

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("NGROK_AUTHTOKEN", "test_ngrok_token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

patch("sqlalchemy.ext.asyncio.create_async_engine").start()
