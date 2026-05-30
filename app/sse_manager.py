import asyncio


class SSEManager:
    def __init__(self) -> None:
        self._game_queues: dict[str, set[asyncio.Queue[str]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, game_id: str) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            if game_id not in self._game_queues:
                self._game_queues[game_id] = set()
            self._game_queues[game_id].add(q)
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


manager = SSEManager()
