from app.game.ships import (
    SHIP_SIZES,
    SHIP_COUNTS,
    VALID_SHIP_TYPES,
    VALID_DIRECTIONS,
    parse_coordinate,
    validate_ship_placement,
    get_ship_cells,
    coordinate_to_string,
)
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from app.events.factory import create_events, _get_event_type_value
from app.events.models import (
    TeamJoinedEvent,
    ShipPlacedEvent,
    BombThrownEvent,
    CodeRedeemedEvent,
    LocationAddedEvent,
)


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
    private_board: list[list[bool]] = field(
        default_factory=lambda: [[False] * 10 for _ in range(10)]
    )
    public_board: list[list[Optional[tuple[str, bool]]]] = field(
        default_factory=lambda: [[None] * 10 for _ in range(10)]
    )
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

    def receive_bomb(
        self, row: int, col: int, attacker_color: str
    ) -> tuple[BombResult, Optional[Ship]]:
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
        typed_events = create_events(events)

        for event in typed_events:
            event_type_value = _get_event_type_value(event.event_type)

            if event_type_value == "team_joined":
                state.handle_team_joined(event)
            elif event_type_value == "ship_placed":
                state.handle_ship_placed(event)
            elif event_type_value == "bomb_thrown":
                state.handle_bomb_thrown(event)
            elif event_type_value == "code_redeemed":
                state.handle_code_redeemed(event)
            elif event_type_value == "location_added":
                state.handle_location_added(event)

        return state

    def handle_team_joined(self, event: TeamJoinedEvent) -> None:
        if event.quick_action:
            color = event.color
            if color and color in self.teams:
                self.handle_quick_action(event)
            return

        color = event.color
        self.teams[color] = TeamState(
            name=event.name,
            color=color,
            chat_id=event.chat_id,
            bombs=event.bombs,
        )

    def handle_quick_action(self, event) -> None:
        quick_action = event.quick_action
        color = event.color

        if not color or color not in self.teams:
            return

        team = self.teams[color]

        if quick_action == "add_bombs":
            count = getattr(event, "count", 1)
            team.bombs += count
        elif quick_action == "reset_team":
            team.ships = []
            team.placed_ship_types = {}
            team.private_board = [[False] * 10 for _ in range(10)]
            team.public_board = [[None] * 10 for _ in range(10)]
            team.bombed_cells = []
        elif quick_action == "place_all_ships":
            pass

    def handle_ship_placed(self, event: ShipPlacedEvent) -> None:
        if event.quick_action:
            self.handle_quick_action(event)
            return

        color = event.color
        if color not in self.teams:
            return
        team = self.teams[color]
        team.place_ship(event.ship_type, event.row, event.col, event.direction)

    def handle_bomb_thrown(self, event: BombThrownEvent) -> None:
        attacker_color = event.attacker_color
        target_color = event.target_color
        row = event.row
        col = event.col

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

        event.result = result.value
        if ship:
            event.ship_type = ship.ship_type
            event.ship_sunk = ship.is_sunk()

    def handle_code_redeemed(self, event: CodeRedeemedEvent) -> None:
        color = event.color
        location_number = event.location_number
        code = event.code

        if color not in self.teams:
            return

        if location_number not in self.location_codes:
            event.success = False
            return

        if self.location_codes[location_number] != code:
            event.success = False
            return

        self.teams[color].bombs += event.bombs_earned
        event.success = True

    def handle_location_added(self, event: LocationAddedEvent) -> None:
        number = event.number
        code = event.code
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

    def can_start(self, total_locations_needed: int = 33) -> bool:
        if not self.teams:
            return False
        if len(self.location_codes) < total_locations_needed:
            return False
        for team in self.teams.values():
            if not team.has_all_ships():
                return False
        return True

    def is_started(self, game_status: str) -> bool:
        return game_status == "started"

    def is_waiting(self, game_status: str) -> bool:
        return game_status == "waiting"

    def is_ended(self, game_status: str) -> bool:
        return game_status == "ended"
