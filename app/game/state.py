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
from dataclasses import dataclass, field, replace
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

    def with_hits(self, hits: int) -> "Ship":
        return replace(self, hits=hits)


def _copy_team(
    team: "TeamState",
    *,
    name: Optional[str] = None,
    color: Optional[str] = None,
    chat_id: Optional[int] = None,
    bombs: Optional[int] = None,
    ships: Optional[list[Ship]] = None,
    placed_ship_types: Optional[dict[str, int]] = None,
    private_board: Optional[list[list[bool]]] = None,
    public_board: Optional[list[list[Optional[tuple[str, bool]]]]] = None,
    bombed_cells: Optional[list[tuple[int, int]]] = None,
) -> "TeamState":
    return TeamState(
        name=name if name is not None else team.name,
        color=color if color is not None else team.color,
        chat_id=chat_id if chat_id is not None else team.chat_id,
        bombs=bombs if bombs is not None else team.bombs,
        ships=ships if ships is not None else team.ships,
        placed_ship_types=placed_ship_types
        if placed_ship_types is not None
        else team.placed_ship_types,
        private_board=private_board
        if private_board is not None
        else team.private_board,
        public_board=public_board if public_board is not None else team.public_board,
        bombed_cells=bombed_cells if bombed_cells is not None else team.bombed_cells,
    )


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

    def place_ship(
        self, ship_type: str, row: int, col: int, direction: str
    ) -> tuple[bool, "TeamState"]:
        if not self.can_place_ship(ship_type):
            return False, self

        size = SHIP_SIZES[ship_type]
        existing_ships = [ship.cells for ship in self.ships]

        if not validate_ship_placement(row, col, size, direction, existing_ships):
            return False, self

        cells = get_ship_cells(row, col, size, direction)
        new_ship = Ship(ship_type=ship_type, cells=cells)
        self.ships.append(new_ship)

        for r, c in cells:
            self.private_board[r][c] = True

        self.placed_ship_types[ship_type] = self.placed_ship_types.get(ship_type, 0) + 1

        return True, _copy_team(self)

    def has_all_ships(self) -> bool:
        for ship_type, count in SHIP_COUNTS.items():
            if self.placed_ship_types.get(ship_type, 0) < count:
                return False
        return True

    def receive_bomb(
        self, row: int, col: int, attacker_color: str
    ) -> tuple[BombResult, Optional[Ship], "TeamState"]:
        cell = (row, col)
        if cell in self.bombed_cells:
            return BombResult.ALREADY_BOMBED, None, self

        self.bombed_cells.append(cell)

        ship = self.get_ship_at(row, col)
        if ship:
            ship.hits += 1
            self.public_board[row][col] = (attacker_color, True)
            return BombResult.HIT, ship, _copy_team(self)

        self.public_board[row][col] = (attacker_color, False)
        return BombResult.MISS, None, _copy_team(self)

    def get_sunk_ships(self) -> list[Ship]:
        return [s for s in self.ships if s.is_sunk()]

    def is_destroyed(self) -> bool:
        return all(s.is_sunk() for s in self.ships)

    def with_bombs(self, bombs: int) -> "TeamState":
        return _copy_team(self, bombs=bombs)

    def with_reset(self) -> "TeamState":
        return _copy_team(
            self,
            bombs=3,
            ships=[],
            placed_ship_types={},
            private_board=[[False] * 10 for _ in range(10)],
            public_board=[[None] * 10 for _ in range(10)],
            bombed_cells=[],
        )


def _copy_game_state(
    state: "GameState",
    *,
    teams: Optional[dict[str, TeamState]] = None,
    location_codes: Optional[dict[int, str]] = None,
    location_counter: Optional[int] = None,
) -> "GameState":
    return GameState(
        teams=teams if teams is not None else state.teams,
        location_codes=location_codes
        if location_codes is not None
        else state.location_codes,
        location_counter=location_counter
        if location_counter is not None
        else state.location_counter,
    )


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
            state, _ = event.apply(state)

        return state

    def handle_team_joined(
        self, event: TeamJoinedEvent
    ) -> tuple["GameState", TeamJoinedEvent]:
        new_state, updated_event = event.apply(self)
        self.teams = new_state.teams
        self.location_codes = new_state.location_codes
        self.location_counter = new_state.location_counter
        return new_state, updated_event

    def handle_ship_placed(
        self, event: ShipPlacedEvent
    ) -> tuple["GameState", ShipPlacedEvent]:
        new_state, updated_event = event.apply(self)
        self.teams = new_state.teams
        self.location_codes = new_state.location_codes
        self.location_counter = new_state.location_counter
        return new_state, updated_event

    def handle_bomb_thrown(
        self, event: BombThrownEvent
    ) -> tuple["GameState", BombThrownEvent]:
        new_state, updated_event = event.apply(self)
        self.teams = new_state.teams
        self.location_codes = new_state.location_codes
        self.location_counter = new_state.location_counter
        return new_state, updated_event

    def handle_code_redeemed(
        self, event: CodeRedeemedEvent
    ) -> tuple["GameState", CodeRedeemedEvent]:
        new_state, updated_event = event.apply(self)
        self.teams = new_state.teams
        self.location_codes = new_state.location_codes
        self.location_counter = new_state.location_counter
        return new_state, updated_event

    def handle_location_added(
        self, event: LocationAddedEvent
    ) -> tuple["GameState", LocationAddedEvent]:
        new_state, updated_event = event.apply(self)
        self.teams = new_state.teams
        self.location_codes = new_state.location_codes
        self.location_counter = new_state.location_counter
        return new_state, updated_event

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
