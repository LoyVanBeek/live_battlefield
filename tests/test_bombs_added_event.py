import pytest
from app.game.state import GameState
from app.events.models import BombsAddedEvent, TeamJoinedEvent


class TestBombsAddedEvent:
    def test_add_bombs_to_team(self):
        """Adding bombs to a team increases their bomb count."""
        state = GameState()
        state.teams["red"] = (
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5)
            .apply(state)[0]
            .teams["red"]
        )

        event = BombsAddedEvent(color="red", count=10)
        new_state, updated_event = event.apply(state)

        assert new_state.teams["red"].bombs == 15
        assert updated_event.success == True

    def test_add_bombs_default_count(self):
        """Adding bombs with default count of 1."""
        state = GameState()
        state.teams["red"] = (
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5)
            .apply(state)[0]
            .teams["red"]
        )

        event = BombsAddedEvent(color="red")
        new_state, updated_event = event.apply(state)

        assert new_state.teams["red"].bombs == 6
        assert updated_event.count == 1

    def test_add_bombs_to_nonexistent_team(self):
        """Adding bombs to a non-existent team fails."""
        state = GameState()

        event = BombsAddedEvent(color="red", count=10)
        new_state, updated_event = event.apply(state)

        assert new_state == state
        assert updated_event.success == False

    def test_add_bombs_event_type(self):
        """BombsAddedEvent has correct event type."""
        event = BombsAddedEvent(color="red", count=5)
        assert event.event_type.value == "bombs_added"

    def test_to_game_event(self):
        """BombsAddedEvent converts to GameEvent correctly."""
        event = BombsAddedEvent(color="red", count=5, success=True)
        game_event = event.to_game_event()

        assert game_event.event_type.value == "bombs_added"
        assert game_event.payload["color"] == "red"
        assert game_event.payload["count"] == 5
        assert game_event.payload["success"] == True
