import pytest
from app.game.state import GameState
from app.events.models import TeamResetEvent, TeamJoinedEvent, ShipPlacedEvent


class TestTeamResetEvent:
    def test_reset_team(self):
        """Resetting a team clears ships and boards."""
        state = GameState()

        # First create a team
        event = TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=10)
        state, _ = event.apply(state)

        # Place some ships
        ship_event = ShipPlacedEvent(
            color="red",
            ship_type="patrol_boat",
            row=0,
            col=0,
            direction="horizontal",
        )
        state, _ = ship_event.apply(state)

        # Verify ships placed
        assert len(state.teams["red"].ships) == 1
        assert len(state.teams["red"].bombed_cells) == 0

        # Now reset the team
        reset_event = TeamResetEvent(color="red")
        new_state, updated_event = reset_event.apply(state)

        # Verify - ships cleared reset, boards cleared, bombs reset to default
        assert len(new_state.teams["red"].ships) == 0
        assert new_state.teams["red"].placed_ship_types == {}
        assert new_state.teams["red"].bombed_cells == []
        assert new_state.teams["red"].bombs == 3  # default
        assert updated_event.success == True

    def test_reset_nonexistent_team(self):
        """Resetting a non-existent team fails."""
        state = GameState()

        reset_event = TeamResetEvent(color="red")
        new_state, updated_event = reset_event.apply(state)

        assert new_state == state
        assert updated_event.success == False

    def test_reset_team_event_type(self):
        """TeamResetEvent has correct event type."""
        event = TeamResetEvent(color="red")
        assert event.event_type.value == "team_reset"

    def test_to_game_event(self):
        """TeamResetEvent converts to GameEvent correctly."""
        event = TeamResetEvent(color="red", success=True)
        game_event = event.to_game_event()

        assert game_event.event_type.value == "team_reset"
        assert game_event.payload["color"] == "red"
        assert game_event.payload["success"] == True

    def test_reset_preserves_only_team(self):
        """Resetting one team doesn't affect other teams."""
        state = GameState()

        # Create two teams
        event1 = TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=10)
        state, _ = event1.apply(state)

        event2 = TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=5)
        state, _ = event2.apply(state)

        # Place ships on both
        ship_event1 = ShipPlacedEvent(
            color="red",
            ship_type="patrol_boat",
            row=0,
            col=0,
            direction="horizontal",
        )
        state, _ = ship_event1.apply(state)

        ship_event2 = ShipPlacedEvent(
            color="blue",
            ship_type="patrol_boat",
            row=5,
            col=5,
            direction="horizontal",
        )
        state, _ = ship_event2.apply(state)

        # Reset only red team
        reset_event = TeamResetEvent(color="red")
        new_state, _ = reset_event.apply(state)

        # Red should be reset
        assert len(new_state.teams["red"].ships) == 0

        # Blue should be untouched
        assert len(new_state.teams["blue"].ships) == 1
        assert new_state.teams["blue"].bombs == 5
