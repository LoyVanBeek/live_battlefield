from app.game.state import TeamState, BombResult


class TestTeamState:
    def test_place_ship(self):
        team = TeamState(name="Test", color="red", chat_id=123)

        result, _ = team.place_ship("airplane_carrier", 0, 0, "horizontal")
        assert result == True
        assert len(team.ships) == 1
        assert team.placed_ship_types["airplane_carrier"] == 1

    def test_cannot_place_same_ship_twice(self):
        team = TeamState(name="Test", color="red", chat_id=123)

        team.place_ship("airplane_carrier", 0, 0, "horizontal")
        result, _ = team.place_ship("airplane_carrier", 5, 5, "horizontal")
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

        result, ship, _ = team.receive_bomb(0, 0, "blue")

        assert result == BombResult.HIT
        assert ship is not None
        assert ship.ship_type == "patrol_boat"
        assert ship.hits == 1

    def test_receive_bomb_miss(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        result, ship, _ = team.receive_bomb(5, 5, "blue")

        assert result == BombResult.MISS
        assert ship is None

    def test_receive_bomb_already_bombed(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        team.receive_bomb(0, 0, "blue")
        result, ship, _ = team.receive_bomb(0, 0, "green")

        assert result == BombResult.ALREADY_BOMBED

    def test_ship_sunk(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        assert not team.ships[0].is_sunk()

        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")

        assert team.ships[0].is_sunk() == True
        assert len(team.get_sunk_ships()) == 1

    def test_team_destroyed(self):
        team = TeamState(name="Test", color="red", chat_id=123)
        team.place_ship("patrol_boat", 0, 0, "horizontal")

        assert not team.is_destroyed()

        team.receive_bomb(0, 0, "blue")
        team.receive_bomb(0, 1, "blue")

        assert team.is_destroyed() == True
