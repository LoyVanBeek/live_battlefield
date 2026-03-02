from app.game.ships import (
    validate_ship_placement,
    get_ship_cells,
)


class TestShipPlacement:
    def test_validate_empty_board(self):
        assert validate_ship_placement(0, 0, 4, "horizontal", []) == True
        assert validate_ship_placement(0, 0, 4, "vertical", []) == True

    def test_validate_out_of_bounds(self):
        assert validate_ship_placement(0, 7, 4, "horizontal", []) == False
        assert validate_ship_placement(7, 0, 4, "vertical", []) == False

    def test_validate_ship_touching(self):
        existing = [[(0, 0), (0, 1), (0, 2), (0, 3)]]
        assert validate_ship_placement(1, 0, 4, "vertical", existing) == False
        assert validate_ship_placement(0, 4, 4, "horizontal", existing) == False

    def test_validate_ship_not_touching(self):
        existing = [[(0, 0), (0, 1), (0, 2), (0, 3)]]
        assert validate_ship_placement(2, 0, 4, "vertical", existing) == True

    def test_get_ship_cells(self):
        cells = get_ship_cells(0, 0, 4, "horizontal")
        assert cells == [(0, 0), (0, 1), (0, 2), (0, 3)]

        cells = get_ship_cells(0, 0, 4, "vertical")
        assert cells == [(0, 0), (1, 0), (2, 0), (3, 0)]
