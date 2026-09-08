import asyncio
from typing import Optional


class SSEManager:
    def __init__(self, max_per_game: int = 30) -> None:
        self.max_per_game = max_per_game
        self._game_queues: dict[str, set[asyncio.Queue[str]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, game_id: str) -> Optional[asyncio.Queue[str]]:
        """Register a queue for the game, or return None if the game is at capacity."""
        q: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            queues = self._game_queues.setdefault(game_id, set())
            if len(queues) >= self.max_per_game:
                return None
            queues.add(q)
        return q

    async def disconnect(self, game_id: str, q: asyncio.Queue[str]) -> None:
        async with self._lock:
            queues = self._game_queues.get(game_id)
            if queues:
                queues.discard(q)
                if not queues:
                    del self._game_queues[game_id]

    async def broadcast(self, game_id: str, data: str) -> None:
        async with self._lock:
            queues = list(self._game_queues.get(game_id, set()))
        for q in queues:
            await q.put(data)


manager = SSEManager(max_per_game=30)
