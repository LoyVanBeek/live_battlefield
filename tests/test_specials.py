import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.events.models import (
    DeactivateTeamEvent,
    LocationAddedEvent,
    ShieldActivatedEvent,
    SpecialAmmoGrantedEvent,
    TeamJoinedEvent,
)
from app.game.specials import SPECIALS, SpecialsConfig, filter_specials, grant_enabled_special_ammo
from app.game.state import GameState, GameStatusField


class TestFilterSpecials:
    def test_drops_unknown_ids(self):
        result = filter_specials({"torpedo": {"enabled": True}, "warp_drive": {"enabled": True}})
        assert "torpedo" in result
        assert "warp_drive" not in result

    def test_drops_unknown_setting_keys(self):
        result = filter_specials({"torpedo": {"enabled": True, " explosions": 5}})
        assert result["torpedo"] == {"enabled": True}

    def test_drops_non_dict_values(self):
        assert filter_specials({"torpedo": "yes"}) == {}

    def test_drops_non_dict_input(self):
        assert filter_specials(None) == {}
        assert filter_specials("torpedo") == {}

    def test_keeps_empty_overrides(self):
        assert filter_specials({"torpedo": {}}) == {"torpedo": {}}


class TestSpecialsConfig:
    def test_defaults_when_no_overrides(self):
        config = SpecialsConfig(None)
        assert config.is_enabled("torpedo") is False
        assert config.value("torpedo", "ammo_per_team") == 2
        assert config.value("area_bomb", "size") == 3

    def test_overrides_merge_over_defaults(self):
        config = SpecialsConfig({"torpedo": {"enabled": True}})
        assert config.is_enabled("torpedo") is True
        assert config.value("torpedo", "ammo_per_team") == 2  # default kept

    def test_unknown_special_is_disabled(self):
        config = SpecialsConfig({"warp_drive": {"enabled": True}})
        assert config.is_enabled("warp_drive") is False
        assert config.settings("warp_drive") == {}

    def test_value_default_for_missing_key(self):
        config = SpecialsConfig(None)
        assert config.value("torpedo", "nonexistent", default=42) == 42

    def test_to_dict_covers_all_registered_specials(self):
        config = SpecialsConfig({"torpedo": {"enabled": True}})
        merged = config.to_dict()
        assert set(merged.keys()) == set(SPECIALS.keys())
        assert merged["torpedo"]["enabled"] is True
        assert merged["armor"]["enabled"] is False

    def test_registry_entries_have_enabled_flag(self):
        for special_id, defaults in SPECIALS.items():
            assert "enabled" in defaults, f"{special_id} missing 'enabled'"


class TestSpecialAmmoGrantedEvent:
    def test_apply_grants_ammo(self):
        state = GameState()
        state, _ = TeamJoinedEvent(name="Red", color="red", chat_id=1, bombs=3).apply(state)
        state, _ = SpecialAmmoGrantedEvent(color="red", bomb_type="torpedo", count=2).apply(state)
        assert state.teams["red"].special_ammo["torpedo"] == 2

        state, _ = SpecialAmmoGrantedEvent(color="red", bomb_type="torpedo", count=1).apply(state)
        assert state.teams["red"].special_ammo["torpedo"] == 3

    def test_apply_unknown_team_is_noop(self):
        state = GameState()
        new_state, event = SpecialAmmoGrantedEvent(color="green", bomb_type="torpedo").apply(state)
        assert event.success is False
        assert "green" not in new_state.teams

    def test_to_game_event_payload(self):
        event = SpecialAmmoGrantedEvent(color="red", bomb_type="area_bomb", count=2, success=True)
        game_event = event.to_game_event(game_id=None)
        assert game_event.event_type.value == "special_ammo_granted"
        assert game_event.payload == {
            "color": "red",
            "bomb_type": "area_bomb",
            "count": 2,
            "success": True,
        }

    def test_replay_via_factory(self):
        from app.events.factory import create_event

        db_event = MagicMock()
        db_event.event_type = "special_ammo_granted"
        db_event.payload = {"color": "red", "bomb_type": "torpedo", "count": 1, "success": True}
        db_event.player_id = None

        event = create_event(db_event)
        assert isinstance(event, SpecialAmmoGrantedEvent)

        state = GameState()
        state, _ = TeamJoinedEvent(name="Red", color="red", chat_id=1, bombs=3).apply(state)
        state, applied = event.apply(state)
        assert applied.success is True
        assert state.teams["red"].special_ammo["torpedo"] == 1

    def test_team_reset_clears_ammo(self):
        state = GameState()
        state, _ = TeamJoinedEvent(name="Red", color="red", chat_id=1, bombs=3).apply(state)
        state, _ = SpecialAmmoGrantedEvent(color="red", bomb_type="torpedo", count=2).apply(state)
        team = state.teams["red"]
        reset = team.with_reset()
        assert reset.special_ammo == {}


