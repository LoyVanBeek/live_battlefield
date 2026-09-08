import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.events.models import SpecialAmmoGrantedEvent, TeamJoinedEvent
from app.game.specials import SPECIALS, SpecialsConfig, filter_specials, grant_enabled_special_ammo
from app.game.state import GameState


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
