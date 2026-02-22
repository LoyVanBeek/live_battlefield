from app.database import EventType
from app.game.ships import (
    SHIP_SIZES, SHIP_COUNTS, VALID_SHIP_TYPES, VALID_DIRECTIONS,
    parse_coordinate, validate_ship_placement, get_ship_cells, coordinate_to_string
)
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


TEAM_COLORS = ["red", "blue", "green", "purple", "orange", "yellow"]


class BombResult(Enum):
    HIT = "hit"
    MISS = "miss"
    ALREADY_BOMBED = "already_bombed"


@dataclass
class Ship:
    ship_type: str
    cells: list[tuple[int, int]]
    hits: int = 0
    
    def is_sunk(self) -> bool:
        return self.hits >= len(self.cells)


@dataclass
class TeamState:
    name: str
    color: str
    chat_id: int
    bombs: int = 3
    ships: list[Ship] = field(default_factory=list)
    placed_ship_types: dict[str, int] = field(default_factory=dict)
    private_board: list[list[bool]] = field(default_factory=lambda: [[False] * 10 for _ in range(10)])
    public_board: list[list[Optional[tuple[str, bool]]]] = field(default_factory=lambda: [[None] * 10 for _ in range(10)])
    bombed_cells: list[tuple[int, int]] = field(default_factory=list)
    
    def get_ship_at(self, row: int, col: int) -> Optional[Ship]:
        for ship in self.ships:
            if (row, col) in ship.cells:
                return ship
        return None
    
    def can_place_ship(self, ship_type: str) -> bool:
        if ship_type not in SHIP_COUNTS:
            return False
        placed = self.placed_ship_types.get(ship_type, 0)
        return placed < SHIP_COUNTS[ship_type]
    
    def place_ship(self, ship_type: str, row: int, col: int, direction: str) -> bool:
        if not self.can_place_ship(ship_type):
            return False
        
        size = SHIP_SIZES[ship_type]
        existing_ships = [ship.cells for ship in self.ships]
        
        if not validate_ship_placement(row, col, size, direction, existing_ships):
            return False
        
        cells = get_ship_cells(row, col, size, direction)
        ship = Ship(ship_type=ship_type, cells=cells)
        self.ships.append(ship)
        
        for r, c in cells:
            self.private_board[r][c] = True
        
        self.placed_ship_types[ship_type] = self.placed_ship_types.get(ship_type, 0) + 1
        return True
    
    def has_all_ships(self) -> bool:
        for ship_type, count in SHIP_COUNTS.items():
            if self.placed_ship_types.get(ship_type, 0) < count:
                return False
        return True
    
    def receive_bomb(self, row: int, col: int, attacker_color: str) -> tuple[BombResult, Optional[Ship]]:
        cell = (row, col)
        if cell in self.bombed_cells:
            return BombResult.ALREADY_BOMBED, None
        
        self.bombed_cells.append(cell)
        
        ship = self.get_ship_at(row, col)
        if ship:
            ship.hits += 1
            self.public_board[row][col] = (attacker_color, True)
            return BombResult.HIT, ship
        
        self.public_board[row][col] = (attacker_color, False)
        return BombResult.MISS, None
    
    def get_sunk_ships(self) -> list[Ship]:
        return [s for s in self.ships if s.is_sunk()]
    
    def is_destroyed(self) -> bool:
        return all(s.is_sunk() for s in self.ships)


@dataclass
class GameState:
    teams: dict[str, TeamState] = field(default_factory=dict)
    location_codes: dict[int, str] = field(default_factory=dict)
    location_counter: int = 0
    
    @classmethod
    def from_events(cls, events: list) -> "GameState":
        state = cls()
        
        for event in events:
            event_type = event.event_type
            payload = event.payload
            
            if event_type == EventType.TEAM_JOINED:
                state.handle_team_joined(payload)
            elif event_type == EventType.SHIP_PLACED:
                state.handle_ship_placed(payload)
            elif event_type == EventType.BOMB_THROWN:
                state.handle_bomb_thrown(payload)
            elif event_type == EventType.CODE_REDEEMED:
                state.handle_code_redeemed(payload)
            elif event_type == EventType.LOCATION_ADDED:
                state.handle_location_added(payload)
        
        return state
    
    def handle_team_joined(self, payload: dict) -> None:
        color = payload["color"]
        self.teams[color] = TeamState(
            name=payload["name"],
            color=color,
            chat_id=payload["chat_id"],
            bombs=payload.get("bombs", 3)
        )
    
    def handle_ship_placed(self, payload: dict) -> None:
        color = payload["color"]
        if color not in self.teams:
            return
        
        team = self.teams[color]
        team.place_ship(
            payload["ship_type"],
            payload["row"],
            payload["col"],
            payload["direction"]
        )
    
    def handle_bomb_thrown(self, payload: dict) -> None:
        attacker_color = payload["attacker_color"]
        target_color = payload["target_color"]
        row = payload["row"]
        col = payload["col"]
        
        if attacker_color not in self.teams:
            return
        if target_color not in self.teams:
            return
        
        attacker = self.teams[attacker_color]
        target = self.teams[target_color]
        
        if attacker.bombs <= 0:
            return
        
        attacker.bombs -= 1
        result, ship = target.receive_bomb(row, col, attacker_color)
        
        payload["result"] = result.value
        if ship:
            payload["ship_type"] = ship.ship_type
            payload["ship_sunk"] = ship.is_sunk()
    
    def handle_code_redeemed(self, payload: dict) -> None:
        color = payload["color"]
        location_number = payload["location_number"]
        
        if color not in self.teams:
            return
        
        if location_number not in self.location_codes:
            payload["success"] = False
            return
        
        code = payload["code"]
        if self.location_codes[location_number] != code:
            payload["success"] = False
            return
        
        self.teams[color].bombs += 1
        payload["success"] = True
    
    def handle_location_added(self, payload: dict) -> None:
        number = payload["number"]
        code = payload["code"]
        self.location_codes[number] = code
        if number > self.location_counter:
            self.location_counter = number
    
    def get_next_color(self) -> Optional[str]:
        for color in TEAM_COLORS:
            if color not in self.teams:
                return color
        return None
    
    def is_team_name_taken(self, name: str) -> bool:
        return any(t.name.lower() == name.lower() for t in self.teams.values())
    
    def get_winner(self) -> Optional[TeamState]:
        active_teams = [t for t in self.teams.values() if t.has_all_ships()]
        if len(active_teams) <= 1:
            for team in active_teams:
                if team.is_destroyed():
                    continue
                return team
        survivors = [t for t in active_teams if not t.is_destroyed()]
        if len(survivors) == 1:
            return survivors[0]
        return None
