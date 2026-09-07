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

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            cutoff = now - self.window_seconds
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self.max_attempts:
                return False
            dq.append(now)
            return True


code_attempt_limiter = RateLimiter(max_attempts=10, window_seconds=60.0)
join_limiter = RateLimiter(max_attempts=10, window_seconds=60.0)
