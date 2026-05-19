from typing import TypedDict, NotRequired


class ShipDict(TypedDict):
    ship_type: str
    cells: list[tuple[int, int]]
    hits: int
    is_sunk: bool


class TeamStateDict(TypedDict):
    name: str
    color: str
    chat_id: int
    bombs: int
    ships: list[ShipDict]
    placed_ship_types: dict[str, int]
    ships_placed: int
    sunk_ships: int
    is_destroyed: bool


class GameStateDict(TypedDict):
    teams: dict[str, TeamStateDict]
    location_codes: dict[int, str]
    location_counter: int
    status: str


class CellData(TypedDict):
    row: int
    col: int
    status: str
    attacker_color: NotRequired[str]
    is_hit: NotRequired[bool]
    has_ship: NotRequired[bool]
    ship_type: NotRequired[str]
    ship_sunk: NotRequired[bool]


class TeamJsonResult(TypedDict):
    team: dict[str, str]
    grid: list[list[CellData]]
    bombs: NotRequired[int]
    ships: NotRequired[list[ShipDict]]
    ships_sunk: NotRequired[int]
    is_destroyed: NotRequired[bool]
