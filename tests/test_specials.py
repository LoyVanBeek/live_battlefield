from app.game.specials import SPECIALS, SpecialsConfig, filter_specials


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
