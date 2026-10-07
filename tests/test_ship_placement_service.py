"""Tests for auto-placement draws (app/services/ship_placement.py).

The service itself needs a database session, so these target the draw logic it
delegates to: one greedy draw per board, redrawn when a draw dead-ends instead
of failing the whole call.
"""

from app.game.ships import SHIP_COUNTS
from app.game.state import Ship, TeamState
from app.services import ship_placement
from app.services.ship_placement import find_placements

ALL_SHIPS = [
    ship_type for ship_type, count in SHIP_COUNTS.items() for _ in range(count)
]


def _fresh_team() -> TeamState:
    return TeamState(name="Test", color="red", chat_id=123)


def test_draw_places_every_ship_and_leaves_the_team_untouched():
    team = _fresh_team()

    placements = find_placements(team, ALL_SHIPS)

    assert placements is not None
    assert len(placements) == len(ALL_SHIPS)

    # the draw works on a private copy — the team itself stays untouched
    assert team.ships == []
    assert team.placed_ship_types == {}

    # and every returned placement is legal when replayed on a clean board
    board = _fresh_team()
    for ship_type, row, col, direction in placements:
        placed, board = board.place_ship(ship_type, row, col, direction)
        assert placed, f"{ship_type} at {row},{col} {direction} does not fit"
    assert board.has_all_ships()


def test_a_dead_end_draw_is_redrawn_instead_of_failing(monkeypatch):
    team = _fresh_team()
    surviving_draw = [("patrol_boat", 0, 0, "horizontal")]
    draws = [None, surviving_draw]
    seen: list[TeamState] = []

    def fake_draw(board, ships_to_place):
        seen.append(board)
        return draws.pop(0)

    monkeypatch.setattr(ship_placement, "_draw_placements", fake_draw)

    assert find_placements(team, ALL_SHIPS) == surviving_draw
    assert len(seen) == 2  # one dead end -> one redraw, not a failure


def test_gives_up_after_max_board_draws(monkeypatch):
    team = _fresh_team()
    calls = []

    def always_dead(board, ships_to_place):
        calls.append(1)
        return None

    monkeypatch.setattr(ship_placement, "_draw_placements", always_dead)
    monkeypatch.setattr(ship_placement, "MAX_BOARD_DRAWS", 3)

    assert find_placements(team, ALL_SHIPS) is None
    assert len(calls) == 3  # bounded: no unbounded retry loop


def test_unfillable_board_returns_none(monkeypatch):
    """A real dead end: every cell of the board is already occupied."""
    monkeypatch.setattr(ship_placement, "MAX_BOARD_DRAWS", 2)
    monkeypatch.setattr(ship_placement, "ATTEMPTS_PER_SHIP", 5)

    team = _fresh_team()
    team.ships = [
        Ship(
            ship_type="airplane_carrier",
            cells=[(row, col) for row in range(10) for col in range(10)],
        )
    ]

    assert find_placements(team, ALL_SHIPS) is None