class TestGrantEnabledSpecialAmmo:
    @pytest.mark.asyncio
    async def test_grants_only_enabled_bomb_types(self):
        import uuid

        config = SpecialsConfig({"torpedo": {"enabled": True}, "area_bomb": {"enabled": True}})
        state = GameState()
        db = MagicMock()

        with patch("app.events.saver.save_event", new_callable=AsyncMock) as mock_save:
            granted = await grant_enabled_special_ammo(db, uuid.uuid4(), state, "red", config)

        assert granted == ["torpedo", "area_bomb"]
        assert mock_save.await_count == 2
        saved_event = mock_save.await_args_list[0].args[1] if mock_save.await_args_list[0].args else mock_save.await_args_list[0].kwargs["event"]
        assert isinstance(saved_event, SpecialAmmoGrantedEvent)
        assert saved_event.bomb_type == "torpedo"

    @pytest.mark.asyncio
    async def test_grants_nothing_when_disabled(self):
        import uuid

        config = SpecialsConfig(None)
        with patch("app.events.saver.save_event", new_callable=AsyncMock) as mock_save:
            granted = await grant_enabled_special_ammo(MagicMock(), uuid.uuid4(), GameState(), "red", config)

        assert granted == []
        mock_save.assert_not_awaited()


class TestFilterChestReward:
    def test_keeps_known_keys_within_bounds(self):
        from app.game.specials import filter_chest_reward

        reward = filter_chest_reward({"bombs": 3, "torpedo": 2, "area_bomb": 99})
        assert reward == {"bombs": 3, "torpedo": 2, "area_bomb": 10}

    def test_drops_unknown_keys_and_bad_values(self):
        from app.game.specials import filter_chest_reward

        reward = filter_chest_reward({"bombs": 1, "warp": 5, "torpedo": -2, "armor": True})
        assert reward == {"bombs": 1}

    def test_drops_non_dict(self):
        from app.game.specials import filter_chest_reward

        assert filter_chest_reward(None) == {}
        assert filter_chest_reward("bombs") == {}


