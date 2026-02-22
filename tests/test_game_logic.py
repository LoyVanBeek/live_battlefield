import pytest
from app.game.ships import (
    parse_coordinate,
    validate_ship_placement,
    get_ship_cells,
    SHIP_SIZES,
    SHIP_COUNTS,
)
from app.game.state import GameState, BombResult, TeamState


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


class TestTeamState:
    def test_place_ship(self):
        team = TeamState(name="Test", color="red", chat_id=123)

        result = team.place_ship("airplane_carrier", 0, 0, "horizontal")
        assert result == True
        assert len(team.ships) == 1
        assert team.placed_ship_types["airplane_carrier"] == 1

    def test_cannot_place_same_ship_twice(self):
        team = TeamState(name="Test", color="red", chat_id=123)

        team.place_ship("airplane_carrier", 0, 0, "horizontal")
        result = team.place_ship("airplane_carrier", 5, 5, "horizontal")
        assert result == False

    def test_can_place_all_ship_types(self):
        team = TeamState(name="Test", color="red", chat_id=123)

        assert team.can_place_ship("airplane_carrier") == True
        assert team.can_place_ship("battleship") == True

        team.place_ship("airplane_carrier", 0, 0, "horizontal")
        assert team.can_place_ship("airplane_carrier") == False
        assert team.can_place_ship("battleship") == True

    def test_all_ships_placed(self):
        team = TeamState(name="Test", color="red", chat_id=123)

        assert team.has_all_ships() == False

        team.placed_ship_types = {
            "airplane_carrier": 1,
            "battleship": 2,
            "torpedo_hunter": 3,
            "patrol_boat": 4,
        }

        assert team.has_all_ships() == True

    def test_receive_bomb_hit(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        result, ship = team.receive_bomb(0, 0, "blue")

        assert result == BombResult.HIT
        assert ship is not None
        assert ship.ship_type == "patrol_boat"
        assert ship.hits == 1

    def test_receive_bomb_miss(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        result, ship = team.receive_bomb(5, 5, "blue")

        assert result == BombResult.MISS
        assert ship is None

    def test_receive_bomb_already_bombed(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        team.receive_bomb(0, 0, "blue")
        result, ship = team.receive_bomb(0, 0, "green")

        assert result == BombResult.ALREADY_BOMBED

    def test_ship_sunk(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        assert not team.ships[0].is_sunk()

        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")

        assert team.ships[0].is_sunk()
        assert len(team.get_sunk_ships()) == 1

    def test_team_destroyed(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        assert not team.is_destroyed()

        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")

        assert team.is_destroyed()


class TestGameState:
    def test_team_joined(self):
        state = GameState()
        state.handle_team_joined(
            {"name": "Team A", "color": "red", "chat_id": 123, "bombs": 3}
        )

        assert "red" in state.teams
        assert state.teams["red"].name == "Team A"
        assert state.teams["red"].bombs == 3

    def test_get_next_color(self):
        state = GameState()

        assert state.get_next_color() == "red"

        state.handle_team_joined(
            {"name": "Team A", "color": "red", "chat_id": 123, "bombs": 3}
        )

        assert state.get_next_color() == "blue"

    def test_is_team_name_taken(self):
        state = GameState()

        assert state.is_team_name_taken("Team A") == False

        state.handle_team_joined(
            {"name": "Team A", "color": "red", "chat_id": 123, "bombs": 3}
        )

        assert state.is_team_name_taken("Team A") == True
        assert state.is_team_name_taken("team a") == True
        assert state.is_team_name_taken("Team B") == False

    def test_bomb_thrown(self):
        state = GameState()
        state.handle_team_joined(
            {"name": "Team A", "color": "red", "chat_id": 123, "bombs": 5}
        )
        state.handle_team_joined(
            {"name": "Team B", "color": "blue", "chat_id": 456, "bombs": 3}
        )
        state.handle_ship_placed(
            {
                "color": "blue",
                "ship_type": "patrol_boat",
                "row": 0,
                "col": 0,
                "direction": "horizontal",
            }
        )

        state.handle_bomb_thrown(
            {"attacker_color": "red", "target_color": "blue", "row": 0, "col": 0}
        )

        assert state.teams["red"].bombs == 4
        assert state.teams["blue"].public_board[0][0] == ("red", True)

    def test_code_redeemed(self):
        state = GameState()
        state.handle_team_joined(
            {"name": "Team A", "color": "red", "chat_id": 123, "bombs": 3}
        )
        state.handle_location_added(
            {"number": 1, "latitude": 52.0, "longitude": 5.0, "code": "ABCD"}
        )

        state.handle_code_redeemed(
            {"color": "red", "location_number": 1, "code": "ABCD"}
        )

        assert state.teams["red"].bombs == 4

    def test_from_events(self):
        events = [
            type(
                "Event",
                (),
                {
                    "event_type": "team_joined",
                    "payload": {
                        "name": "Team A",
                        "color": "red",
                        "chat_id": 123,
                        "bombs": 3,
                    },
                },
            )(),
            type(
                "Event",
                (),
                {
                    "event_type": "ship_placed",
                    "payload": {
                        "color": "red",
                        "ship_type": "patrol_boat",
                        "row": 0,
                        "col": 0,
                        "direction": "horizontal",
                    },
                },
            )(),
        ]

        state = GameState.from_events(events)

        assert "red" in state.teams
        assert len(state.teams["red"].ships) == 1
