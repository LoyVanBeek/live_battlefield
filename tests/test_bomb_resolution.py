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


class TestTorpedoBomb:
    def _torpedo_state(self) -> GameState:
        state = _started_state()
        state.teams["red"].special_ammo = {"torpedo": 1}
        return state

    def test_torpedo_sinks_full_ship_in_one_hit(self):
        state = self._torpedo_state()
        # Blue patrol boat has 2 cells; a single torpedo must sink it
        resolution = resolve_bomb(state, "red", "blue", "A1", bomb_type="torpedo")

        assert isinstance(resolution, BombApplied)
        assert resolution.hit is True
        assert resolution.sunk is True
        assert state.teams["blue"].ships[0].is_sunk() is True

    def test_torpedo_consumes_ammo_and_bomb(self):
        state = self._torpedo_state()
        resolution = resolve_bomb(state, "red", "blue", "A1", bomb_type="torpedo")

        assert isinstance(resolution, BombApplied)
        assert state.teams["red"].special_ammo["torpedo"] == 0
        assert state.teams["red"].bombs == 4  # 5 - 1

    def test_torpedo_without_ammo_rejected(self):
        state = _started_state()
        resolution = resolve_bomb(state, "red", "blue", "A1", bomb_type="torpedo")

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "no_special_ammo"
        assert state.teams["red"].bombs == 5  # unchanged

    def test_torpedo_miss_still_consumes_ammo(self):
        state = self._torpedo_state()
        resolution = resolve_bomb(state, "red", "blue", "J10", bomb_type="torpedo")

        assert isinstance(resolution, BombApplied)
        assert resolution.hit is False
        assert state.teams["red"].special_ammo["torpedo"] == 0

    def test_torpedo_replay_matches_live_state(self):
        from app.events.models import BombThrownEvent

        state = self._torpedo_state()
        live = _started_state()
        live.teams["red"].special_ammo = {"torpedo": 1}

        resolve_bomb(state, "red", "blue", "A1", bomb_type="torpedo")
        replayed = GameState(teams=dict(live.teams))
        event = BombThrownEvent(
            attacker_color="red", target_color="blue", row=0, col=0,
            bomb_type="torpedo",
        )
        replayed, updated = event.apply(replayed)

        assert replayed.teams["blue"].ships[0].is_sunk()
        assert replayed.teams["blue"].ships[0].hits == state.teams["blue"].ships[0].hits
        assert replayed.teams["red"].special_ammo["torpedo"] == 0
        assert replayed.teams["red"].bombs == 4
        assert updated.ship_sunk is True


class TestAnonymousBomb:
    def _anon_state(self) -> GameState:
        state = _started_state()
        state.teams["red"].special_ammo = {"anonymous_bomb": 1}
        return state

    def test_anon_hit_records_anon_as_attacker(self):
        state = self._anon_state()
        resolution = resolve_bomb(state, "red", "blue", "A1", bomb_type="anonymous_bomb")

        assert isinstance(resolution, BombApplied)
        assert resolution.hit is True
        # The victim's public board must not reveal the attacker color
        assert state.teams["blue"].public_board[0][0] == ("anon", True)

    def test_anon_miss_records_anon_as_attacker(self):
        state = self._anon_state()
        resolution = resolve_bomb(state, "red", "blue", "J10", bomb_type="anonymous_bomb")

        assert isinstance(resolution, BombApplied)
        assert state.teams["blue"].public_board[9][9] == ("anon", False)

    def test_anon_consumes_ammo(self):
        state = self._anon_state()
        resolve_bomb(state, "red", "blue", "A1", bomb_type="anonymous_bomb")
        assert state.teams["red"].special_ammo["anonymous_bomb"] == 0
        assert state.teams["red"].bombs == 4

    def test_anon_replay_records_anon(self):
        from app.events.models import BombThrownEvent

        replayed = GameState(teams=dict(self._anon_state().teams))
        event = BombThrownEvent(
            attacker_color="red", target_color="blue", row=0, col=0,
            bomb_type="anonymous_bomb",
        )
        replayed, _ = event.apply(replayed)

        assert replayed.teams["blue"].public_board[0][0] == ("anon", True)
        assert replayed.teams["red"].special_ammo["anonymous_bomb"] == 0

    def test_anon_board_png_renders_without_crash(self):
        state = self._anon_state()
        resolve_bomb(state, "red", "blue", "A1", bomb_type="anonymous_bomb")
        resolve_bomb(state, "red", "blue", "J10", bomb_type="anonymous_bomb")

        from app.game.board import render_board, boards_to_bytes

        img = render_board(state.teams["blue"], show_private=False)
        assert boards_to_bytes(img)  # gray fallback for unknown 'anon' color