class TestChestRedemption:
    def test_location_added_event_carries_kind_and_reward(self):
        state = GameState()
        event = LocationAddedEvent(
            number=1, latitude=52.0, longitude=4.0, code="ABC123",
            bomb_value=0, kind="chest", reward={"bombs": 2, "torpedo": 1},
        )
        state, _ = event.apply(state)
        assert state.location_codes[1] == "ABC123"

        game_event = event.to_game_event(game_id=None)
        assert game_event.payload["kind"] == "chest"
        assert game_event.payload["reward"] == {"bombs": 2, "torpedo": 1}

    def test_redeem_chest_grants_contents(self):
        import uuid
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField, TeamState
        from unittest.mock import AsyncMock

        state = GameState()
        state.status = GameStatusField.STARTED
        red = TeamState(name="Red", color="red", chat_id=1, bombs=0)
        state.teams = {"red": red}
        state.location_codes[1] = "ABC123"

        chest = MagicMock()
        chest.kind = "chest"
        chest.reward = {"bombs": 2, "torpedo": 1, "anonymous_bomb": 1}
        chest.bomb_value = 0

        game = MagicMock()
        game.specials = {}
        game.max_bombs = 100
        game.paused_until = None

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": "00000000-0000-0000-0000-000000000000", "color": "red"
        }
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_location_by_number", new_callable=AsyncMock, return_value=chest):
                        with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                            with patch("app.api.routes.save_event", new_callable=AsyncMock) as mock_save:
                                client = TestClient(app)
                                response = client.post(
                                    "/api/execute",
                                    json={
                                        "team_color": "red", "command": "code",
                                        "args": {"location_number": 1, "code": "ABC123"},
                                    },
                                )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Treasure chest opened" in data["message"]
        assert "+2 bombs" in data["message"]
        assert "+1 torpedo" in data["message"]

        # code event + 2 special ammo grants (torpedo + anonymous)
        assert mock_save.await_count == 3
        events_saved = [call.args[1] for call in mock_save.await_args_list]
        code_events = [e for e in events_saved if e.event_type.value == "code_redeemed"]
        ammo_events = [e for e in events_saved if e.event_type.value == "special_ammo_granted"]
        assert len(code_events) == 1
        assert code_events[0].bombs_earned == 2
        assert {e.bomb_type for e in ammo_events} == {"torpedo", "anonymous_bomb"}
        assert state.teams["red"].bombs == 2

    def test_redeem_quest_location_still_grants_normal_bombs(self):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField, TeamState
        from unittest.mock import AsyncMock

        state = GameState()
        state.status = GameStatusField.STARTED
        red = TeamState(name="Red", color="red", chat_id=1, bombs=0)
        state.teams = {"red": red}
        state.location_codes[1] = "ABC123"

        quest = MagicMock()
        quest.kind = None
        quest.reward = {}
        quest.bomb_value = 4

        game = MagicMock()
        game.specials = {}
        game.max_bombs = 100
        game.paused_until = None

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": "00000000-0000-0000-0000-000000000000", "color": "red"
        }
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_location_by_number", new_callable=AsyncMock, return_value=quest):
                        with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                            with patch("app.api.routes.save_event", new_callable=AsyncMock) as mock_save:
                                client = TestClient(app)
                                response = client.post(
                                    "/api/execute",
                                    json={
                                        "team_color": "red", "command": "code",
                                        "args": {"location_number": 1, "code": "ABC123"},
                                    },
                                )
        finally:
            app.dependency_overrides.clear()

        data = response.json()
        assert data["success"] is True
        assert "Code redeemed" in data["message"]
        assert mock_save.await_count == 1  # only the code event, no ammo grants
        assert state.teams["red"].bombs == 4


