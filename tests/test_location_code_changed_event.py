from app.database import GameEvent
from app.events.factory import create_event
from app.events.models import (
    LocationAddedEvent,
    LocationCodeChangedEvent,
)
from app.events.types import EventType
from app.game.state import GameState


def make_state(*locations: tuple[int, str]) -> GameState:
    state = GameState()
    for number, code in locations:
        state, _ = LocationAddedEvent(
            number=number, latitude=52.0, longitude=5.0, code=code
        ).apply(state)
    return state


class TestLocationCodeChangedEvent:
    def test_apply_updates_existing_code(self):
        state = make_state((1, "OLD111"), (2, "CODE2"))

        new_state, _ = LocationCodeChangedEvent(number=1, code="NEW222").apply(state)

        assert new_state.location_codes == {1: "NEW222", 2: "CODE2"}
        # original state untouched (immutable replace)
        assert state.location_codes == {1: "OLD111", 2: "CODE2"}

    def test_apply_unknown_location_is_noop(self):
        state = make_state((1, "CODE1"))

        new_state, _ = LocationCodeChangedEvent(number=99, code="NOPE").apply(state)

        # must not create phantom entries (would skew can_start counting)
        assert new_state.location_codes == {1: "CODE1"}

    def test_state_rebuilds_with_new_code_from_event_log(self):
        """Full replay: add → change code → old code no longer valid."""
        events = [
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="OLD111"
            ).to_game_event(),
            LocationCodeChangedEvent(number=1, code="NEW222").to_game_event(),
        ]
        # to_game_event() already leaves game_id=None (these events predate the
        # game binding), so nothing to strip before replay.

        state = GameState.from_events(events)

        assert state.location_codes == {1: "NEW222"}

    def test_factory_round_trip(self):
        game_event = LocationCodeChangedEvent(number=7, code="XY7Z9A").to_game_event()

        restored = create_event(game_event)

        assert isinstance(restored, LocationCodeChangedEvent)
        assert restored.number == 7
        assert restored.code == "XY7Z9A"
        assert restored.event_type == EventType.LOCATION_CODE_CHANGED

    def test_to_game_event_payload(self):
        game_event = LocationCodeChangedEvent(number=3, code="ABC").to_game_event()

        assert game_event.event_type == EventType.LOCATION_CODE_CHANGED
        assert game_event.payload == {"number": 3, "code": "ABC"}

    def test_factory_handles_string_event_type(self):
        """GameEvent.event_type may arrive as a plain string from the DB."""
        db_event = GameEvent(
            event_type=EventType.LOCATION_CODE_CHANGED,
            payload={"number": 5, "code": "ZZZ111"},
        )

        restored = create_event(db_event)

        assert isinstance(restored, LocationCodeChangedEvent)
        assert restored.number == 5
        assert restored.code == "ZZZ111"
