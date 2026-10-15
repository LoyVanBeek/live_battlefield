from app.team_view import _serialize_grid, _serialize_team
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


class TestSerializeTeamEliminated:
    """The 'x' (eliminated) flag drives the team page's 💀 indicator."""

    @staticmethod
    def _sunk_team() -> TeamState:
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")
        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")
        return team

    def test_flagged_when_all_ships_sunk_and_started(self):
        assert _serialize_team(self._sunk_team(), private=True, status="started").get("x") == 1

    def test_flagged_when_all_ships_sunk_and_ended(self):
        assert _serialize_team(self._sunk_team(), private=False, status="ended").get("x") == 1

    def test_not_flagged_while_preparing(self):
        assert "x" not in _serialize_team(self._sunk_team(), private=False, status="preparing")

    def test_not_flagged_for_empty_fleet(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        assert "x" not in _serialize_team(team, private=False, status="started")

    def test_not_flagged_while_ships_remain(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")
        team.place_ship("patrol_boat", 2, 0, "horizontal")
        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")
        assert "x" not in _serialize_team(team, private=False, status="started")
