import os
from unittest.mock import patch

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("NGROK_AUTHTOKEN", "test_ngrok_token")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

patch("sqlalchemy.ext.asyncio.create_async_engine").start()


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    from app.rate_limit import auth_fail_limiter, code_attempt_limiter, join_limiter

    auth_fail_limiter.reset()
    code_attempt_limiter.reset()
    join_limiter.reset()
    yield
    auth_fail_limiter.reset()
    code_attempt_limiter.reset()
    join_limiter.reset()
