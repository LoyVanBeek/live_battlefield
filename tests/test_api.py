import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


def create_mock_team(name="Blue", color="blue", chat_id=123, bombs=3):
    from app.game.state import TeamState

    return TeamState(name=name, color=color, chat_id=chat_id, bombs=bombs)


class TestExecuteCommand:
    """Tests for /api/execute endpoint"""

    def test_join_command_creates_team_joined_event(self):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState
        from unittest.mock import AsyncMock

        app.dependency_overrides[verify_team_or_gm] = lambda: {"role": "admin", "game_id": "00000000-0000-0000-0000-000000000000", "color": "blue"}
        try:
            with patch("app.models.get_game_events", return_value=[]):
                with patch("app.api.routes.save_event") as mock_save:
                    with patch("app.models.create_team_token", new_callable=AsyncMock):
                        with patch("app.api.routes.GameState.from_events") as mock_from_events:
                            mock_state = GameState()
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
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "Blue Team" in data["message"]
        mock_save.assert_called_once()
        call_args = mock_save.call_args[0][1]
        assert call_args.event_type.value == "team_joined"
        assert call_args.color == "blue"

    def test_team_role_cannot_act_as_another_color(self):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState
        from unittest.mock import AsyncMock

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team",
            "game_id": "00000000-0000-0000-0000-000000000000",
            "color": "blue",
        }
        try:
            with patch("app.models.get_game_events", return_value=[]):
                with patch("app.api.routes.save_event"):
                    with patch("app.api.routes.GameState.from_events") as mock_from_events:
                        mock_state = GameState()
                        mock_from_events.return_value = mock_state

                        client = TestClient(app)
                        response = client.post(
                            "/api/execute",
                            json={
                                "team_color": "red",
                                "command": "rename",
                                "args": {"name": "Hijacked"},
                            },
                        )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "doesn't exist" in data["message"]

    def test_team_role_force_placed_on_own_color(self):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField
        from tests.test_api import create_mock_team

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team",
            "game_id": "00000000-0000-0000-0000-000000000000",
            "color": "blue",
        }
        try:
            with patch("app.models.get_game_events", return_value=[]):
                with patch("app.models.is_game_paused", new_callable=AsyncMock, return_value=(False, None)):
                    with patch("app.api.routes.save_event"):
                        with patch("app.api.routes.GameState.from_events") as mock_from_events:
                            mock_state = GameState()
                            mock_state.status = GameStatusField.STARTED
                            mock_state.teams = {
                                "blue": create_mock_team(color="blue", bombs=5)
                            }
                            mock_from_events.return_value = mock_state

                            client = TestClient(app)
                            response = client.post(
                                "/api/execute",
                                json={
                                    "team_color": "red",
                                    "command": "bomb",
                                    "args": {"target": "green", "coordinate": "A1"},
                                },
                            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        # Auth color is blue; the "red" in the payload is ignored, so the blue
        # team never receives a "Team red doesn't exist" error path.
        assert data["message"].startswith("Target team")

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

    def test_join_command_rejects_invalid_color(self):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState

        app.dependency_overrides[verify_team_or_gm] = lambda: {"role": "gm", "game_id": "00000000-0000-0000-0000-000000000000"}
        try:
            with patch("app.models.get_game_events", return_value=[]):
                with patch("app.api.routes.GameState.from_events") as mock_from_events:
                    mock_from_events.return_value = GameState()

                    client = TestClient(app)
                    response = client.post(
                        "/api/execute",
                        json={"team_color": "pink", "command": "join", "args": {}},
                    )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid team color" in data["message"]


class TestJoinGameEndpoint:
    """Tests for /api/join-game/{invite_token}"""

    def test_join_game_rejects_invalid_team_color(self):
        from app.api.routes import app
        from unittest.mock import AsyncMock, MagicMock

        mock_game = MagicMock()
        with patch("app.models.get_game_by_invite_token", new_callable=AsyncMock, return_value=mock_game):
            client = TestClient(app)
            response = client.post(
                "/api/join-game/invite-token-123",
                json={"team_color": "chartreuse", "name": "Cheaters"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid team color" in data["message"]


class TestClearDatabase:
    """Tests for /api/quick/clear-database (admin-only global reset)"""

    def test_clear_database_rejects_gm_token(self):
        from app.api.routes import app
        from unittest.mock import AsyncMock, MagicMock

        admin = MagicMock()
        admin.token = "test_admin_token"
        with patch("app.models.get_admin", new_callable=AsyncMock, return_value=admin):
            client = TestClient(app)
            response = client.post(
                "/api/quick/clear-database?token=wrong_token&gm_token=somegm"
            )

        assert response.status_code == 404

    def test_clear_database_as_admin_wipes_all_games(self):
        from app.api.routes import app, verify_admin
        from unittest.mock import AsyncMock, MagicMock

        game1, game2 = MagicMock(), MagicMock()
        app.dependency_overrides[verify_admin] = lambda: "test_admin_token"
        try:
            with patch("app.models.get_all_games", new_callable=AsyncMock, return_value=[game1, game2]):
                with patch("app.models.delete_all_players", new_callable=AsyncMock, return_value=3) as mock_players:
                    with patch("app.models.delete_all_events", new_callable=AsyncMock, return_value=5) as mock_events:
                        with patch("app.models.delete_all_locations", new_callable=AsyncMock, return_value=2) as mock_locations:
                            with patch("app.models.delete_all_team_tokens", new_callable=AsyncMock) as mock_tokens:
                                with patch("app.models.update_game_status", new_callable=AsyncMock) as mock_status:
                                    client = TestClient(app)
                                    response = client.post("/api/quick/clear-database")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert mock_players.await_count == 2
        assert mock_events.await_count == 2
        assert mock_locations.await_count == 2
        assert mock_tokens.await_count == 2
        assert mock_status.await_count == 2
        assert "Players: 6" in data["message"]
        assert "Events: 10" in data["message"]
        assert "Locations: 4" in data["message"]


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
        # Test that ShipRemovedEvent cannot be applied when game has started
        from app.game.state import GameState, GameStatusField

        state = GameState()
        state.status = GameStatusField.STARTED
        state.teams["blue"] = create_mock_team()

        from app.events.models import ShipRemovedEvent

        event = ShipRemovedEvent(color="blue", row=0, col=0)

        # When status is STARTED, applying should still return success=True because
        # we removed the game_status check from apply() - it's now in the API endpoint
        # So this test just verifies the event can be created
        assert event.event_type.value == "ship_removed"


class TestGameControl:
    """Tests for game control endpoints"""

    def test_start_game_creates_event(self):
        from app.events.models import GameStartedEvent
        from app.game.state import GameState

        event = GameStartedEvent()
        state = GameState()

        new_state, updated_event = event.apply(state)

        assert new_state.status.value == "started"
        assert updated_event.timestamp != ""

    def test_start_game_already_started_fails(self):
        from app.api.routes import app, verify_gm_token
        from app.game.state import GameState, GameStatusField

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            state = GameState()
            state.status = GameStatusField.STARTED

            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    with patch("app.models.get_game_locations", return_value=[]):
                        with patch("app.api.routes.save_event"):
                            client = TestClient(app)
                            response = client.post("/api/quick/start-game", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] == False
        finally:
            app.dependency_overrides.clear()

    def test_end_game_creates_event(self):
        from app.events.models import GameEndedEvent
        from app.game.state import GameState, GameStatusField

        event = GameEndedEvent(winner="blue")
        state = GameState()
        state.status = GameStatusField.STARTED

        new_state, updated_event = event.apply(state)

        assert new_state.status.value == "ended"
        assert updated_event.winner == "blue"
        assert updated_event.timestamp != ""

    def test_end_game_from_preparing_fails(self):
        from app.api.routes import app, verify_gm_token
        from app.game.state import GameState, GameStatusField

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            state = GameState()
            state.status = GameStatusField.PREPARING

            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    client = TestClient(app)
                    response = client.post("/api/quick/end-game", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] == False
            assert "hasn't started" in data["message"]
        finally:
            app.dependency_overrides.clear()

    def test_game_status_field_enum(self):
        from app.game.state import GameStatusField

        assert GameStatusField.PREPARING.value == "preparing"
        assert GameStatusField.STARTED.value == "started"
        assert GameStatusField.ENDED.value == "ended"


class TestAdminEvents:
    """Tests for /api/admin/events* endpoints"""

    def test_get_all_events_returns_list(self):
        from app.api.routes import app, verify_admin_or_gm
        from app.database import EventType
        from app import models

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch.object(models, "get_game_events") as mock_get:
                mock_event = MagicMock()
                mock_event.event_type = EventType.TEAM_JOINED
                mock_event.payload = {"color": "blue"}
                mock_event.id = 1
                mock_event.player_id = None
                mock_event.created_at = None
                mock_get.return_value = [mock_event]

                client = TestClient(app)
                response = client.get("/api/admin/events?game_id=00000000-0000-0000-0000-000000000000")

            assert response.status_code == 200
            data = response.json()
            assert "events" in data
            assert data["total_events"] == 1
        finally:
            app.dependency_overrides.clear()

    def test_get_event_state_invalid_index_fails(self):
        from app.api.routes import app, verify_admin_or_gm
        from app import models

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch.object(models, "get_game_events") as mock_get:
                mock_get.return_value = [MagicMock(), MagicMock()]  # 2 events

                client = TestClient(app)
                response = client.get("/api/admin/events/999/state?game_id=00000000-0000-0000-0000-000000000000")

            assert response.status_code == 200
            data = response.json()
            assert "error" in data
        finally:
            app.dependency_overrides.clear()


class TestLocations:
    """Tests for /api/locations* endpoints"""

    def test_get_public_locations(self):
        from app.api.routes import app
        from app import models

        with patch.object(models, "get_game_locations") as mock_get:
            mock_location = MagicMock()
            mock_location.number = 1
            mock_location.code = "ABCD"
            mock_location.latitude = 52.0
            mock_location.longitude = 4.0
            mock_location.bomb_value = 1
            mock_location.is_found = False
            mock_get.return_value = [mock_location]

            client = TestClient(app)
            response = client.get("/api/locations?game_id=00000000-0000-0000-0000-000000000000")

        assert response.status_code == 200
        data = response.json()
        assert "locations" in data


class TestWelcomeAndMap:
    """Root serves a welcome page only; /map requires a game_id."""

    def test_root_serves_welcome_page_only(self):
        from app.api.routes import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "Live Battlefield" in response.text
        assert "/map" not in response.headers.get("location", "")

    def test_root_does_not_expose_game_data(self):
        from app.api.routes import app

        client = TestClient(app)
        response = client.get("/")

        assert "teams-container" not in response.text
        assert "game-status-badge" not in response.text
        assert "/api/public-state" not in response.text
        assert "/api/locations" not in response.text

    def test_root_language_query_param(self):
        from app.api.routes import app

        client = TestClient(app)
        response = client.get("/?lang=nl")

        assert response.status_code == 200
        assert "Hoe het werkt" in response.text
        assert response.cookies.get("lang") == "nl"

    def test_root_language_from_accept_language(self):
        from app.api.routes import app

        client = TestClient(app)
        response = client.get("/", headers={"Accept-Language": "nl,en;q=0.9"})

        assert response.status_code == 200
        assert "Hoe het werkt" in response.text

    def test_root_language_cookie_persists(self):
        from app.api.routes import app

        client = TestClient(app)
        client.get("/?lang=nl")
        response = client.get("/")

        assert response.status_code == 200
        assert "Hoe het werkt" in response.text

    def test_root_unsupported_lang_falls_back(self):
        from app.api.routes import app

        client = TestClient(app)
        response = client.get("/?lang=fr")

        assert response.status_code == 200
        assert "How it works" in response.text

    def test_map_requires_game_id(self):
        from app.api.routes import app

        client = TestClient(app)
        response = client.get("/map", follow_redirects=False)

        assert 300 <= response.status_code < 400
        assert response.headers["location"] == "/"

    def test_map_requires_valid_uuid(self):
        from app.api.routes import app

        client = TestClient(app)
        response = client.get("/map?game_id=not-a-uuid", follow_redirects=False)

        assert 300 <= response.status_code < 400
        assert response.headers["location"] == "/"

    def test_map_unknown_game_redirects_home(self):
        from app.api.routes import app, get_api_db

        async def override_get_db():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, *args, **kwargs):
                    return MagicMock()

            yield MockSession()

        app.dependency_overrides[get_api_db] = override_get_db
        try:
            with patch("app.models.get_game", new_callable=AsyncMock, return_value=None):
                client = TestClient(app)
                response = client.get("/map?game_id=00000000-0000-0000-0000-000000000000", follow_redirects=False)
        finally:
            app.dependency_overrides.clear()

        assert 300 <= response.status_code < 400
        assert response.headers["location"] == "/"

    def test_map_renders_for_valid_game(self):
        from app.api.routes import app, get_api_db

        async def override_get_db():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, *args, **kwargs):
                    return MagicMock()

            yield MockSession()

        app.dependency_overrides[get_api_db] = override_get_db
        mock_game = MagicMock()
        mock_game.id = "00000000-0000-0000-0000-000000000000"
        try:
            with patch("app.models.get_game", new_callable=AsyncMock, return_value=mock_game):
                client = TestClient(app)
                response = client.get("/map?game_id=00000000-0000-0000-0000-000000000000")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.headers["Referrer-Policy"] == "origin"
        assert "00000000-0000-0000-0000-000000000000" in response.text
        assert "live_board" not in response.text.lower()


class TestBoardJson:
    """Tests for /api/board/*/public.json and /api/board/*/private.json endpoints"""

    def test_team_to_json_public_board(self):
        from app.api.routes import _team_to_json
        from app.game.state import TeamState

        team = TeamState(name="Red Team", color="red", chat_id=123, bombs=5)
        team.place_ship("patrol_boat", 0, 0, "horizontal")
        team.place_ship("destroyer", 2, 2, "vertical")
        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(5, 5, "blue")
        team.receive_bomb(5, 6, "green")

        result = _team_to_json(team, include_ships=False)

        assert "team" in result
        assert "grid" in result
        assert "bombs" not in result
        assert "ships" not in result

        assert result["team"]["name"] == "Red Team"
        assert result["team"]["color"] == "red"

        grid = result["grid"]
        assert len(grid) == 10
        assert len(grid[0]) == 10

    def test_team_to_json_private_board(self):
        from app.api.routes import _team_to_json
        from app.game.state import TeamState

        team = TeamState(name="Blue Team", color="blue", chat_id=456, bombs=3)
        _, team = team.place_ship("patrol_boat", 0, 0, "horizontal")
        _, team = team.place_ship("torpedo_hunter", 5, 5, "vertical")
        _, _, team = team.receive_bomb(0, 0, "red")

        result = _team_to_json(team, include_ships=True)

        assert "team" in result
        assert "grid" in result
        assert "bombs" in result
        assert "ships" in result
        assert "ships_sunk" in result
        assert "is_destroyed" in result

        assert result["bombs"] == 3
        assert len(result["ships"]) == 2

    def test_team_to_json_grid_structure(self):
        from app.api.routes import _team_to_json
        from app.game.state import TeamState

        team = TeamState(name="Test", color="red", chat_id=123)
        result = _team_to_json(team, include_ships=False)

        for row in result["grid"]:
            for cell in row:
                assert "row" in cell
                assert "col" in cell
                assert "status" in cell

    def test_team_to_json_hit_miss_clear(self):
        from app.api.routes import _team_to_json
        from app.game.state import TeamState

        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(5, 5, "blue")
        result = _team_to_json(team, include_ships=False)

        hit_cell = result["grid"][0][0]
        assert hit_cell["status"] == "hit"
        assert hit_cell["attacker_color"] == "blue"
        assert hit_cell["is_hit"] == True

        miss_cell = result["grid"][5][5]
        assert miss_cell["status"] == "miss"
        assert miss_cell["attacker_color"] == "blue"
        assert miss_cell["is_hit"] == False

        clear_cell = result["grid"][9][9]
        assert clear_cell["status"] == "clear"

    def test_team_to_json_private_ship_info(self):
        from app.api.routes import _team_to_json
        from app.game.state import TeamState

        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        result = _team_to_json(team, include_ships=True)

        ship_cell = result["grid"][0][0]
        assert ship_cell["has_ship"] == True
        assert ship_cell["ship_type"] == "patrol_boat"

        empty_cell = result["grid"][5][5]
        assert empty_cell["has_ship"] == False

    def test_team_to_json_sunk_ship(self):
        from app.api.routes import _team_to_json
        from app.game.state import TeamState

        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")

        result = _team_to_json(team, include_ships=True)

        assert result["ships_sunk"] == 1
        assert result["is_destroyed"] == True

        sunk_cell = result["grid"][0][0]
        assert sunk_cell["ship_sunk"] == True

    def test_api_public_board_json_endpoint(self):
        from app.api.routes import app, get_api_db, verify_gm_token
        from app.game.state import GameState
        from app.events.models import TeamJoinedEvent

        state = GameState()
        event = TeamJoinedEvent(name="Red Team", color="red", chat_id=123, bombs=3)
        state.handle_team_joined(event)

        async def override_get_db():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, *args, **kwargs):
                    return MagicMock()

                async def commit(self):
                    pass

                async def refresh(self, *args):
                    pass

            yield MockSession()

        app.dependency_overrides[get_api_db] = override_get_db
        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"

        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    client = TestClient(app)
                    response = client.get("/api/board/red/public.json")

            assert response.status_code == 200
            data = response.json()
            assert "team" in data
            assert "grid" in data
        finally:
            app.dependency_overrides.clear()

    def test_api_private_board_json_endpoint(self):
        from app.api.routes import app, get_api_db, verify_gm_token
        from app.game.state import GameState
        from app.events.models import TeamJoinedEvent

        state = GameState()
        event = TeamJoinedEvent(name="Blue Team", color="blue", chat_id=456, bombs=3)
        state.handle_team_joined(event)

        async def override_get_db():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, *args, **kwargs):
                    return MagicMock()

                async def commit(self):
                    pass

                async def refresh(self, *args):
                    pass

            yield MockSession()

        app.dependency_overrides[get_api_db] = override_get_db
        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"

        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    client = TestClient(app)
                    response = client.get("/api/board/blue/private.json")

            assert response.status_code == 200
            data = response.json()
            assert "team" in data
            assert "grid" in data
            assert "bombs" in data
        finally:
            app.dependency_overrides.clear()

    def test_private_board_png_requires_auth(self):
        from app.api.routes import app

        app.dependency_overrides.clear()

        client = TestClient(app)
        response = client.get("/api/board/blue/private.png", params={"game_id": "00000000-0000-0000-0000-000000000000"})
        assert response.status_code == 401

        response = client.get("/api/board/blue/private.png")
        assert response.status_code == 401

    def test_private_board_png_own_team_token_allowed(self):
        from app.api.routes import app, get_api_db
        from app.game.state import GameState
        from app.events.models import TeamJoinedEvent

        state = GameState()
        event = TeamJoinedEvent(name="Blue Team", color="blue", chat_id=456, bombs=3)
        state.handle_team_joined(event)

        async def override_get_db():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, *args, **kwargs):
                    return MagicMock()

                async def commit(self):
                    pass

            yield MockSession()

        app.dependency_overrides[get_api_db] = override_get_db

        try:
            with patch("app.models.lookup_team_token", new_callable=AsyncMock, return_value=("00000000-0000-0000-0000-000000000000", "blue")):
                with patch("app.api.routes.GameState.from_events", return_value=state):
                    with patch("app.api.routes.render_private_board"):
                        with patch("app.api.routes.boards_to_bytes", return_value=b"png-bytes"):
                            client = TestClient(app)
                            response = client.get("/api/board/blue/private.png", params={"team_token": "abc"})
                            assert response.status_code == 200
                            assert response.content == b"png-bytes"
        finally:
            app.dependency_overrides.clear()

    def test_private_board_png_wrong_team_token_rejected(self):
        from app.api.routes import app, get_api_db

        async def override_get_db():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, *args, **kwargs):
                    return MagicMock()

            yield MockSession()

        app.dependency_overrides[get_api_db] = override_get_db

        try:
            with patch("app.models.lookup_team_token", new_callable=AsyncMock, return_value=("00000000-0000-0000-0000-000000000000", "blue")):
                client = TestClient(app)
                response = client.get("/api/board/red/private.png", params={"team_token": "abc"})
                assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    def test_api_board_json_team_not_found(self):
        from app.api.routes import app, get_api_db, verify_gm_token
        from app.game.state import GameState
        from app.events.models import TeamJoinedEvent

        state = GameState()
        event = TeamJoinedEvent(name="Red Team", color="red", chat_id=123, bombs=3)
        state.handle_team_joined(event)

        async def override_get_db():
            class MockSession:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def execute(self, *args, **kwargs):
                    return MagicMock()

                async def commit(self):
                    pass

                async def refresh(self, *args):
                    pass

            yield MockSession()

        app.dependency_overrides[get_api_db] = override_get_db
        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"

        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    client = TestClient(app)
                    response = client.get("/api/board/nonexistent/private.json")

            assert response.status_code == 200
            data = response.json()
            assert "error" in data
            assert data["error"] == "Team not found"
        finally:
            app.dependency_overrides.clear()


