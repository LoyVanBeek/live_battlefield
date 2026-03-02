SHIP_SIZES = {
    "airplane_carrier": 6,
    "battleship": 4,
    "torpedo_hunter": 3,
    "patrol_boat": 2,
}

SHIP_COUNTS = {
    "airplane_carrier": 1,
    "battleship": 2,
    "torpedo_hunter": 3,
    "patrol_boat": 4,
}

VALID_SHIP_TYPES = list(SHIP_SIZES.keys())
VALID_DIRECTIONS = ["horizontal", "vertical"]

BOARD_SIZE = 10
COLS = "ABCDEFGHIJ"


def parse_coordinate(coord: str) -> tuple[int, int]:
    coord = coord.strip().upper()
    if len(coord) < 2:
        raise ValueError(f"Invalid coordinate: {coord}")
    
    col = COLS.index(coord[0])
    row = int(coord[1:]) - 1
    
    if col < 0 or col >= BOARD_SIZE or row < 0 or row >= BOARD_SIZE:
        raise ValueError(f"Coordinate out of bounds: {coord}")
    
    return row, col


def coordinate_to_string(row: int, col: int) -> str:
    return f"{COLS[col]}{row + 1}"


def validate_ship_placement(
    row: int, 
    col: int, 
    size: int, 
    direction: str, 
    existing_ships: list[list[tuple[int, int]]]
) -> bool:
    if direction == "horizontal":
        if col + size > BOARD_SIZE:
            return False
        cells = [(row, c) for c in range(col, col + size)]
    else:
        if row + size > BOARD_SIZE:
            return False
        cells = [(r, col) for r in range(row, row + size)]
    
    for ship_cells in existing_ships:
        for cell in cells:
            for sc in ship_cells:
                if abs(cell[0] - sc[0]) <= 1 and abs(cell[1] - sc[1]) <= 1:
                    return False
    
    return True


def get_ship_cells(row: int, col: int, size: int, direction: str) -> list[tuple[int, int]]:
    if direction == "horizontal":
        return [(row, c) for c in range(col, col + size)]
    else:
        return [(r, col) for r in range(row, row + size)]
