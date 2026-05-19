from app.types import (
    ShipDict,
    TeamStateDict,
    GameStateDict,
    CellData,
    TeamJsonResult,
)


class TestTypedDicts:
    def test_ship_dict(self):
        data: ShipDict = {
            "ship_type": "patrol_boat",
            "cells": [(0, 0), (0, 1)],
            "hits": 1,
            "is_sunk": False,
        }
        assert data["ship_type"] == "patrol_boat"
        assert data["cells"] == [(0, 0), (0, 1)]
        assert data["hits"] == 1
        assert data["is_sunk"] is False

    def test_ship_dict_sunk(self):
        data: ShipDict = {
            "ship_type": "patrol_boat",
            "cells": [(0, 0), (0, 1)],
            "hits": 2,
            "is_sunk": True,
        }
        assert data["is_sunk"] is True

    def test_team_state_dict(self):
        ship: ShipDict = {
            "ship_type": "patrol_boat",
            "cells": [(0, 0), (0, 1)],
            "hits": 0,
            "is_sunk": False,
        }
        data: TeamStateDict = {
            "name": "Team A",
            "color": "red",
            "chat_id": 123,
            "bombs": 5,
            "ships": [ship],
            "placed_ship_types": {"patrol_boat": 1},
            "ships_placed": 1,
            "sunk_ships": 0,
            "is_destroyed": False,
        }
        assert data["name"] == "Team A"
        assert data["chat_id"] == 123
        assert len(data["ships"]) == 1
        assert data["is_destroyed"] is False

    def test_team_state_dict_chat_id_none(self):
        data: TeamStateDict = {
            "name": "AI Player",
            "color": "purple",
            "chat_id": None,
            "bombs": 3,
            "ships": [],
            "placed_ship_types": {},
            "ships_placed": 0,
            "sunk_ships": 0,
            "is_destroyed": False,
        }
        assert data["chat_id"] is None

    def test_game_state_dict(self):
        team_a: TeamStateDict = {
            "name": "Team A",
            "color": "red",
            "chat_id": 1,
            "bombs": 5,
            "ships": [],
            "placed_ship_types": {},
            "ships_placed": 0,
            "sunk_ships": 0,
            "is_destroyed": False,
        }
        data: GameStateDict = {
            "teams": {"red": team_a},
            "location_codes": {1: "ABCD"},
            "location_counter": 1,
            "status": "started",
        }
        assert data["teams"]["red"]["name"] == "Team A"
        assert data["location_codes"][1] == "ABCD"
        assert data["status"] == "started"

    def test_game_state_dict_empty(self):
        data: GameStateDict = {
            "teams": {},
            "location_codes": {},
            "location_counter": 0,
            "status": "preparing",
        }
        assert len(data["teams"]) == 0

    def test_cell_data_clear(self):
        data: CellData = {"row": 0, "col": 0, "status": "clear"}
        assert data["row"] == 0
        assert data["status"] == "clear"
        assert "attacker_color" not in data

    def test_cell_data_hit(self):
        data: CellData = {
            "row": 3,
            "col": 5,
            "status": "hit",
            "attacker_color": "blue",
            "is_hit": True,
        }
        assert data["status"] == "hit"
        assert data["attacker_color"] == "blue"

    def test_cell_data_with_ship(self):
        data: CellData = {
            "row": 1,
            "col": 2,
            "status": "clear",
            "has_ship": True,
            "ship_type": "battleship",
            "ship_sunk": False,
        }
        assert data["has_ship"] is True
        assert data["ship_type"] == "battleship"

    def test_team_json_result_no_ships(self):
        grid: list[list[CellData]] = [
            [{"row": 0, "col": 0, "status": "clear"}]
        ]
        data: TeamJsonResult = {
            "team": {"name": "Team A", "color": "red"},
            "grid": grid,
        }
        assert data["team"]["name"] == "Team A"
        assert "bombs" not in data

    def test_team_json_result_with_ships(self):
        grid: list[list[CellData]] = [
            [{"row": 0, "col": 0, "status": "clear"}]
        ]
        ship: ShipDict = {
            "ship_type": "patrol_boat",
            "cells": [(0, 0), (0, 1)],
            "hits": 0,
            "is_sunk": False,
        }
        data: TeamJsonResult = {
            "team": {"name": "Team A", "color": "red"},
            "grid": grid,
            "bombs": 3,
            "ships": [ship],
            "ships_sunk": 0,
            "is_destroyed": False,
        }
        assert data["bombs"] == 3
        assert len(data["ships"]) == 1