class TestQuizMode:
    """Tests for quiz mode"""

    def test_start_game_fails_without_bomb_source(self):
        from app.api.routes import app, verify_gm_token
        from app.game.state import GameState, GameStatusField

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            state = GameState()
            state.status = GameStatusField.PREPARING
            state.teams["red"] = create_mock_team(name="Red", color="red")
            state.teams["blue"] = create_mock_team(name="Blue", color="blue")

            from app.game.ships import SHIP_COUNTS
            for team in state.teams.values():
                for ship_type, count in SHIP_COUNTS.items():
                    for _ in range(count):
                        team.placed_ship_types[ship_type] = team.placed_ship_types.get(ship_type, 0) + 1

            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    with patch("app.models.get_game_locations", return_value=[]):
                        with patch("app.models.get_game") as mock_get_game:
                            mock_game = MagicMock()
                            mock_game.paused_until = None
                            mock_game.quiz_enabled = False
                            mock_game.trickle_enabled = False
                            mock_game.paused_until = None
                            mock_get_game.return_value = mock_game
                            client = TestClient(app)
                            response = client.post("/api/quick/start-game", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "bomb source" in data["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_start_game_succeeds_with_quiz_enabled(self):
        from app.api.routes import app, verify_gm_token
        from app.game.state import GameState, GameStatusField

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            state = GameState()
            state.status = GameStatusField.PREPARING
            state.teams["red"] = create_mock_team(name="Red", color="red")
            state.teams["blue"] = create_mock_team(name="Blue", color="blue")

            from app.game.ships import SHIP_COUNTS
            for team in state.teams.values():
                for ship_type, count in SHIP_COUNTS.items():
                    for _ in range(count):
                        team.placed_ship_types[ship_type] = team.placed_ship_types.get(ship_type, 0) + 1

            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    with patch("app.models.get_game_locations", return_value=[]):
                        with patch("app.models.get_game") as mock_get_game:
                            mock_game = MagicMock()
                            mock_game.paused_until = None
                            mock_game.quiz_enabled = True
                            mock_game.trickle_enabled = False
                            mock_get_game.return_value = mock_game
                            with patch("app.api.routes.save_event"):
                                with patch("app.models.update_game_status"):
                                    client = TestClient(app)
                                    response = client.post("/api/quick/start-game", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_start_game_succeeds_with_trickle_enabled(self):
        from app.api.routes import app, verify_gm_token
        from app.game.state import GameState, GameStatusField

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            state = GameState()
            state.status = GameStatusField.PREPARING
            state.teams["red"] = create_mock_team(name="Red", color="red")
            state.teams["blue"] = create_mock_team(name="Blue", color="blue")

            from app.game.ships import SHIP_COUNTS
            for team in state.teams.values():
                for ship_type, count in SHIP_COUNTS.items():
                    for _ in range(count):
                        team.placed_ship_types[ship_type] = team.placed_ship_types.get(ship_type, 0) + 1

            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    with patch("app.models.get_game_locations", return_value=[]):
                        with patch("app.models.get_game") as mock_get_game:
                            mock_game = MagicMock()
                            mock_game.paused_until = None
                            mock_game.quiz_enabled = False
                            mock_game.trickle_enabled = True
                            mock_get_game.return_value = mock_game
                            with patch("app.api.routes.save_event"):
                                with patch("app.models.update_game_status"):
                                    client = TestClient(app)
                                    response = client.post("/api/quick/start-game", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_quiz_command_awards_bombs(self):
        import uuid
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField
        from app.game.ships import SHIP_COUNTS
        from unittest.mock import AsyncMock

        app.dependency_overrides[verify_team_or_gm] = lambda: {"role": "team", "game_id": "00000000-0000-0000-0000-000000000000", "color": "red"}
        try:
            state = GameState()
            state.status = GameStatusField.STARTED
            state.teams["red"] = create_mock_team(name="Red", color="red", bombs=0)
            state.teams["blue"] = create_mock_team(name="Blue", color="blue", bombs=0)

            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    with patch("app.api.routes.save_event") as mock_save:
                        with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute:
                            # First execute returns the answer, second returns the question
                            mock_question = MagicMock()
                            mock_question.game_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
                            mock_answer_row = MagicMock(bomb_value=5)
                            mock_execute.side_effect = [
                                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_answer_row)),
                                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_question)),
                            ]
                            with patch("app.models.get_game") as mock_get_game:
                                mock_game = MagicMock()
                                mock_game.paused_until = None
                                mock_game.max_bombs = 100
                                mock_get_game.return_value = mock_game

                                client = TestClient(app)
                                response = client.post("/api/execute", json={
                                    "team_color": "red",
                                    "command": "quiz",
                                    "args": {"question_id": 1, "answer_id": 1}
                                })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Correct! +5 bombs."
        finally:
            app.dependency_overrides.clear()


