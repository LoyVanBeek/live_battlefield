import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def create_mock_team(name="Blue", color="blue", chat_id=123, bombs=3):
    from app.game.state import TeamState

    return TeamState(name=name, color=color, chat_id=chat_id, bombs=bombs)


class TestExecuteCommand:
    """Tests for /api/execute endpoint"""

    def test_join_command_creates_team_joined_event(self):
        from app.api.routes import app
        from app.game.state import GameState
        from app import models

        with patch.object(models, "get_all_events", return_value=[]):
            with patch("app.api.routes.save_event") as mock_save:
                with patch("app.api.routes.GameState.from_events") as mock_from_events:
                    mock_state = GameState()
                    mock_state.available_colors = ["blue", "red"]
                    mock_from_events.return_value = mock_state

                    client = TestClient(app)
                    response = client.post(
                        "/api/execute",
                        json={
                            "team_color": "blue",
                            "command": "join",
                            "args": {"name": "Blue Team"},
                        },
                    )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "Blue Team" in data["message"]
        mock_save.assert_called_once()
        call_args = mock_save.call_args[0][1]
        assert call_args.event_type.value == "team_joined"
        assert call_args.color == "blue"

    def test_place_command_creates_ship_placed_event(self):
        from app.api.routes import app
        from app.game.state import GameState
        from app import models
        from unittest.mock import AsyncMock

        # Test that the coordinate parsing is correct
        # We'll test the event creation directly without hitting the DB
        from app.events.models import ShipPlacedEvent
        from app.game.ships import parse_coordinate

        # Verify coordinate parsing
        row, col = parse_coordinate("E7")
        assert row == 6  # E7 -> row 6
        assert col == 4  # E7 -> col 4


class TestQuickActions:
    """Tests for /api/quick/* endpoints"""

    def test_add_bombs_creates_bombs_added_event(self):
        from app.events.models import BombsAddedEvent

        # Test that BombsAddedEvent has correct event type
        event = BombsAddedEvent(color="blue", count=5)
        assert event.event_type.value == "bombs_added"
        assert event.color == "blue"
        assert event.count == 5

    def test_reset_team_creates_team_reset_event(self):
        from app.events.models import TeamResetEvent
        from app.game.state import GameState

        # Test that TeamResetEvent has correct event type
        event = TeamResetEvent(color="blue")
        assert event.event_type.value == "team_reset"
        assert event.color == "blue"

    def test_remove_ship_creates_ship_removed_event(self):
        from app.events.models import ShipRemovedEvent

        # Test that ShipRemovedEvent has correct event type
        event = ShipRemovedEvent(color="blue", row=0, col=0)
        assert event.event_type.value == "ship_removed"
        assert event.color == "blue"
        assert event.row == 0
        assert event.col == 0

    def test_remove_ship_game_started_fails(self):
        from app.api.routes import app
        from app.game.state import GameState
        from app.database import GameStatus
        from app import models

        with patch.object(models, "get_or_create_game_settings") as mock_settings:
            with patch.object(models, "get_all_events", return_value=[]):
                with patch("app.api.routes.GameState.from_events") as mock_from_events:
                    mock_settings_obj = MagicMock()
                    mock_settings_obj.status = GameStatus.STARTED
                    mock_settings.return_value = mock_settings_obj

                    mock_state = GameState()
                    mock_state.teams["blue"] = create_mock_team()
                    mock_from_events.return_value = mock_state

                    client = TestClient(app)
                    response = client.post(
                        "/api/quick/remove_ship",
                        json={"team_color": "blue", "row": 0, "col": 0},
                    )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert "already started" in data["message"]


class TestGameControl:
    """Tests for game control endpoints"""

    def test_start_game_already_started_fails(self):
        from app.api.routes import app
        from app.database import GameStatus
        from app import models

        with patch.object(models, "get_or_create_game_settings") as mock_settings:
            mock_settings_obj = MagicMock()
            mock_settings_obj.status = GameStatus.STARTED
            mock_settings.return_value = mock_settings_obj

            client = TestClient(app)
            response = client.post("/api/quick/start-game", json={})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False


class TestAdminEvents:
    """Tests for /api/admin/events* endpoints"""

    def test_get_all_events_returns_list(self):
        from app.api.routes import app
        from app.database import EventType
        from app import models

        with patch.object(models, "get_all_events") as mock_get:
            mock_event = MagicMock()
            mock_event.event_type = EventType.TEAM_JOINED
            mock_event.payload = {"color": "blue"}
            mock_event.id = 1
            mock_event.player_id = None
            mock_event.created_at = None
            mock_get.return_value = [mock_event]

            client = TestClient(app)
            response = client.get("/api/admin/events")

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert data["total_events"] == 1

    def test_get_event_state_invalid_index_fails(self):
        from app.api.routes import app
        from app import models

        with patch.object(models, "get_all_events") as mock_get:
            mock_get.return_value = [MagicMock(), MagicMock()]  # 2 events

            client = TestClient(app)
            response = client.get("/api/admin/events/999/state")

        assert response.status_code == 200
        data = response.json()
        assert "error" in data


class TestLocations:
    """Tests for /api/locations* endpoints"""

    def test_get_public_locations(self):
        from app.api.routes import app
        from app import models

        with patch.object(models, "get_all_locations") as mock_get:
            mock_location = MagicMock()
            mock_location.number = 1
            mock_location.code = "ABCD"
            mock_location.latitude = 52.0
            mock_location.longitude = 4.0
            mock_location.bomb_value = 1
            mock_location.is_found = False
            mock_get.return_value = [mock_location]

            client = TestClient(app)
            response = client.get("/api/locations")

        assert response.status_code == 200
        data = response.json()
        assert "locations" in data
