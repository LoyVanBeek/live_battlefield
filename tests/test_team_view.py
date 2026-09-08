from unittest.mock import AsyncMock, MagicMock, patch

from app.team_view import _serialize_grid
from app.game.state import TeamState


class TestSerializeGrid:
    def test_public_grid_hides_live_ships(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        grid = _serialize_grid(team, include_ships=False)

        assert not any(cell.get("p") for row in grid for cell in row)

    def test_public_grid_reveals_sunk_ships(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")
        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")

        grid = _serialize_grid(team, include_ships=False)

        assert grid[0][0].get("p") == 1
        assert grid[0][0].get("k") == 1
        assert grid[0][1].get("p") == 1
        assert grid[0][1].get("k") == 1
        assert grid[0][0].get("s") == "h"
        assert grid[0][0].get("a") == "blue"

    def test_private_grid_still_marks_all_ships(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")
        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")

        grid = _serialize_grid(team, include_ships=True)

        assert grid[0][0].get("p") == 1
        assert grid[0][0].get("k") == 1
        assert grid[0][1].get("p") == 1
        assert grid[0][1].get("k") == 1


class TestRadarShipView:
    def _radar_state(self, radar_sunk=False):
        from app.game.state import GameState, TeamState, Ship

        state = GameState()
        red = TeamState(name="Red", color="red", chat_id=1, bombs=5)
        radar = Ship(
            ship_type="patrol_boat", cells=[(0, 0), (0, 1)],
            traits=["radar"],
        )
        if radar_sunk:
            radar.hits = 2
        red.ships.append(radar)
        red.ships.append(Ship(ship_type="battleship", cells=[(9, 0), (9, 1), (9, 2), (9, 3)]))

        blue = TeamState(name="Blue", color="blue", chat_id=2, bombs=3)
        # Blue ships: one near red's radar (A1 area), one far away
        blue.place_ship("patrol_boat", 2, 2, "horizontal")
        blue.place_ship("battleship", 8, 3, "horizontal")
        state.teams = {"red": red, "blue": blue}
        return state

    def _view(self, state, viewer_color="red", radius=3):
        from app.team_view import get_team_view
        import app.team_view as tv
        from unittest.mock import AsyncMock, patch
        import uuid

        game = MagicMock()
        game.specials = {"radar_ship": {"enabled": True, "radius_cells": radius}}
        game.trickle_enabled = False
        game.paused_until = None

        token_game = ("00000000-0000-0000-0000-000000000001", viewer_color)
        with patch.object(tv, "lookup_team_token", new_callable=AsyncMock, return_value=token_game):
            with patch.object(tv, "get_game_events", new_callable=AsyncMock, return_value=[]):
                with patch.object(tv, "get_game", new_callable=AsyncMock, return_value=game):
                    with patch.object(tv.GameState, "from_events", return_value=state):
                        import asyncio
                        return asyncio.run(get_team_view("tok", AsyncMock()))

    def test_own_view_reveals_enemy_ships_within_radius(self):
        view = self._view(self._radar_state(), viewer_color="red", radius=3)
        blue_view = next(t for t in view["ts"] if t["c"] == "blue")

        grid = blue_view["g"]
        # Blue patrol boat at (2,2)-(2,3): within 3 of red radar at (0,0)-(0,1)
        assert grid[2][2].get("p") == 1
        assert grid[2][3].get("p") == 1
        # Blue battleship at row 8: far away, must NOT be revealed
        assert grid[8][3].get("p") is None
        assert grid[8][6].get("p") is None

    def test_sunk_radar_ship_reveals_nothing(self):
        view = self._view(self._radar_state(radar_sunk=True), viewer_color="red", radius=3)
        blue_view = next(t for t in view["ts"] if t["c"] == "blue")
        assert blue_view["g"][2][2].get("p") is None

    def test_radar_badge_public_but_identity_hidden(self):
        view = self._view(self._radar_state(), viewer_color="blue", radius=3)
        red_view = next(t for t in view["ts"] if t["c"] == "red")
        # Blue sees the radar badge on red...
        assert red_view.get("rs") == 1
        # ...but red's un-sunk ships are NOT revealed to blue
        assert red_view["g"][0][0].get("p") is None
        assert red_view["g"][9][0].get("p") is None

    def test_no_badge_when_radar_sunk(self):
        view = self._view(self._radar_state(radar_sunk=True), viewer_color="blue", radius=3)
        red_view = next(t for t in view["ts"] if t["c"] == "red")
        assert red_view.get("rs") is None