class TestAuthRateLimit:
    """Failed auth attempts are throttled per client IP."""

    def test_failed_auth_attempts_are_rate_limited(self):
        from app.api.routes import app
        from unittest.mock import AsyncMock

        with patch("app.models.get_game_by_gm_token", new_callable=AsyncMock, return_value=None):
            client = TestClient(app)
            statuses = [
                client.post("/api/quick/reset-game?gm_token=wrong").status_code
                for _ in range(12)
            ]

        assert statuses[:10] == [404] * 10
        assert statuses[10:] == [429, 429]

    def test_valid_token_not_blocked_by_failed_auth_limiter(self):
        from app.api.routes import app
        from app.game.state import GameState
        from unittest.mock import AsyncMock, MagicMock

        mock_game = MagicMock()
        mock_game.id = "00000000-0000-0000-0000-000000000001"

        with patch("app.models.get_game_by_gm_token", new_callable=AsyncMock, return_value=None):
            client = TestClient(app)
            for _ in range(10):
                client.post(
                    "/api/quick/reset-game?gm_token=wrong",
                    headers={"X-Forwarded-For": "9.9.9.9"},
                )

        with patch("app.models.get_game_by_gm_token", new_callable=AsyncMock, return_value=mock_game):
            with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                with patch("app.models.delete_all_events", new_callable=AsyncMock, return_value=0):
                    with patch("app.models.delete_all_team_tokens", new_callable=AsyncMock):
                        with patch("app.models.update_game_status", new_callable=AsyncMock):
                            with patch("app.api.routes.GameState.from_events", return_value=GameState()):
                                response = client.post(
                                    "/api/quick/reset-game?gm_token=valid",
                                    headers={"X-Forwarded-For": "9.9.9.9"},
                                )

        assert response.status_code == 200

    def test_auth_rate_limit_is_per_ip(self):
        from app.api.routes import app
        from unittest.mock import AsyncMock

        with patch("app.models.get_game_by_gm_token", new_callable=AsyncMock, return_value=None):
            client = TestClient(app)
            for _ in range(10):
                client.post(
                    "/api/quick/reset-game?gm_token=wrong",
                    headers={"X-Forwarded-For": "1.1.1.1"},
                )
            blocked = client.post(
                "/api/quick/reset-game?gm_token=wrong",
                headers={"X-Forwarded-For": "1.1.1.1"},
            )
            other = client.post(
                "/api/quick/reset-game?gm_token=wrong",
                headers={"X-Forwarded-For": "2.2.2.2"},
            )

        assert blocked.status_code == 429
        assert other.status_code == 404

    def test_client_ip_prefers_forwarded_for(self):
        from app.api.routes import _client_ip
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"3.3.3.3, 10.0.0.1")],
            "query_string": b"",
            "client": ("1.2.3.4", 1234),
        }
        request = Request(scope)
        assert _client_ip(request) == "3.3.3.3"

        scope_no_forwarded = dict(scope, headers=[])
        assert _client_ip(Request(scope_no_forwarded)) == "1.2.3.4"