class TestCreateChest:
    @staticmethod
    def _mock_db():
        class MockSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def add(self, *args, **kwargs):
                pass

            async def commit(self):
                pass

            async def execute(self, *args, **kwargs):
                return MagicMock()

        return MockSession()

    def test_create_chest_requires_enabled_special(self):
        from app.api.routes import app, verify_gm_token, get_api_db
        from app.game.state import GameState
        from unittest.mock import AsyncMock

        game = MagicMock()
        game.specials = {}

        async def override_get_db():
            yield self._mock_db()

        app.dependency_overrides[get_api_db] = override_get_db

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            with patch("app.api.routes.GameState.from_events", return_value=GameState()):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game_locations", new_callable=AsyncMock, return_value=[]):
                        with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                            client = TestClient(app)
                            response = client.post(
                                "/api/quick/create_locations",
                                json={"latitude": 52.0, "longitude": 4.0, "count": 1, "kind": "chest", "reward": {"bombs": 2}},
                            )
        finally:
            app.dependency_overrides.clear()

        data = response.json()
        assert data["success"] is False
        assert "not enabled" in data["message"]

    def test_create_chest_with_reward(self):
        from app.api.routes import app, verify_gm_token, get_api_db
        from app.game.state import GameState
        from unittest.mock import AsyncMock

        game = MagicMock()
        game.specials = {"treasure_chest": {"enabled": True}}

        async def override_get_db():
            yield self._mock_db()

        app.dependency_overrides[get_api_db] = override_get_db

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            with patch("app.api.routes.GameState.from_events", return_value=GameState()):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game_locations", new_callable=AsyncMock, return_value=[]):
                        with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                            with patch("app.models.get_next_location_number", new_callable=AsyncMock, return_value=1):
                                with patch("app.api.routes.save_event", new_callable=AsyncMock) as mock_save:
                                    client = TestClient(app)
                                    response = client.post(
                                        "/api/quick/create_locations",
                                        json={
                                            "latitude": 52.0, "longitude": 4.0, "count": 1,
                                            "kind": "chest", "reward": {"bombs": 2, "torpedo": 1},
                                        },
                                    )
        finally:
            app.dependency_overrides.clear()

        data = response.json()
        assert data["success"] is True
        assert data["locations"][0]["kind"] == "chest"
        assert data["locations"][0]["reward"] == {"bombs": 2, "torpedo": 1}
        saved_event = mock_save.await_args_list[0].args[1]
        assert saved_event.kind == "chest"
        assert saved_event.reward == {"bombs": 2, "torpedo": 1}

    def test_create_chest_without_reward_rejected(self):
        from app.api.routes import app, verify_gm_token, get_api_db
        from app.game.state import GameState
        from unittest.mock import AsyncMock

        game = MagicMock()
        game.specials = {"treasure_chest": {"enabled": True}}

        async def override_get_db():
            yield self._mock_db()

        app.dependency_overrides[get_api_db] = override_get_db

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            with patch("app.api.routes.GameState.from_events", return_value=GameState()):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game_locations", new_callable=AsyncMock, return_value=[]):
                        with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                            client = TestClient(app)
                            response = client.post(
                                "/api/quick/create_locations",
                                json={"latitude": 52.0, "longitude": 4.0, "count": 1, "kind": "chest", "reward": {}},
                            )
        finally:
            app.dependency_overrides.clear()

        data = response.json()
        assert data["success"] is False
        assert "needs a reward" in data["message"]


class TestShieldActivatedEvent:
    def test_apply_sets_shield_and_consumes_ammo(self):
        from datetime import datetime, timezone, timedelta

        state = GameState()
        state, _ = TeamJoinedEvent(name="Red", color="red", chat_id=1, bombs=3).apply(state)
        state, _ = SpecialAmmoGrantedEvent(color="red", bomb_type="armor", count=1).apply(state)

        until = datetime.now(timezone.utc) + timedelta(minutes=10)
        event = ShieldActivatedEvent(color="red", until=until.isoformat(), success=True)
        state, applied = event.apply(state)

        assert applied.success is True
        assert state.teams["red"].special_ammo["armor"] == 0
        assert state.teams["red"].shielded_until is not None
        assert state.teams["red"].is_shielded(datetime.now(timezone.utc)) is True

    def test_apply_unknown_team_noop(self):
        event = ShieldActivatedEvent(color="green", until=None, success=True)
        state = GameState()
        new_state, applied = event.apply(state)
        assert applied.success is False

    def test_to_game_event_payload(self):
        event = ShieldActivatedEvent(color="red", until="2026-09-08T12:00:00+00:00", success=True)
        game_event = event.to_game_event(game_id=None)
        assert game_event.event_type.value == "shield_activated"
        assert game_event.payload["until"] == "2026-09-08T12:00:00+00:00"


