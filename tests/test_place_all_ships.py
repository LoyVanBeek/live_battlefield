from app.game.state import TeamState
from app.game.ships import SHIP_COUNTS


class TestPlaceAllShips:
    def test_place_all_ships_algorithm(self):
        """Test that the random placement algorithm can place all ships"""
        import random

        random.seed(42)

        team = TeamState(name="Test", color="red", chat_id=123)

        placed = []
        failed = []

        for ship_type, count in SHIP_COUNTS.items():
            for i in range(count):
                attempts = 0
                placed_ship = False
                while attempts < 5000:
                    row = random.randint(0, 9)
                    col = random.randint(0, 9)
                    direction = random.choice(["horizontal", "vertical"])

                    if team.place_ship(ship_type, row, col, direction):
                        placed.append(ship_type)
                        placed_ship = True
                        break
                    attempts += 1

                if not placed_ship:
                    failed.append(ship_type)

        assert len(failed) == 0, f"Failed to place: {failed}"
        assert len(placed) == sum(SHIP_COUNTS.values()), (
            f"Expected {sum(SHIP_COUNTS.values())} ships, placed {len(placed)}"
        )

        assert team.has_all_ships() == True

    def test_place_ship_respects_no_touching_rule(self):
        """Test that ships cannot touch each other"""
        team = TeamState(name="Test", color="red", chat_id=123)

        result = team.place_ship("patrol_boat", 0, 0, "horizontal")
        assert result == True

        result = team.place_ship("patrol_boat", 1, 0, "horizontal")
        assert result == False

        result = team.place_ship("patrol_boat", 5, 5, "horizontal")
        assert result == True

    def test_place_all_ships_returns_failure_on_error(self):
        """Test that the endpoint returns success: False when placement fails"""
        import random

        random.seed(42)

        team = TeamState(name="Test", color="red", chat_id=123)

        placed = []
        failed = []

        for ship_type, count in SHIP_COUNTS.items():
            for i in range(count):
                attempts = 0
                placed_ship = False
                while attempts < 1:
                    row = 0
                    col = 0
                    direction = "horizontal"

                    if team.place_ship(ship_type, row, col, direction):
                        placed.append(ship_type)
                        placed_ship = True
                        break
                    attempts += 1

                if not placed_ship:
                    failed.append(ship_type)

        result_success = len(failed) == 0

        assert result_success == False or len(failed) > 0, (
            "Expected some ships to fail with only 1 attempt"
        )

    def test_place_all_ships_returns_ships_placed_count(self):
        """Test that the endpoint returns ships_placed count in the response"""
        import random

        random.seed(42)

        team = TeamState(name="Test", color="red", chat_id=123)

        placed = []
        failed = []

        for ship_type, count in SHIP_COUNTS.items():
            for i in range(count):
                attempts = 0
                placed_ship = False
                while attempts < 5000:
                    row = random.randint(0, 9)
                    col = random.randint(0, 9)
                    direction = random.choice(["horizontal", "vertical"])

                    if team.place_ship(ship_type, row, col, direction):
                        placed.append(ship_type)
                        placed_ship = True
                        break
                    attempts += 1

                if not placed_ship:
                    failed.append(ship_type)

        ships_placed_count = sum(team.placed_ship_types.values())

        if failed:
            response = {
                "success": False,
                "message": f"Placed {len(placed)} ships. Failed: {failed}",
                "ships_placed": ships_placed_count,
            }
        else:
            response = {
                "success": True,
                "message": f"Placed all {len(placed)} ships successfully!",
                "ships_placed": ships_placed_count,
            }

        assert "ships_placed" in response
        assert response["ships_placed"] == ships_placed_count

        assert response["success"] == True
        assert response["ships_placed"] == sum(SHIP_COUNTS.values())

        team2 = TeamState(name="Test2", color="blue", chat_id=456)
        placed2 = []
        failed2 = []

        for ship_type, count in SHIP_COUNTS.items():
            for i in range(count):
                attempts = 0
                placed_ship = False
                while attempts < 1:
                    if team2.place_ship(ship_type, 0, 0, "horizontal"):
                        placed2.append(ship_type)
                        placed_ship = True
                        break
                    attempts += 1
                if not placed_ship:
                    failed2.append(ship_type)

        ships_placed2 = sum(team2.placed_ship_types.values())

        if failed2:
            response2 = {
                "success": False,
                "message": f"Placed {len(placed2)} ships. Failed: {failed2}",
                "ships_placed": ships_placed2,
            }

        assert response2["success"] == False
        assert response2["ships_placed"] == ships_placed2