class TestAreaBomb:
    def _area_state(self, radius: int = 1) -> GameState:
        state = _started_state()
        state.teams["red"].special_ammo = {"area_bomb": 1}
        state.teams["red"].bombs = 5
        return state

    def test_area_bomb_sinks_two_cell_ship_in_one_bomb(self):
        state = self._area_state()
        # Radius 1 around A1 (0,0) covers (0,0),(0,1),(1,0),(1,1) — the whole patrol boat
        resolution = resolve_bomb(
            state, "red", "blue", "A1", bomb_type="area_bomb", radius=1
        )

        assert isinstance(resolution, BombApplied)
        assert resolution.hit is True
        assert resolution.sunk is True
        assert state.teams["blue"].ships[0].is_sunk() is True

    def test_area_bomb_consumes_ammo_and_bomb_once(self):
        state = self._area_state()
        resolve_bomb(state, "red", "blue", "A1", bomb_type="area_bomb", radius=1)

        assert state.teams["red"].special_ammo["area_bomb"] == 0
        assert state.teams["red"].bombs == 4

    def test_area_bomb_skips_already_bombed_cells(self):
        state = self._area_state()
        state.teams["red"].special_ammo = {"area_bomb": 2}
        resolve_bomb(state, "red", "blue", "A1", bomb_type="area_bomb", radius=0)
        # (0,0) already bombed; radius 1 must not re-record it
        bombed_before = list(state.teams["blue"].bombed_cells)
        resolution = resolve_bomb(
            state, "red", "blue", "A1", bomb_type="area_bomb", radius=1
        )

        assert isinstance(resolution, BombApplied)
        assert state.teams["blue"].bombed_cells.count((0, 0)) == 1
        assert len(state.teams["blue"].bombed_cells) > len(bombed_before)

    def test_area_bomb_clamps_at_board_edges(self):
        state = self._area_state()
        # Red's own ship is at (9,0)-(9,1); bomb the far corner instead
        resolution = resolve_bomb(
            state, "red", "blue", "A1", bomb_type="area_bomb", radius=5
        )
        assert isinstance(resolution, BombApplied)
        assert state.teams["blue"].ships[0].is_sunk() is True

    def test_area_bomb_replay_matches_live(self):
        from app.events.models import BombThrownEvent

        state = self._area_state()
        live = _started_state()
        live.teams["red"].special_ammo = {"area_bomb": 1}

        resolve_bomb(state, "red", "blue", "A1", bomb_type="area_bomb", radius=1)
        replayed = GameState(teams=dict(live.teams))
        event = BombThrownEvent(
            attacker_color="red", target_color="blue", row=0, col=0,
            bomb_type="area_bomb", radius=1,
        )
        replayed, updated = event.apply(replayed)

        assert replayed.teams["blue"].ships[0].is_sunk()
        assert replayed.teams["blue"].bombed_cells == state.teams["blue"].bombed_cells
        assert replayed.teams["red"].special_ammo["area_bomb"] == 0
        assert replayed.teams["red"].bombs == 4
        assert updated.ship_sunk is True

    def test_area_bomb_without_ammo_rejected(self):
        state = _started_state()
        resolution = resolve_bomb(
            state, "red", "blue", "A1", bomb_type="area_bomb", radius=1
        )

        assert isinstance(resolution, BombRejected)
        assert resolution.error_key == "no_special_ammo"


class TestShieldBomb:
    def _shielded_state(self, minutes_ahead: int = 10) -> GameState:
        from datetime import datetime, timezone, timedelta

        state = _started_state()
        state.teams["red"].special_ammo = {"normal": 0}
        state.teams["blue"].shielded_until = datetime.now(timezone.utc) + timedelta(minutes=minutes_ahead)
        return state

    def test_shielded_hit_records_marker_without_damage(self):
        from datetime import datetime, timezone, timedelta

        state = _started_state()
        state.teams["blue"].shielded_until = datetime.now(timezone.utc) + timedelta(minutes=10)
        resolution = resolve_bomb(state, "red", "blue", "A1")

        assert isinstance(resolution, BombApplied)
        assert resolution.hit is True
        assert resolution.shielded is True
        assert resolution.sunk is False
        assert "shield absorbed" in resolution.message
        # Detected but undamaged and re-bombable
        assert state.teams["blue"].public_board[0][0] == ("red", True)
        assert (0, 0) not in state.teams["blue"].bombed_cells
        assert state.teams["blue"].ships[0].hits == 0
        assert state.teams["red"].bombs == 4  # bomb consumed

    def test_expired_shield_has_no_effect(self):
        from datetime import datetime, timezone, timedelta

        state = _started_state()
        state.teams["blue"].shielded_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        resolution = resolve_bomb(state, "red", "blue", "A1")

        assert isinstance(resolution, BombApplied)
        assert resolution.shielded is False
        assert resolution.hit is True
        assert (0, 0) in state.teams["blue"].bombed_cells

    def test_shielded_hit_replay_is_marker_only(self):
        from app.events.models import BombThrownEvent

        live = _started_state()
        replayed = GameState(teams=dict(live.teams))
        event = BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=0, shielded=True)
        replayed, updated = event.apply(replayed)

        assert updated.shielded is True
        assert replayed.teams["blue"].public_board[0][0] == ("red", True)
        assert (0, 0) not in replayed.teams["blue"].bombed_cells
        assert replayed.teams["blue"].ships[0].hits == 0
        assert replayed.teams["red"].bombs == 4

    def test_shielded_anon_bomb_records_anon(self):
        from datetime import datetime, timezone, timedelta
        from app.events.models import BombThrownEvent

        replayed = GameState(teams=dict(_started_state().teams))
        event = BombThrownEvent(
            attacker_color="red", target_color="blue", row=0, col=0,
            bomb_type="anonymous_bomb", shielded=True,
        )
        replayed, _ = event.apply(replayed)
        assert replayed.teams["blue"].public_board[0][0] == ("anon", True)
