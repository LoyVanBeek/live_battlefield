import time
from unittest.mock import patch

from app.rate_limit import RateLimiter


class TestRateLimiterKeyStorage:
    """Key storage stays bounded under floods of unique keys."""

    def test_record_bounds_key_count(self):
        rl = RateLimiter(max_attempts=5, window_seconds=60.0, max_keys=3)
        for i in range(10):
            rl.record(f"key-{i}")

        assert len(rl._hits) == 3
        assert "key-0" not in rl._hits
        assert "key-9" in rl._hits

    def test_check_does_not_allocate_keys(self):
        rl = RateLimiter(max_attempts=5, window_seconds=60.0)
        assert rl.check("never-seen") is True
        assert "never-seen" not in rl._hits

    def test_window_still_enforces_limit(self):
        rl = RateLimiter(max_attempts=2, window_seconds=60.0)
        rl.record("k")
        rl.record("k")
        assert rl.check("k") is False

        with patch("app.rate_limit.time.monotonic", return_value=time.monotonic() + 120):
            assert rl.check("k") is True

    def test_evicted_key_gets_fresh_budget(self):
        rl = RateLimiter(max_attempts=1, window_seconds=60.0, max_keys=1)
        rl.record("a")
        assert rl.check("a") is False

        rl.record("b")  # evicts "a"
        assert "a" not in rl._hits
        assert rl.check("a") is True

    def test_reset_clears_storage(self):
        rl = RateLimiter(max_attempts=5, window_seconds=60.0)
        rl.record("k")
        rl.reset()
        assert rl._hits == {}
