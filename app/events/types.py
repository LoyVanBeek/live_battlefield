from enum import Enum


class EventType(str, Enum):
    TEAM_JOINED = "team_joined"
    SHIP_PLACED = "ship_placed"
    SHIP_REMOVED = "ship_removed"
    BOMB_THROWN = "bomb_thrown"
    CODE_REDEEMED = "code_redeemed"
    LOCATION_ADDED = "location_added"
    BOMBS_ADDED = "bombs_added"
    TEAM_RESET = "team_reset"
    GAME_STARTED = "game_started"
    GAME_ENDED = "game_ended"
