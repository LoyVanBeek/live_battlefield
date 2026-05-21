import asyncio


class SSEManager:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

    async def connect(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue()
        async with self._lock:
            self._queues.add(q)
        return q

    async def disconnect(self, q: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._queues.discard(q)

    async def broadcast(self, data: str) -> None:
        async with self._lock:
            queues = list(self._queues)
        for q in queues:
            await q.put(data)


manager = SSEManager()
