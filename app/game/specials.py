"""Registry and configuration for game specials.

Each special declares its id and default settings here. The GM can enable
specials per game and override settings via the game-settings page; the
merged view (defaults + overrides) is what the rest of the code reads.

Only ids listed in SPECIALS are accepted when saving — unknown ids are
dropped so future clients can't write garbage into the config.
"""

from typing import Any

SPECIALS: dict[str, dict[str, Any]] = {
    "torpedo": {"enabled": False, "ammo_per_team": 2},
    "anonymous_bomb": {"enabled": False, "ammo_per_team": 2},
    "area_bomb": {"enabled": False, "ammo_per_team": 2, "size": 3},
    "armor": {"enabled": False, "minutes": 10, "ammo_per_team": 1},
    "deactivate": {"enabled": False, "minutes": 5, "ammo_per_team": 1},
    "radar_ship": {"enabled": False, "radius_cells": 3},
    "zombie_ship": {"enabled": False},
    "tsunami": {"enabled": False, "ships_destroyed": 1},
    "treasure_chest": {"enabled": False},
    "reward_per_sunk": {"enabled": False, "bombs": 2},
}

# Valid keys for a treasure chest's reward (per-chest contents set by the GM).
# Specials that are consumable bomb types (usable via the bomb command).
BOMB_TYPE_SPECIALS: tuple[str, ...] = ("torpedo", "anonymous_bomb", "area_bomb")

# Specials with consumable ammo the GM can grant (bomb types + defensive/utility).
GRANTABLE_SPECIALS: tuple[str, ...] = BOMB_TYPE_SPECIALS + ("armor", "deactivate")

# Valid keys for a treasure chest's reward (per-chest contents set by the GM).
CHEST_REWARD_KEYS: tuple[str, ...] = ("bombs",) + BOMB_TYPE_SPECIALS
CHEST_MAX_BOMBS = 20
CHEST_MAX_SPECIALS = 10


def filter_chest_reward(raw: Any) -> dict[str, int]:
    """Sanitize a chest reward dict: known keys only, sane bounds."""
    if not isinstance(raw, dict):
        return {}
    result: dict[str, int] = {}
    for key, value in raw.items():
        if key not in CHEST_REWARD_KEYS or not isinstance(value, int) or isinstance(value, bool):
            continue
        if value <= 0:
            continue
        result[key] = min(value, CHEST_MAX_BOMBS if key == "bombs" else CHEST_MAX_SPECIALS)
    return result

# Specials that are consumable bomb types (usable via the bomb command).
BOMB_TYPE_SPECIALS: tuple[str, ...] = ("torpedo", "anonymous_bomb", "area_bomb")

# Specials with consumable ammo the GM can grant (bomb types + defensive/utility).
GRANTABLE_SPECIALS: tuple[str, ...] = BOMB_TYPE_SPECIALS + ("armor", "deactivate")


async def grant_enabled_special_ammo(
    db, game_id, state, color: str, config: "SpecialsConfig"
) -> list[str]:
    """Grant +1 ammo of every enabled bomb-type special to a team.

    Called after a team earns a reward (location code, quiz answer). Each
    grant is persisted as its own SpecialAmmoGrantedEvent so replay stays
    authoritative. Returns the granted bomb types.
    """
    from app.events.models import SpecialAmmoGrantedEvent
    from app.events.saver import save_event

    granted: list[str] = []
    for bomb_type in BOMB_TYPE_SPECIALS:
        if config.is_enabled(bomb_type):
            await save_event(
                db,
                SpecialAmmoGrantedEvent(color=color, bomb_type=bomb_type, count=1),
                game_id=game_id,
            )
            granted.append(bomb_type)
    return granted


def filter_specials(raw: Any) -> dict[str, dict[str, Any]]:
    """Keep only known special ids and their known setting keys."""
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for special_id, overrides in raw.items():
        if special_id not in SPECIALS:
            continue
        if not isinstance(overrides, dict):
            continue
        defaults = SPECIALS[special_id]
        clean: dict[str, Any] = {}
        for key, value in overrides.items():
            if key in defaults:
                clean[key] = value
        result[special_id] = clean
    return result


class SpecialsConfig:
    """Merged view over the SPECIALS defaults and a game's stored overrides."""

    def __init__(self, overrides: dict[str, dict[str, Any]] | None = None) -> None:
        self._overrides = overrides or {}

    def settings(self, special_id: str) -> dict[str, Any]:
        """Merged defaults + overrides for one special ({} if unknown id)."""
        if special_id not in SPECIALS:
            return {}
        merged = dict(SPECIALS[special_id])
        merged.update(self._overrides.get(special_id, {}))
        return merged

    def is_enabled(self, special_id: str) -> bool:
        return bool(self.settings(special_id).get("enabled", False))

    def value(self, special_id: str, key: str, default: Any = None) -> Any:
        return self.settings(special_id).get(key, default)

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Merged config for every known special — safe to send to clients."""
        return {special_id: self.settings(special_id) for special_id in SPECIALS}
