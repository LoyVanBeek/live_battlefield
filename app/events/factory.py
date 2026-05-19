from typing import Optional, Union
from app.events.types import EventType
from app.events.models import AnyEvent
from app.events.models import (
    TeamJoinedEvent,
    ShipPlacedEvent,
    ShipRemovedEvent,
    BombThrownEvent,
    CodeRedeemedEvent,
    LocationAddedEvent,
    LocationRemovedEvent,
    BombsAddedEvent,
    TeamResetEvent,
    GameStartedEvent,
    GameEndedEvent,
)


def _get_event_type_value(event_type: Union[EventType, str]) -> str:
    if isinstance(event_type, EventType):
        return event_type.value
    return event_type


def create_event(db_event) -> Optional[AnyEvent]:
    event_type = db_event.event_type
    payload_dict = db_event.payload
    player_id = getattr(db_event, "player_id", None)

    event_type_value = _get_event_type_value(event_type)

    if event_type_value == "team_joined":
        return TeamJoinedEvent(**payload_dict)

    elif event_type_value == "ship_placed":
        return ShipPlacedEvent(**payload_dict)

    elif event_type_value == "ship_removed":
        return ShipRemovedEvent(**payload_dict)

    elif event_type_value == "bomb_thrown":
        return BombThrownEvent(**payload_dict)

    elif event_type_value == "code_redeemed":
        return CodeRedeemedEvent(**payload_dict)

    elif event_type_value == "location_added":
        return LocationAddedEvent(**payload_dict)

    elif event_type_value == "location_removed":
        return LocationRemovedEvent(**payload_dict)

    elif event_type_value == "bombs_added":
        return BombsAddedEvent(**payload_dict)

    elif event_type_value == "team_reset":
        return TeamResetEvent(**payload_dict)

    elif event_type_value == "game_started":
        return GameStartedEvent(**payload_dict)

    elif event_type_value == "game_ended":
        return GameEndedEvent(**payload_dict)

    return None


def create_events(db_events: list) -> list[AnyEvent]:
    events: list[AnyEvent] = []
    for db_event in db_events:
        event = create_event(db_event)
        if event:
            events.append(event)
    return events
