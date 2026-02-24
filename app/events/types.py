from enum import Enum


class EventType(str, Enum):
    TEAM_JOINED = "team_joined"
    SHIP_PLACED = "ship_placed"
    BOMB_THROWN = "bomb_thrown"
    CODE_REDEEMED = "code_redeemed"
    LOCATION_ADDED = "location_added"