class TestShieldCommand:
    def _post_shield(self, specials, ammo=1, already_shielded=False):
        import uuid
        from datetime import datetime, timezone, timedelta
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField, TeamState

        state = GameState()
        state.status = GameStatusField.STARTED
        red = TeamState(name="Red", color="red", chat_id=1, bombs=5)
        red.special_ammo = {"armor": ammo}
        if already_shielded:
            red.shielded_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        state.teams = {"red": red}

        game = MagicMock()
        game.specials = specials
        game.paused_until = None

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": "00000000-0000-0000-0000-000000000000", "color": "red"
        }
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                        with patch("app.api.routes.save_event", new_callable=AsyncMock) as mock_save:
                            with patch("app.api.routes._check_game_paused", new_callable=AsyncMock, return_value=None):
                                client = TestClient(app)
                                response = client.post(
                                    "/api/execute",
                                    json={"team_color": "red", "command": "shield", "args": {}},
                                )
        finally:
            app.dependency_overrides.clear()
        return response, mock_save, state

    def test_activate_shield_success(self):
        response, mock_save, state = self._post_shield({"armor": {"enabled": True, "minutes": 10}})
        data = response.json()
        assert data["success"] is True
        assert "Shield active" in data["message"]
        assert mock_save.await_count == 1
        assert state.teams["red"].special_ammo["armor"] == 0
        assert state.teams["red"].shielded_until is not None

    def test_activate_shield_disabled_rejected(self):
        response, mock_save, _ = self._post_shield({"armor": {"enabled": False}})
        assert response.json()["error_key"] == "special_disabled"

    def test_activate_shield_without_ammo_rejected(self):
        response, mock_save, _ = self._post_shield({"armor": {"enabled": True}}, ammo=0)
        assert response.json()["error_key"] == "no_special_ammo"

    def test_activate_shield_twice_rejected(self):
        response, mock_save, _ = self._post_shield(
            {"armor": {"enabled": True, "minutes": 10}}, ammo=2, already_shielded=True
        )
        assert response.json()["success"] is False
        assert "already active" in response.json()["message"]


class TestDeactivateTeamEvent:
    def test_apply_deactivates_target_and_consumes_actor_ammo(self):
        from datetime import datetime, timezone, timedelta

        state = GameState()
        state, _ = TeamJoinedEvent(name="Red", color="red", chat_id=1, bombs=3).apply(state)
        state, _ = TeamJoinedEvent(name="Blue", color="blue", chat_id=2, bombs=3).apply(state)
        state, _ = SpecialAmmoGrantedEvent(color="red", bomb_type="deactivate", count=1).apply(state)

        until = datetime.now(timezone.utc) + timedelta(minutes=5)
        event = DeactivateTeamEvent(color="blue", by_color="red", until=until.isoformat(), success=True)
        state, applied = event.apply(state)

        assert applied.success is True
        assert state.teams["blue"].is_deactivated(datetime.now(timezone.utc)) is True
        assert state.teams["red"].special_ammo["deactivate"] == 0

    def test_apply_gm_deactivation_has_no_actor(self):
        from datetime import datetime, timezone, timedelta

        state = GameState()
        state, _ = TeamJoinedEvent(name="Blue", color="blue", chat_id=2, bombs=3).apply(state)

        until = datetime.now(timezone.utc) + timedelta(minutes=5)
        event = DeactivateTeamEvent(color="blue", by_color=None, until=until.isoformat(), success=True)
        state, applied = event.apply(state)

        assert applied.success is True
        assert state.teams["blue"].is_deactivated(datetime.now(timezone.utc)) is True

    def test_expired_deactivation_allows_actions(self):
        from datetime import datetime, timezone, timedelta

        state = GameState()
        state, _ = TeamJoinedEvent(name="Blue", color="blue", chat_id=2, bombs=3).apply(state)
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        state.teams["blue"] = state.teams["blue"].with_deactivation(past)
        assert state.teams["blue"].is_deactivated(datetime.now(timezone.utc)) is False


