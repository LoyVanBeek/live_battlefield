from dataclasses import dataclass, asdict
from typing import Optional
from app.events.types import EventType
from app.database import GameEvent


@dataclass
class TeamJoinedEvent:
    event_type: EventType = EventType.TEAM_JOINED
    name: str = ""
    color: str = ""
    chat_id: int = 0
    bombs: int = 0
    quick_action: Optional[str] = None
    count: Optional[int] = None

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.TEAM_JOINED,
            payload={
                "name": self.name,
                "color": self.color,
                "chat_id": self.chat_id,
                "bombs": self.bombs,
                "quick_action": self.quick_action,
                "count": self.count,
            },
            player_id=player_id,
        )


@dataclass
class ShipPlacedEvent:
    event_type: EventType = EventType.SHIP_PLACED
    color: str = ""
    ship_type: str = ""
    row: int = 0
    col: int = 0
    direction: str = ""
    quick_action: Optional[str] = None

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.SHIP_PLACED,
            payload={
                "color": self.color,
                "ship_type": self.ship_type,
                "row": self.row,
                "col": self.col,
                "direction": self.direction,
                "quick_action": self.quick_action,
            },
            player_id=player_id,
        )


@dataclass
class BombThrownEvent:
    event_type: EventType = EventType.BOMB_THROWN
    attacker_color: str = ""
    target_color: str = ""
    row: int = 0
    col: int = 0
    result: Optional[str] = None
    ship_type: Optional[str] = None
    ship_sunk: Optional[bool] = None

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.BOMB_THROWN,
            payload={
                "attacker_color": self.attacker_color,
                "target_color": self.target_color,
                "row": self.row,
                "col": self.col,
                "result": self.result,
                "ship_type": self.ship_type,
                "ship_sunk": self.ship_sunk,
            },
            player_id=player_id,
        )


@dataclass
class CodeRedeemedEvent:
    event_type: EventType = EventType.CODE_REDEEMED
    color: str = ""
    location_number: int = 0
    code: str = ""
    success: bool = True
    bombs_earned: int = 1

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.CODE_REDEEMED,
            payload={
                "color": self.color,
                "location_number": self.location_number,
                "code": self.code,
                "success": self.success,
                "bombs_earned": self.bombs_earned,
            },
            player_id=player_id,
        )


@dataclass
class LocationAddedEvent:
    event_type: EventType = EventType.LOCATION_ADDED
    number: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    code: str = ""
    bomb_value: int = 1

    def to_game_event(self, player_id: Optional[int] = None) -> GameEvent:
        return GameEvent(
            event_type=EventType.LOCATION_ADDED,
            payload={
                "number": self.number,
                "latitude": self.latitude,
                "longitude": self.longitude,
                "code": self.code,
                "bomb_value": self.bomb_value,
            },
            player_id=player_id,
        )
