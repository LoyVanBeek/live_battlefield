from app.game.state import (
    GameState,
    GameStatusField,
    TeamState,
    Ship,
    resolve_bomb,
    BombApplied,
    BombRejected,
)


def _started_state(red_bombs: int = 5) -> GameState:
    state = GameState()
    state.status = GameStatusField.STARTED
    red = TeamState(name="Red Team", color="red", chat_id=1, bombs=red_bombs)
    red.ships.append(Ship(ship_type="patrol_boat", cells=[(9, 0), (9, 1)]))
    blue = TeamState(name="Blue Team", color="blue", chat_id=2, bombs=3)
    blue.ships.append(Ship(ship_type="patrol_boat", cells=[(0, 0), (0, 1)]))
    state.teams = {"red": red, "blue": blue}
    return state


class TestResolveBombSuccess:
    def test_hit_fields_and_state_mutation(self):
        state = _started_state()
        resolution = resolve_bomb(state, "red", "blue", "A1")

        assert isinstance(resolution, BombApplied)
        assert resolution.hit is True
        assert resolution.sunk is False
        assert resolution.ship_type == "patrol_boat"
        assert resolution.target_name == "Blue Team"
        assert resolution.coord == "A1"
        assert resolution.bombs_left == 4
        assert resolution.row == 0 and resolution.col == 0
        assert "HIT at A1!" in resolution.message
        assert "Bombs left: 4" in resolution.message

        assert state.teams["red"].bombs == 4
        assert (0, 0) in state.teams["blue"].bombed_cells
        assert state.teams["blue"].public_board[0][0] == ("red", True)

    def test_miss_fields(self):
        state = _started_state()
        resolution = resolve_bomb(state, "red", "blue", "J10")

        assert isinstance(resolution, BombApplied)
        assert resolution.hit is False
        assert resolution.ship is None
        assert "MISS at J10!" in resolution.message

    def test_sunk_ship_detected(self):
        state = _started_state()
        resolve_bomb(state, "red", "blue", "A1")
        resolution = resolve_bomb(state, "red", "blue", "B1")

        assert isinstance(resolution, BombApplied)
        assert resolution.sunk is True
        assert "Sunk patrol_boat!" in resolution.message

    def test_winner_returned_when_last_team_destroyed(self):
        state = _started_state()
        resolve_bomb(state, "red", "blue", "A1")
        resolution = resolve_bomb(state, "red", "blue", "B1")

        assert isinstance(resolution, BombApplied)
        assert resolution.winner is not None
        assert resolution.winner.color == "red"

    def test_no_winner_while_multiple_teams_alive(self):
        state = _started_state()
        resolution = resolve_bomb(state, "red", "blue", "A1")
        assert isinstance(resolution, BombApplied)
        assert resolution.winner is None


class TestResolveBombRejections:
    def test_not_started(self):
        state = _started_state()
        state.status = GameStatusField.PREPARING
        resolution = resolve_bomb(state, "red", "blue", "A1")

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "game_not_started"

    def test_attacker_missing(self):
        state = _started_state()
        resolution = resolve_bomb(state, "green", "blue", "A1")

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "team_doesnt_exist"
        assert resolution.color == "green"

    def test_target_missing(self):
        state = _started_state()
        resolution = resolve_bomb(state, "red", "green", "A1")

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "target_doesnt_exist"
        assert resolution.color == "green"

    def test_no_bombs(self):
        state = _started_state(red_bombs=0)
        resolution = resolve_bomb(state, "red", "blue", "A1")

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "no_bombs"
        assert state.teams["blue"].bombed_cells == []

    def test_invalid_coord(self):
        state = _started_state()
        resolution = resolve_bomb(state, "red", "blue", "Z99")

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "invalid_coord"
        assert resolution.message  # carries the parse error text

    def test_target_destroyed(self):
        state = _started_state()
        state.teams["blue"].ships[0].hits = 2  # fully sunk
        resolution = resolve_bomb(state, "red", "blue", "C3")

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "target_destroyed"
        assert resolution.color == "blue"

    def test_already_bombed(self):
        state = _started_state()
        resolve_bomb(state, "red", "blue", "A1")
        resolution = resolve_bomb(state, "red", "blue", "A1")

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "already_bombed"
        assert resolution.coord == "A1"

    def test_self_bomb_allowed_by_default(self):
        state = _started_state()
        resolution = resolve_bomb(state, "blue", "blue", "A1")

        assert isinstance(resolution, BombApplied)
        assert state.teams["blue"].bombs == 2  # 3 - 1

    def test_self_bomb_rejected_when_disallowed(self):
        state = _started_state()
        resolution = resolve_bomb(
            state, "blue", "blue", "A1", allow_self_bomb=False
        )

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "self_bomb"
        assert "cannot bomb yourself" in resolution.message.lower()
        assert state.teams["blue"].bombs == 3  # unchanged