class TestDeactivateCommand:
    def _setup(self, ammo=1, enabled=True):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField, TeamState

        state = GameState()
        state.status = GameStatusField.STARTED
        red = TeamState(name="Red", color="red", chat_id=1, bombs=5)
        red.special_ammo = {"deactivate": ammo}
        blue = TeamState(name="Blue", color="blue", chat_id=2, bombs=1)
        state.teams = {"red": red, "blue": blue}

        game = MagicMock()
        game.specials = {"deactivate": {"enabled": enabled, "minutes": 5}}
        game.paused_until = None

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": "00000000-0000-0000-0000-000000000000", "color": "red"
        }
        return app, state, game

    def test_deactivate_success(self):
        app, state, game = self._setup()
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                        with patch("app.api.routes.save_event", new_callable=AsyncMock) as mock_save:
                            with patch("app.api.routes._check_game_paused", new_callable=AsyncMock, return_value=None):
                                client = TestClient(app)
                                response = client.post(
                                    "/api/execute",
                                    json={
                                        "team_color": "red", "command": "deactivate",
                                        "args": {"target": "blue"},
                                    },
                                )
        finally:
            app.dependency_overrides.clear()

        data = response.json()
        assert data["success"] is True
        assert "deactivated for 5 minutes" in data["message"]
        assert state.teams["red"].special_ammo["deactivate"] == 0
        assert state.teams["blue"].is_deactivated(__import__("datetime").datetime.now(__import__("datetime").timezone.utc)) is True
        saved_event = mock_save.await_args_list[0].args[1]
        assert saved_event.event_type.value == "team_deactivated"
        assert saved_event.by_color == "red"

    def test_deactivate_disabled_rejected(self):
        app, state, game = self._setup(enabled=False)
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                        client = TestClient(app)
                        response = client.post(
                            "/api/execute",
                            json={
                                "team_color": "red", "command": "deactivate",
                                "args": {"target": "blue"},
                            },
                        )
        finally:
            app.dependency_overrides.clear()

        assert response.json()["error_key"] == "special_disabled"

    def test_deactivated_team_cannot_bomb(self):
        import uuid
        from datetime import datetime, timezone, timedelta
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField, TeamState

        state = GameState()
        state.status = GameStatusField.STARTED
        red = TeamState(name="Red", color="red", chat_id=1, bombs=5)
        red.deactivated_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        blue = TeamState(name="Blue", color="blue", chat_id=2, bombs=1)
        state.teams = {"red": red, "blue": blue}

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": "00000000-0000-0000-0000-000000000000", "color": "red"
        }
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.api.routes._check_game_paused", new_callable=AsyncMock, return_value=None):
                        client = TestClient(app)
                        response = client.post(
                            "/api/execute",
                            json={
                                "team_color": "red", "command": "bomb",
                                "args": {"target": "blue", "coordinate": "A1"},
                            },
                        )
        finally:
            app.dependency_overrides.clear()

        data = response.json()
        assert data["success"] is False
        assert data["error_key"] == "team_deactivated"

    def test_gm_can_deactivate_team(self):
        from app.api.routes import app, verify_gm_token
        from app.game.state import GameState, GameStatusField, TeamState
        from datetime import datetime, timezone

        state = GameState()
        state.status = GameStatusField.STARTED
        blue = TeamState(name="Blue", color="blue", chat_id=2, bombs=1)
        state.teams = {"blue": blue}

        app.dependency_overrides[verify_gm_token] = lambda: "00000000-0000-0000-0000-000000000000"
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.api.routes.save_event", new_callable=AsyncMock) as mock_save:
                        client = TestClient(app)
                        response = client.post(
                            "/api/quick/deactivate_team",
                            json={"team_color": "blue", "minutes": 7},
                        )
        finally:
            app.dependency_overrides.clear()

        data = response.json()
        assert data["success"] is True
        assert state.teams["blue"].is_deactivated(datetime.now(timezone.utc)) is True
        saved_event = mock_save.await_args_list[0].args[1]
        assert saved_event.by_color is None


