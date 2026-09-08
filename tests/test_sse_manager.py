import asyncio

import pytest

from app.sse_manager import SSEManager


@pytest.fixture
def manager():
    return SSEManager(max_per_game=2)


def test_connect_returns_queue_under_cap(manager):
    q1 = asyncio.run(manager.connect("g1"))
    q2 = asyncio.run(manager.connect("g1"))
    assert q1 is not None
    assert q2 is not None


def test_connect_returns_none_at_cap(manager):
    asyncio.run(manager.connect("g1"))
    asyncio.run(manager.connect("g1"))
    assert asyncio.run(manager.connect("g1")) is None


def test_disconnect_frees_a_slot(manager):
    q1 = asyncio.run(manager.connect("g1"))
    asyncio.run(manager.connect("g1"))
    asyncio.run(manager.disconnect("g1", q1))
    assert asyncio.run(manager.connect("g1")) is not None


def test_games_are_independent(manager):
    asyncio.run(manager.connect("g1"))
    asyncio.run(manager.connect("g1"))
    assert asyncio.run(manager.connect("g2")) is not None


def test_disconnect_removes_empty_game(manager):
    q1 = asyncio.run(manager.connect("g1"))
    asyncio.run(manager.disconnect("g1", q1))
    assert "g1" not in manager._game_queues


def test_broadcast_reaches_all_queues():
    manager = SSEManager(max_per_game=5)
    q1 = asyncio.run(manager.connect("g1"))
    q2 = asyncio.run(manager.connect("g1"))
    assert q1 is not None
    assert q2 is not None

    async def broadcast_and_collect():
        await manager.broadcast("g1", "payload")
        return [q1.get_nowait(), q2.get_nowait()]

    assert asyncio.run(broadcast_and_collect()) == ["payload", "payload"]
