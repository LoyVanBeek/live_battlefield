import random
from app.game.state import GameState, BombResult
from app.events.models import (
    TeamJoinedEvent,
    ShipPlacedEvent,
    BombThrownEvent,
    CodeRedeemedEvent,
    LocationAddedEvent,
    BombsAddedEvent,
    TeamResetEvent,
)


def create_ship_placement_events(
    color: str, ships: list[tuple[str, int, int, str]]
) -> list:
    """Helper to create ship placement events for a team."""
    events = []
    for ship_type, row, col, direction in ships:
        events.append(
            ShipPlacedEvent(
                color=color,
                ship_type=ship_type,
                row=row,
                col=col,
                direction=direction,
            )
        )
    return events


def create_full_game_state(events: list) -> GameState:
    """Helper to create GameState from events."""
    db_events = []
    for event in events:
        game_event = type(
            "GameEvent",
            (),
            {
                "event_type": event.event_type.value,
                "payload": {k: v for k, v in vars(event).items() if k != "event_type"},
                "player_id": None,
            },
        )()
        db_events.append(game_event)
    return GameState.from_events(db_events)


class TestEventSequences:
    def test_two_teams_battle(self):
        """Two teams join, place ships, exchange bombs until one runs out."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=5),
        ]

        events.extend(
            create_ship_placement_events(
                "red",
                [
                    ("patrol_boat", 0, 0, "horizontal"),
                    ("patrol_boat", 5, 5, "horizontal"),
                ],
            )
        )

        events.extend(
            create_ship_placement_events(
                "blue",
                [
                    ("patrol_boat", 0, 5, "horizontal"),
                    ("patrol_boat", 5, 0, "horizontal"),
                ],
            )
        )

        events.extend(
            [  # ty: ignore[invalid-argument-type]
                BombThrownEvent(
                    attacker_color="red", target_color="blue", row=0, col=5
                ),
                BombThrownEvent(
                    attacker_color="blue", target_color="red", row=0, col=0
                ),
                BombThrownEvent(
                    attacker_color="red", target_color="blue", row=5, col=0
                ),
                BombThrownEvent(
                    attacker_color="blue", target_color="red", row=5, col=5
                ),
            ]
        )

        state = create_full_game_state(events)

        assert "red" in state.teams
        assert "blue" in state.teams
        assert state.teams["red"].bombs == 3
        assert state.teams["blue"].bombs == 3
        assert state.teams["blue"].public_board[0][5] == ("red", True)
        assert state.teams["red"].public_board[0][0] == ("blue", True)

    def test_teams_run_out_of_bombs(self):
        """Teams use all bombs, verify bombs == 0."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=3),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=2),
        ]

        events.extend(
            create_ship_placement_events(
                "red",
                [
                    ("patrol_boat", 0, 0, "horizontal"),
                ],
            )
        )
        events.extend(
            create_ship_placement_events(
                "blue",
                [
                    ("patrol_boat", 0, 5, "horizontal"),
                ],
            )
        )

        events.extend(
            [  # ty: ignore[invalid-argument-type]
                BombThrownEvent(
                    attacker_color="red", target_color="blue", row=0, col=5
                ),
                BombThrownEvent(
                    attacker_color="red", target_color="blue", row=1, col=5
                ),
                BombThrownEvent(
                    attacker_color="red", target_color="blue", row=2, col=5
                ),
            ]
        )

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 0
        assert state.teams["blue"].bombs == 2

    def test_redeem_code_increases_bombs(self):
        """Team redeems code, bombs increase correctly."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=1),
        ]

        events.extend(
            [  # ty: ignore[invalid-argument-type]
                LocationAddedEvent(
                    number=1, latitude=52.0, longitude=5.0, code="ABCD", bomb_value=5
                ),
                CodeRedeemedEvent(
                    color="red",
                    location_number=1,
                    code="ABCD",
                    success=True,
                    bombs_earned=5,
                ),
            ]
        )

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 6

    def test_full_game_flow(self):
        """Multiple teams join → location added → code redeemed → battle."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=2),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=1),
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="CODE1", bomb_value=10
            ),
            LocationAddedEvent(
                number=2, latitude=52.1, longitude=5.1, code="CODE2", bomb_value=5
            ),
            CodeRedeemedEvent(
                color="red",
                location_number=1,
                code="CODE1",
                success=True,
                bombs_earned=10,
            ),
            CodeRedeemedEvent(
                color="blue",
                location_number=2,
                code="CODE2",
                success=True,
                bombs_earned=5,
            ),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=5,
                col=5,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=5, col=5),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 11
        assert state.teams["blue"].bombs == 6

    def test_prevent_duplicate_code_redeem(self):
        """Same team cannot redeem same location twice."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=1),
        ]

        events.extend(
            [  # ty: ignore[invalid-argument-type]
                LocationAddedEvent(
                    number=1, latitude=52.0, longitude=5.0, code="ABCD", bomb_value=5
                ),
                CodeRedeemedEvent(
                    color="red",
                    location_number=1,
                    code="ABCD",
                    success=True,
                    bombs_earned=5,
                ),
                CodeRedeemedEvent(
                    color="red",
                    location_number=1,
                    code="ABCD",
                    success=False,
                    bombs_earned=0,
                ),
            ]
        )

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 6

    def test_battle_after_code_redeem(self):
        """Team redeems code mid-battle, then continues bombing."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=1),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=1),
            LocationAddedEvent(
                number=1, latitude=51.0, longitude=4.0, code="CODE1", bomb_value=3
            ),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=5,
                col=5,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=5, col=5),
            CodeRedeemedEvent(
                color="red",
                location_number=1,
                code="CODE1",
                success=True,
                bombs_earned=3,
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=5, col=6),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 2
        assert state.teams["blue"].bombs == 1

    def test_team_elimination(self):
        """One team loses all ships, other team wins."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=10),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=1),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=3,
                col=3,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=3, col=3),
            BombThrownEvent(attacker_color="red", target_color="blue", row=3, col=4),
        ]

        state = create_full_game_state(events)

        assert state.teams["blue"].is_destroyed()
        assert not state.teams["red"].is_destroyed()
        assert state.teams["red"].bombs == 8

    def test_cannot_bomb_own_ships(self):
        """Teams cannot bomb themselves (just loses a bomb)."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=3),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="red", row=0, col=0),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 2

    def test_three_teams_complex_battle(self):
        """Three teams with complex battle interactions."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=3),
            TeamJoinedEvent(name="Team C", color="green", chat_id=3, bombs=4),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=5,
                col=5,
                direction="horizontal",
            ),
            ShipPlacedEvent(
                color="green",
                ship_type="patrol_boat",
                row=9,
                col=9,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=5, col=5),
            BombThrownEvent(attacker_color="blue", target_color="green", row=9, col=9),
            BombThrownEvent(attacker_color="green", target_color="red", row=0, col=0),
            BombThrownEvent(attacker_color="red", target_color="blue", row=5, col=6),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 3
        assert state.teams["blue"].bombs == 2
        assert state.teams["green"].bombs == 3

    def test_locations_accumulate_bombs(self):
        """Multiple locations can be redeemed by multiple teams."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=0),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=0),
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="A1", bomb_value=3
            ),
            LocationAddedEvent(
                number=2, latitude=52.1, longitude=5.1, code="B2", bomb_value=7
            ),
            LocationAddedEvent(
                number=3, latitude=52.2, longitude=5.2, code="C3", bomb_value=5
            ),
            CodeRedeemedEvent(
                color="red", location_number=1, code="A1", success=True, bombs_earned=3
            ),
            CodeRedeemedEvent(
                color="blue", location_number=1, code="A1", success=True, bombs_earned=3
            ),
            CodeRedeemedEvent(
                color="red", location_number=2, code="B2", success=True, bombs_earned=7
            ),
            CodeRedeemedEvent(
                color="blue", location_number=3, code="C3", success=True, bombs_earned=5
            ),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 10
        assert state.teams["blue"].bombs == 8

    def test_ship_placement_affects_battle_outcome(self):
        """Ships placed strategically affect battle outcomes."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=5),
        ]

        events.extend(
            create_ship_placement_events(
                "red",
                [
                    ("patrol_boat", 0, 0, "horizontal"),
                ],
            )
        )
        events.extend(
            create_ship_placement_events(
                "blue",
                [
                    ("patrol_boat", 0, 0, "horizontal"),
                ],
            )
        )

        events.append(
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=0)  # ty: ignore[invalid-argument-type]
        )
        events.append(
            BombThrownEvent(attacker_color="blue", target_color="red", row=0, col=0)  # ty: ignore[invalid-argument-type]
        )

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 4
        assert state.teams["blue"].bombs == 4

        red_board = state.teams["red"].public_board
        blue_board = state.teams["blue"].public_board

        assert red_board[0][0] == ("blue", True)
        assert blue_board[0][0] == ("red", True)

    def test_from_events_reconstructs_complete_state(self):
        """GameState.from_events correctly reconstructs complete game state."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=3),
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="LOC1", bomb_value=10
            ),
            CodeRedeemedEvent(
                color="red",
                location_number=1,
                code="LOC1",
                success=True,
                bombs_earned=10,
            ),
        ]

        events.extend(
            create_ship_placement_events(
                "red",
                [
                    ("airplane_carrier", 0, 0, "horizontal"),
                    ("battleship", 2, 0, "horizontal"),
                    ("torpedo_hunter", 4, 0, "horizontal"),
                    ("patrol_boat", 6, 0, "horizontal"),
                ],
            )
        )

        events.append(
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=0)  # ty: ignore[invalid-argument-type]
        )
        events.append(
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=1)  # ty: ignore[invalid-argument-type]
        )

        state = create_full_game_state(events)

        assert len(state.teams) == 2
        assert state.teams["red"].bombs == 13
        assert state.teams["blue"].bombs == 3
        assert len(state.teams["red"].ships) == 4
        assert state.teams["blue"].public_board[0][0] == ("red", False)
        assert state.teams["blue"].public_board[0][1] is None or state.teams[
            "blue"
        ].public_board[0][1] == ("red", False)

    def test_bombs_added_event(self):
        """Add bombs to a team using BombsAddedEvent."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            BombsAddedEvent(color="red", count=10),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 15

    def test_bombs_added_default_count(self):
        """BombsAddedEvent uses default count of 1."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            BombsAddedEvent(color="red"),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 6

    def test_team_reset_event(self):
        """Reset a team's state using TeamResetEvent."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=10),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            ShipPlacedEvent(
                color="red",
                ship_type="battleship",
                row=2,
                col=0,
                direction="horizontal",
            ),
            TeamResetEvent(color="red"),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 3  # default
        assert len(state.teams["red"].ships) == 0
        assert state.teams["red"].placed_ship_types == {}

    def test_bombs_added_nonexistent_team(self):
        """BombsAddedEvent for non-existent team is ignored."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            BombsAddedEvent(color="blue", count=10),
        ]

        state = create_full_game_state(events)

        assert "blue" not in state.teams
        assert state.teams["red"].bombs == 5

    def test_ship_placement_success_event(self):
        """Ship placed event returns success=True when placement succeeds."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
        ]

        state = create_full_game_state(events)

        assert len(state.teams["red"].ships) == 1

    def test_ship_placement_failure(self):
        """Ship placement fails for invalid position."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=1,
                direction="horizontal",
            ),
        ]

        state = create_full_game_state(events)

        assert len(state.teams["red"].ships) == 1

    def test_bomb_throw_invalid_attacker(self):
        """Bomb throw is ignored if attacker doesn't exist."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="blue", target_color="red", row=0, col=0),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 5

    def test_bomb_throw_invalid_target(self):
        """Bomb throw is ignored if target doesn't exist."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=0),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 5

    def test_bomb_throw_no_bombs(self):
        """Bomb throw is ignored if attacker has no bombs."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=0),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=5),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=0),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 0
        assert state.teams["blue"].bombs == 5

    def test_bomb_result_hit(self):
        """Bomb throw results in hit."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=5),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=0),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 4
        assert state.teams["blue"].public_board[0][0] == ("red", True)

    def test_bomb_result_miss(self):
        """Bomb throw results in miss."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=5),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=5, col=5),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 4
        assert state.teams["blue"].public_board[5][5] == ("red", False)

    def test_code_redeemed_invalid_location(self):
        """Code redemption fails for invalid location."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="CODE1", bomb_value=10
            ),
            CodeRedeemedEvent(
                color="red",
                location_number=2,
                code="CODE1",
                success=True,
                bombs_earned=10,
            ),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 5

    def test_code_redeemed_invalid_code(self):
        """Code redemption fails for invalid code."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="CODE1", bomb_value=10
            ),
            CodeRedeemedEvent(
                color="red",
                location_number=1,
                code="WRONG",
                success=True,
                bombs_earned=10,
            ),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 5

    def test_code_redeemed_invalid_team(self):
        """Code redemption fails for non-existent team."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="CODE1", bomb_value=10
            ),
            CodeRedeemedEvent(
                color="blue",
                location_number=1,
                code="CODE1",
                success=True,
                bombs_earned=10,
            ),
        ]

        state = create_full_game_state(events)

        assert "blue" not in state.teams

    def test_location_added_updates_counter(self):
        """Location added updates location counter."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            LocationAddedEvent(
                number=3, latitude=52.0, longitude=5.0, code="CODE1", bomb_value=10
            ),
            LocationAddedEvent(
                number=1, latitude=52.1, longitude=5.1, code="CODE2", bomb_value=5
            ),
        ]

        state = create_full_game_state(events)

        assert state.location_counter == 3

    def test_duplicate_team_ignored(self):
        """Duplicate team with same color is ignored."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=5),
            TeamJoinedEvent(name="Team A2", color="red", chat_id=2, bombs=10),
        ]

        state = create_full_game_state(events)

        assert len(state.teams) == 1
        assert state.teams["red"].bombs == 5

    def test_ship_placement_team_not_exists(self):
        """Ship placement fails if team doesn't exist."""
        events = [
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
        ]

        state = create_full_game_state(events)

        assert len(state.teams) == 0

    def test_full_battle_sequence(self):
        """Complete battle sequence from start to finish."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=10),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=10),
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="CODE1", bomb_value=5
            ),
            CodeRedeemedEvent(
                color="red",
                location_number=1,
                code="CODE1",
                success=True,
                bombs_earned=5,
            ),
            ShipPlacedEvent(
                color="red",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=0,
                col=5,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=5),
            BombThrownEvent(attacker_color="blue", target_color="red", row=0, col=0),
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=6),
            BombThrownEvent(attacker_color="blue", target_color="red", row=0, col=1),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 13
        assert state.teams["blue"].bombs == 8
        assert state.teams["blue"].public_board[0][5] == ("red", True)
        assert state.teams["red"].public_board[0][0] == ("blue", True)

    def test_multi_team_location_redeem(self):
        """Multiple teams redeem same location."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=1),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=1),
            TeamJoinedEvent(name="Team C", color="green", chat_id=3, bombs=1),
            LocationAddedEvent(
                number=1, latitude=52.0, longitude=5.0, code="CODE1", bomb_value=5
            ),
            CodeRedeemedEvent(
                color="red",
                location_number=1,
                code="CODE1",
                success=True,
                bombs_earned=5,
            ),
            CodeRedeemedEvent(
                color="blue",
                location_number=1,
                code="CODE1",
                success=True,
                bombs_earned=5,
            ),
            CodeRedeemedEvent(
                color="green",
                location_number=1,
                code="CODE1",
                success=True,
                bombs_earned=5,
            ),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 6
        assert state.teams["blue"].bombs == 6
        assert state.teams["green"].bombs == 6

    def test_ship_sunk_completely(self):
        """Ship is marked as sunk when all cells are hit."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=10),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=10),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=5,
                col=5,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=5, col=5),
            BombThrownEvent(attacker_color="red", target_color="blue", row=5, col=6),
        ]

        state = create_full_game_state(events)

        assert state.teams["blue"].is_destroyed() == True

    def test_already_bombed_cell(self):
        """Bombing an already bombed cell returns already_bombed."""
        events = [
            TeamJoinedEvent(name="Team A", color="red", chat_id=1, bombs=10),
            TeamJoinedEvent(name="Team B", color="blue", chat_id=2, bombs=10),
            ShipPlacedEvent(
                color="blue",
                ship_type="patrol_boat",
                row=0,
                col=0,
                direction="horizontal",
            ),
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=0),
            BombThrownEvent(attacker_color="red", target_color="blue", row=0, col=0),
        ]

        state = create_full_game_state(events)

        assert state.teams["red"].bombs == 8