class TestAssignTrait:
    def _setup(self, trait="radar", enabled=True):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField, TeamState, Ship

        state = GameState()
        state.status = GameStatusField.STARTED
        red = TeamState(name="Red", color="red", chat_id=1, bombs=5)
        red.ships.append(Ship(ship_type="battleship", cells=[(5, 5), (5, 6), (5, 7), (5, 8)]))
        blue = TeamState(name="Blue", color="blue", chat_id=2, bombs=1)
        state.teams = {"red": red, "blue": blue}

        game = MagicMock()
        game.specials = {f"{trait}_ship": {"enabled": enabled}}
        game.paused_until = None

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": "00000000-0000-0000-0000-000000000000", "color": "red"
        }
        return app, state, game

    def _post(self, app, trait="radar", ship_type="battleship"):
        with patch("app.api.routes.GameState.from_events") as mock_from_events:
            # retrieve state from the patch closure is not possible; use module-level holder
            pass
        # placeholder replaced below

    def test_assign_radar_trait_success(self):
        from app.api.routes import app
        from unittest.mock import AsyncMock

        app_ref, state, game = self._setup()
        captured = {}
        original = state

        try:
            with patch("app.api.routes.GameState.from_events", return_value=state) as mf:
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                        with patch("app.api.routes.save_event", new_callable=AsyncMock) as mock_save:
                            with patch("app.api.routes._check_game_paused", new_callable=AsyncMock, return_value=None):
                                client = TestClient(app_ref)
                                response = client.post(
                                    "/api/execute",
                                    json={
                                        "team_color": "red", "command": "assign_trait",
                                        "args": {"trait": "radar", "ship_type": "battleship"},
                                    },
                                )
                                captured["state"] = mf.return_value
        finally:
            app.dependency_overrides.clear()

        data = response.json()
        assert data["success"] is True
        assert "radar ship" in data["message"]
        assert mock_save.await_count == 1
        saved_event = mock_save.await_args_list[0].args[1]
        assert saved_event.event_type.value == "trait_assigned"
        # live state mutated: first battleship carries the radar trait
        assert state.teams["red"].ships[0].has_trait("radar") is True

    def test_assign_trait_disabled_rejected(self):
        from app.api.routes import app
        from unittest.mock import AsyncMock

        app_ref, state, game = self._setup(enabled=False)
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                        client = TestClient(app_ref)
                        response = client.post(
                            "/api/execute",
                            json={
                                "team_color": "red", "command": "assign_trait",
                                "args": {"trait": "radar", "ship_type": "battleship"},
                            },
                        )
        finally:
            app.dependency_overrides.clear()

        assert response.json()["error_key"] == "special_disabled"

    def test_assign_same_trait_twice_rejected(self):
        from app.api.routes import app
        from unittest.mock import AsyncMock

        app_ref, state, game = self._setup()
        try:
            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                    with patch("app.models.get_game", new_callable=AsyncMock, return_value=game):
                        with patch("app.api.routes.save_event", new_callable=AsyncMock):
                            with patch("app.api.routes._check_game_paused", new_callable=AsyncMock, return_value=None):
                                client = TestClient(app_ref)
                                first = client.post(
                                    "/api/execute",
                                    json={
                                        "team_color": "red", "command": "assign_trait",
                                        "args": {"trait": "radar", "ship_type": "battleship"},
                                    },
                                )
                                second = client.post(
                                    "/api/execute",
                                    json={
                                        "team_color": "red", "command": "assign_trait",
                                        "args": {"trait": "radar", "ship_type": "patrol_boat"},
                                    },
                                )
        finally:
            app.dependency_overrides.clear()

        assert first.json()["success"] is True
        assert second.json()["success"] is False
        assert "already have" in second.json()["message"]


