import pytest
from app.game.ships import parse_coordinate


class TestCoordinateParsing:
    def test_parse_valid_coordinate(self):
        assert parse_coordinate("A1") == (0, 0)
        assert parse_coordinate("J10") == (9, 9)
        assert parse_coordinate("B2") == (1, 1)
        assert parse_coordinate("E5") == (4, 4)

    def test_parse_lowercase(self):
        assert parse_coordinate("a1") == (0, 0)
        assert parse_coordinate("b2") == (1, 1)

    def test_parse_invalid_coordinate(self):
        with pytest.raises(ValueError):
            parse_coordinate("K1")
        with pytest.raises(ValueError):
            parse_coordinate("A0")
        with pytest.raises(ValueError):
            parse_coordinate("A11")
