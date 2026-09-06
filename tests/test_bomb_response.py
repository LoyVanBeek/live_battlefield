import uuid
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.api.routes import app, verify_team_or_gm
from app.events.models import (
    TeamJoinedEvent,
    ShipPlacedEvent,
    GameStartedEvent,
)
from app.game.state import GameState


def _build_started_state():
    """Real event sequence: two teams, each with a 2-cell patrol boat, game started."""
    state = GameState()
    state, _ = TeamJoinedEvent(name="Red Team", color="red", chat_id=1, bombs=5).apply(state)
    state, _ = TeamJoinedEvent(name="Blue Team", color="blue", chat_id=2, bombs=3).apply(state)
    state, _ = ShipPlacedEvent(
        color="blue", ship_type="patrol_boat", row=0, col=0, direction="horizontal"
    ).apply(state)
    state, _ = ShipPlacedEvent(
        color="red", ship_type="patrol_boat", row=9, col=0, direction="horizontal"
    ).apply(state)
    state, _ = GameStartedEvent().apply(state)
    return state


def _post_bomb(state: GameState, coord: str = "A1"):
    game_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    app.dependency_overrides[verify_team_or_gm] = lambda: {
        "role": "team", "game_id": str(game_id), "color": "red"
    }
    try:
        with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
            with patch("app.models.get_game", new_callable=AsyncMock, return_value=None):
                with patch("app.api.routes.GameState.from_events", return_value=state):
                    with patch("app.api.routes.save_event", new_callable=AsyncMock):
                        with patch(
                            "app.api.routes._check_game_paused",
                            new_callable=AsyncMock,
                            return_value=None,
                        ):
                            with patch(
                                "app.models.get_player_by_color_in_game",
                                new_callable=AsyncMock,
                                return_value=None,
                            ):
                                client = TestClient(app)
                                return client.post(
                                "/api/execute",
                                json={
                                    "team_color": "red",
                                    "command": "bomb",
                                    "args": {"target": "blue", "coordinate": coord},
                                },
                            )
    finally:
        app.dependency_overrides.clear()


class TestBombResponse:
    def test_bomb_hit_fields(self):
        resp = _post_bomb(_build_started_state())
        data = resp.json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert data["hit"] is True
        assert data["sunk"] is False
        assert data["ship_type"] == "patrol_boat"
        assert data["target_name"] == "Blue Team"
        assert data["coord"] == "A1"
        assert data["bombs_left"] == 4

    def test_bomb_miss_fields(self):
        resp = _post_bomb(_build_started_state(), coord="C5")
        data = resp.json()
        assert data["success"] is True
        assert data["hit"] is False
        assert data["sunk"] is False
        assert data["coord"] == "C5"
        assert data["bombs_left"] == 4

    def test_bomb_already_bombed_error_key(self):
        state = _build_started_state()
        resp = _post_bomb(state, coord="A1")
        assert resp.json()["success"] is True

        resp = _post_bomb(state, coord="A1")
        data = resp.json()
        assert data["success"] is False
        assert data["error_key"] == "already_bombed"
        assert data["coord"] == "A1"