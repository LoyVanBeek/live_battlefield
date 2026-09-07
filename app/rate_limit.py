import time
import threading
from collections import defaultdict, deque
from typing import Deque


class RateLimiter:
    """Simple in-memory fixed-window rate limiter keyed by a string."""

    def __init__(self, max_attempts: int, window_seconds: float) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, dq: Deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()

    def check(self, key: str) -> bool:
        """Return True if the key is under the limit, without recording a hit."""
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            self._prune(dq, now)
            return len(dq) < self.max_attempts

    def record(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._hits[key].append(now)

    def allow(self, key: str) -> bool:
        if not self.check(key):
            return False
        self.record(key)
        return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


code_attempt_limiter = RateLimiter(max_attempts=10, window_seconds=60.0)
join_limiter = RateLimiter(max_attempts=10, window_seconds=60.0)
auth_fail_limiter = RateLimiter(max_attempts=10, window_seconds=60.0)
