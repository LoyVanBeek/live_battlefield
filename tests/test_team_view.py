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
