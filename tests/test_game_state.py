from app.game.state import GameState
from app.events.models import (
    TeamJoinedEvent,
    ShipPlacedEvent,
    BombThrownEvent,
    CodeRedeemedEvent,
    LocationAddedEvent,
)


class TestGameState:
    def test_team_joined(self):
        state = GameState()
        event = TeamJoinedEvent(name="Team A", color="red", chat_id=123, bombs=3)
        state.handle_team_joined(event)

        assert "red" in state.teams
        assert state.teams["red"].name == "Team A"
        assert state.teams["red"].bombs == 3

    def test_get_next_color(self):
        state = GameState()

        assert state.get_next_color() == "red"

        event = TeamJoinedEvent(name="Team A", color="red", chat_id=123, bombs=3)
        state.handle_team_joined(event)

        assert state.get_next_color() == "blue"

    def test_is_team_name_taken(self):
        state = GameState()

        assert state.is_team_name_taken("Team A") == False

        event = TeamJoinedEvent(name="Team A", color="red", chat_id=123, bombs=3)
        state.handle_team_joined(event)

        assert state.is_team_name_taken("Team A") == True
        assert state.is_team_name_taken("team a") == True
        assert state.is_team_name_taken("Team B") == False

    def test_bomb_thrown(self):
        state = GameState()
        event1 = TeamJoinedEvent(name="Team A", color="red", chat_id=123, bombs=5)
        state.handle_team_joined(event1)
        event2 = TeamJoinedEvent(name="Team B", color="blue", chat_id=456, bombs=3)
        state.handle_team_joined(event2)
        ship_event = ShipPlacedEvent(
            color="blue",
            ship_type="patrol_boat",
            row=0,
            col=0,
            direction="horizontal",
        )
        state.handle_ship_placed(ship_event)

        bomb_event = BombThrownEvent(
            attacker_color="red", target_color="blue", row=0, col=0
        )
        state.handle_bomb_thrown(bomb_event)

        assert state.teams["red"].bombs == 4
        assert state.teams["blue"].public_board[0][0] == ("red", True)

    def test_code_redeemed(self):
        state = GameState()
        event = TeamJoinedEvent(name="Team A", color="red", chat_id=123, bombs=3)
        state.handle_team_joined(event)
        loc_event = LocationAddedEvent(
            number=1, latitude=52.0, longitude=5.0, code="ABCD"
        )
        state.handle_location_added(loc_event)

        code_event = CodeRedeemedEvent(color="red", location_number=1, code="ABCD")
        state.handle_code_redeemed(code_event)

        assert state.teams["red"].bombs == 4

    def test_from_events(self):
        events = [
            type(
                "Event",
                (),
                {
                    "event_type": "team_joined",
                    "payload": {
                        "name": "Team A",
                        "color": "red",
                        "chat_id": 123,
                        "bombs": 3,
                    },
                },
            )(),
            type(
                "Event",
                (),
                {
                    "event_type": "ship_placed",
                    "payload": {
                        "color": "red",
                        "ship_type": "patrol_boat",
                        "row": 0,
                        "col": 0,
                        "direction": "horizontal",
                    },
                },
            )(),
        ]

        state = GameState.from_events(events)

        assert "red" in state.teams
        assert len(state.teams["red"].ships) == 1