class TestTsunami:
    def _tsunami_state(self):
        from app.game.state import GameState, TeamState, Ship

        state = GameState()
        state.status = GameStatusField.STARTED
        red = TeamState(name="Red", color="red", chat_id=1, bombs=5)
        red.ships.append(Ship(ship_type="patrol_boat", cells=[(0, 0), (0, 1)]))
        blue = TeamState(name="Blue", color="blue", chat_id=2, bombs=1)
        blue.ships.append(Ship(ship_type="battleship", cells=[(5, 5), (5, 6), (5, 7), (5, 8)]))
        state.teams = {"red": red, "blue": blue}
        return state

    def test_pick_victims_returns_distinct_alive_ships(self):
        from app.services.tsunami import pick_tsunami_victims

        state = self._tsunami_state()
        victims = pick_tsunami_victims(state, 5)
        assert len(victims) == 2  # only 2 alive ships exist
        keys = {(v["color"], v["ship_type"]) for v in victims}
        assert len(keys) == len(victims)

    def test_event_apply_sinks_ships(self):
        from app.events.models import TsunamiEvent

        state = self._tsunami_state()
        event = TsunamiEvent(
            destroyed=[
                {"color": "red", "ship_type": "patrol_boat", "cells": [[0, 0], [0, 1]]},
            ],
            success=True,
        )
        state, applied = event.apply(state)
        assert applied.success is True
        assert state.teams["red"].ships[0].is_sunk() is True
        assert state.teams["blue"].ships[0].is_sunk() is False

    def test_tsunami_revives_zombie_ship(self):
        from app.events.models import TsunamiEvent
        from app.game.state import Ship

        state = self._tsunami_state()
        state.teams["red"].ships[0] = Ship(
            ship_type="patrol_boat", cells=[(0, 0), (0, 1)], traits=["zombie"]
        )
        event = TsunamiEvent(
            destroyed=[
                {"color": "red", "ship_type": "patrol_boat", "cells": [[0, 0], [0, 1]]},
            ],
            success=True,
        )
        state, _ = event.apply(state)
        ship = state.teams["red"].ships[0]
        assert ship.revived is True
        assert ship.is_sunk() is False

    def test_trigger_endpoint_washes_ships_away(self):
        from app.api.routes import app, verify_gm_token
        from app.services.tsunami import trigger_tsunami_for_game
        from app.game.specials import SpecialsConfig
        from unittest.mock import AsyncMock

        state = self._tsunami_state()
        game = MagicMock()
        game.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        game.status.value = "started"
        game.specials = {"tsunami": {"enabled": True, "ships_destroyed": 1}}
        game.last_tsunami_at = None

        config = SpecialsConfig(game.specials)

        with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
            with patch("app.services.tsunami.GameState") as mock_gs:
                mock_gs.from_events.return_value = state
                with patch("app.services.tsunami.save_event", new_callable=AsyncMock) as mock_save:
                    import asyncio
                    result = asyncio.run(trigger_tsunami_for_game(AsyncMock(), game, config))

        assert result["success"] is True
        assert "Tsunami" in result["message"]
        assert len(result["destroyed"]) == 1
        assert mock_save.await_count == 1
        # exactly one ship sunk on the live state
        sunk = [
            (color, s.ship_type)
            for color, team in state.teams.items()
            for s in team.ships if s.is_sunk()
        ]
        assert len(sunk) == 1
        assert game.last_tsunami_at is not None

    def test_trigger_endpoint_disabled_rejected(self):
        from app.services.tsunami import trigger_tsunami_for_game
        from app.game.specials import SpecialsConfig
        from unittest.mock import AsyncMock

        game = MagicMock()
        game.status.value = "started"
        game.specials = {}
        config = SpecialsConfig(game.specials)
        import asyncio
        result = asyncio.run(trigger_tsunami_for_game(AsyncMock(), game, config))
        assert result["success"] is False
        assert "not enabled" in result["message"]

    def test_trigger_endpoint_requires_started_game(self):
        from app.services.tsunami import trigger_tsunami_for_game
        from app.game.specials import SpecialsConfig
        from unittest.mock import AsyncMock

        game = MagicMock()
        game.status.value = "preparing"
        game.specials = {"tsunami": {"enabled": True}}
        config = SpecialsConfig(game.specials)
        import asyncio
        result = asyncio.run(trigger_tsunami_for_game(AsyncMock(), game, config))
        assert result["success"] is False
        assert "during a game" in result["message"]

    def test_replay_deterministic(self):
        from app.services.tsunami import pick_tsunami_victims, apply_tsunami_live
        from app.events.models import TsunamiEvent

        state = self._tsunami_state()
        destroyed = pick_tsunami_victims(state, 2)
        descriptions = apply_tsunami_live(state, destroyed)

        replayed = self._tsunami_state()
        event = TsunamiEvent(destroyed=destroyed, success=True)
        replayed, _ = event.apply(replayed)

        for team_color in ("red", "blue"):
            for live_ship, replay_ship in zip(
                state.teams[team_color].ships, replayed.teams[team_color].ships
            ):
                assert live_ship.is_sunk() == replay_ship.is_sunk()
                assert live_ship.hits == replay_ship.hits
