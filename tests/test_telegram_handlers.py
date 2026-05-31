import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.database import Role


def create_mock_update(chat_id=12345):
    """Create a mock Telegram Update object"""
    mock_update = MagicMock()
    mock_update.effective_chat.id = chat_id
    return mock_update


def create_mock_context():
    """Create a mock Telegram context object"""
    return MagicMock()


def create_mock_game(status="preparing"):
    mock_game = MagicMock()
    mock_game.id = "00000000-0000-0000-0000-000000000000"
    mock_game.gm_token = "test-gm-token"
    mock_game.status.value = status
    return mock_game


class TestHandleJoin:
    """Tests for handle_join() function"""

    @pytest.mark.asyncio
    async def test_new_user_can_join(self):
        from app.bot.handlers import handle_join

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                with patch(
                    "app.bot.handlers.create_player", new_callable=AsyncMock
                ) as mock_create:
                    with patch(
                        "app.bot.handlers.save_event", new_callable=AsyncMock
                    ) as mock_save:
                        with patch(
                            "app.models.get_all_players_in_game",
                            new_callable=AsyncMock,
                        ) as mock_get_all:
                            mock_get_all.return_value = []
                            with patch(
                                "app.models.get_all_games",
                                new_callable=AsyncMock,
                            ) as mock_get_games:
                                mock_get_games.return_value = [create_mock_game("preparing")]
                                mock_get_player.return_value = None
                                mock_events.return_value = []

                                result = await handle_join(
                                    mock_db,
                                    mock_update,
                                    mock_context,
                                    "Blue Team",
                                )

                                assert "Welcome" in result
                                assert "Blue Team" in result

    @pytest.mark.asyncio
    async def test_gm_can_join_as_team(self):
        from app.bot.handlers import handle_join

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.delete = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                with patch(
                    "app.bot.handlers.create_player", new_callable=AsyncMock
                ) as mock_create:
                    with patch(
                        "app.bot.handlers.save_event", new_callable=AsyncMock
                    ) as mock_save:
                        with patch(
                            "app.models.get_all_players_in_game",
                            new_callable=AsyncMock,
                        ) as mock_get_all:
                            mock_get_all.return_value = []
                            with patch(
                                "app.models.get_all_games",
                                new_callable=AsyncMock,
                            ) as mock_get_games:
                                mock_get_games.return_value = [create_mock_game("preparing")]
                                mock_player = MagicMock()
                                mock_player.role = Role.GAMEMASTER
                                mock_get_player.return_value = mock_player

                                mock_events.return_value = []

                                result = await handle_join(
                                    mock_db,
                                    mock_update,
                                    mock_context,
                                    "Red Team",
                                )

                                assert "Welcome" in result

    @pytest.mark.asyncio
    async def test_team_player_can_rejoin(self):
        from app.bot.handlers import handle_join

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.delete = AsyncMock()
        mock_db.refresh = AsyncMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                with patch(
                    "app.bot.handlers.create_player", new_callable=AsyncMock
                ) as mock_create:
                    with patch(
                        "app.bot.handlers.save_event", new_callable=AsyncMock
                    ) as mock_save:
                        with patch(
                            "app.models.get_all_players_in_game",
                            new_callable=AsyncMock,
                        ) as mock_get_all:
                            mock_get_all.return_value = []
                            with patch(
                                "app.models.get_all_games",
                                new_callable=AsyncMock,
                            ) as mock_get_games:
                                mock_get_games.return_value = [create_mock_game("preparing")]
                                mock_player = MagicMock()
                                mock_player.role = Role.TEAM
                                mock_get_player.return_value = mock_player

                                mock_events.return_value = []

                                result = await handle_join(
                                    mock_db,
                                    mock_update,
                                    mock_context,
                                    "New Team",
                                )

                                assert "Welcome" in result

    @pytest.mark.asyncio
    async def test_game_started_blocks_join(self):
        from app.bot.handlers import handle_join

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                mock_get_player.return_value = None
                mock_events.return_value = []
                with patch(
                    "app.models.get_all_games",
                    new_callable=AsyncMock,
                ) as mock_get_games:
                    mock_get_games.return_value = [create_mock_game("started")]

                    result = await handle_join(
                        mock_db, mock_update, mock_context, "Blue Team"
                    )

                    assert "already started" in result.lower()

    @pytest.mark.asyncio
    async def test_game_ended_message(self):
        from app.bot.handlers import handle_join

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                mock_get_player.return_value = None
                mock_events.return_value = []
                with patch(
                    "app.models.get_all_games",
                    new_callable=AsyncMock,
                ) as mock_get_games:
                    mock_get_games.return_value = [create_mock_game("ended")]

                    result = await handle_join(
                        mock_db, mock_update, mock_context, "Blue Team"
                    )

                    assert "ended" in result.lower()


class TestHandlePlace:
    """Tests for handle_place() function"""

    @pytest.mark.asyncio
    async def test_not_joined_error(self):
        from app.bot.handlers import handle_place

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_get_player.return_value = None

            result = await handle_place(
                mock_db, mock_update, mock_context, "battleship", "A1", "horizontal"
            )

            assert result is not None and "need to join" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_ship_type(self):
        from app.bot.handlers import handle_place

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_player = MagicMock()
            mock_player.color = "blue"
            mock_get_player.return_value = mock_player

            result = await handle_place(
                mock_db, mock_update, mock_context, "invalid_ship", "A1", "horizontal"
            )

            assert result is not None and "invalid ship type" in result.lower()

    @pytest.mark.asyncio
    async def test_invalid_direction(self):
        from app.bot.handlers import handle_place

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_player = MagicMock()
            mock_player.color = "blue"
            mock_get_player.return_value = mock_player

            result = await handle_place(
                mock_db, mock_update, mock_context, "battleship", "A1", "diagonal"
            )

            assert result is not None and "invalid direction" in result.lower()


class TestHandleBomb:
    """Tests for handle_bomb() function"""

    @pytest.mark.asyncio
    async def test_not_joined_error(self):
        from app.bot.handlers import handle_bomb

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_get_player.return_value = None

            result = await handle_bomb(mock_db, mock_update, mock_context, "red", "A1")

            assert result is not None and "need to join" in result.lower()

    @pytest.mark.asyncio
    async def test_self_bomb_error(self):
        from app.bot.handlers import handle_bomb
        from app.game.state import GameState, GameStatusField, TeamState

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                with patch.object(
                    GameState, "from_events", return_value=GameState()
                ) as mock_from_events:
                    mock_player = MagicMock()
                    mock_player.color = "blue"
                    mock_get_player.return_value = mock_player

                    from app.game.state import GameStatusField

                    mock_team = TeamState(
                        name="Blue", color="blue", bombs=3, chat_id=123
                    )
                    mock_state = GameState()
                    mock_state.status = GameStatusField.STARTED
                    mock_state.teams = {"blue": mock_team}
                    mock_from_events.return_value = mock_state
                    mock_events.return_value = []

                    result = await handle_bomb(
                        mock_db, mock_update, mock_context, "blue", "A1"
                    )

                    assert (
                        result is not None
                        and "cannot bomb yourself" in result.lower()
                    )


class TestHandleCode:
    """Tests for handle_code() function"""

    @pytest.mark.asyncio
    async def test_not_joined_error(self):
        from app.bot.handlers import handle_code

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_get_player.return_value = None

            result = await handle_code(mock_db, mock_update, mock_context, 1, "ABCD")

            assert result is not None and "need to join" in result.lower()


class TestHandleRegisterGM:
    """Tests for handle_register_gm() function"""

    @pytest.mark.asyncio
    async def test_new_gm_registration(self):
        from app.bot.handlers import handle_register_gm

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.create_player", new_callable=AsyncMock
            ) as mock_create:
                mock_get_player.return_value = None
                with patch(
                    "app.models.get_all_games",
                    new_callable=AsyncMock,
                ) as mock_get_games:
                    mock_get_games.return_value = [create_mock_game("preparing")]

                    result = await handle_register_gm(mock_db, mock_update, mock_context)

                    assert "registered as a game master" in result.lower()

    @pytest.mark.asyncio
    async def test_already_gm_error(self):
        from app.bot.handlers import handle_register_gm

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_player = MagicMock()
            mock_player.role = Role.GAMEMASTER
            mock_get_player.return_value = mock_player
            with patch(
                "app.models.get_all_games",
                new_callable=AsyncMock,
            ) as mock_get_games:
                mock_get_games.return_value = [create_mock_game("preparing")]

                result = await handle_register_gm(mock_db, mock_update, mock_context)

                assert "already registered as a game master" in result.lower()

    @pytest.mark.asyncio
    async def test_team_player_becomes_gm(self):
        from app.bot.handlers import handle_register_gm

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_player = MagicMock()
            mock_player.role = Role.TEAM
            mock_get_player.return_value = mock_player
            with patch(
                "app.models.get_all_games",
                new_callable=AsyncMock,
            ) as mock_get_games:
                mock_get_games.return_value = [create_mock_game("preparing")]

                result = await handle_register_gm(mock_db, mock_update, mock_context)

                assert "also registered" in result.lower() or "now also" in result.lower()


class TestHandleStartGame:
    """Tests for handle_start_game() function"""

    @pytest.mark.asyncio
    async def test_not_gm_error(self):
        from app.bot.handlers import handle_start_game

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_player = MagicMock()
            mock_player.role = Role.TEAM
            mock_get_player.return_value = mock_player

            result = await handle_start_game(mock_db, mock_update, mock_context)

            assert result is not None and "only game masters" in result.lower()


class TestHandleResetGame:
    """Tests for handle_reset_game() function"""

    @pytest.mark.asyncio
    async def test_not_gm_error(self):
        from app.bot.handlers import handle_reset_game

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_player = MagicMock()
            mock_player.role = Role.TEAM
            mock_get_player.return_value = mock_player

            result = await handle_reset_game(mock_db, mock_update, mock_context)

            assert result is not None and "only game masters" in result.lower()


class TestHandleOverview:
    """Tests for handle_overview() function"""

    @pytest.mark.asyncio
    async def test_not_joined_error(self):
        from app.bot.handlers import handle_overview

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            mock_get_player.return_value = None

            result = await handle_overview(mock_db, mock_update, mock_context)

            assert result is not None and "need to join" in result.lower()

    @pytest.mark.asyncio
    async def test_success_with_full_stats(self):
        from app.bot.handlers import handle_overview
        from app.game.state import GameState, TeamState

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                with patch.object(GameState, "from_events") as mock_from_events:
                    with patch(
                        "app.bot.handlers.render_private_board"
                    ) as mock_render_private:
                        with patch(
                            "app.bot.handlers.render_all_public_boards"
                        ) as mock_render_public:
                            with patch(
                                "app.bot.handlers.boards_to_bytes"
                            ) as mock_to_bytes:
                                with patch(
                                    "app.bot.handlers.send_photo",
                                    new_callable=AsyncMock,
                                ) as mock_send_photo:
                                    mock_player = MagicMock()
                                    mock_player.color = "blue"
                                    mock_get_player.return_value = mock_player

                                    mock_team = TeamState(
                                        name="Blue Team",
                                        color="blue",
                                        bombs=5,
                                        chat_id=123,
                                        ships=[],
                                        placed_ship_types={
                                            "battleship": 1,
                                            "cruiser": 1,
                                        },
                                    )
                                    mock_state = GameState()
                                    mock_state.teams = {"blue": mock_team}
                                    mock_events.return_value = []
                                    mock_from_events.return_value = mock_state

                                    mock_render_private.return_value = MagicMock()
                                    mock_render_public.return_value = MagicMock()
                                    mock_to_bytes.return_value = b"fake_image_bytes"

                                    result = await handle_overview(
                                        mock_db, mock_update, mock_context
                                    )

                                    assert result is None
                                    assert mock_send_photo.call_count == 2
                                    first_call = mock_send_photo.call_args_list[0]
                                    assert "Blue Team" in first_call.kwargs.get(
                                        "caption", ""
                                    )

    @pytest.mark.asyncio
    async def test_not_in_game_yet(self):
        from app.bot.handlers import handle_overview
        from app.game.state import GameState

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                mock_player = MagicMock()
                mock_player.color = "blue"
                mock_get_player.return_value = mock_player

                mock_events.return_value = []

                result = await handle_overview(mock_db, mock_update, mock_context)

                assert result is not None and "not in the game yet" in result.lower()

    @pytest.mark.asyncio
    async def test_no_ships_placed(self):
        from app.bot.handlers import handle_overview
        from app.game.state import GameState, TeamState

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                with patch.object(GameState, "from_events") as mock_from_events:
                    with patch("app.bot.handlers.send_photo", new_callable=AsyncMock):
                        mock_player = MagicMock()
                        mock_player.color = "blue"
                        mock_get_player.return_value = mock_player

                        mock_team = TeamState(
                            name="Blue Team",
                            color="blue",
                            bombs=3,
                            chat_id=123,
                            ships=[],
                            placed_ship_types={},
                        )
                        mock_state = GameState()
                        mock_state.teams = {"blue": mock_team}
                        mock_events.return_value = []
                        mock_from_events.return_value = mock_state

                        result = await handle_overview(
                            mock_db, mock_update, mock_context
                        )

                    assert result is None

    @pytest.mark.asyncio
    async def test_with_sunk_ships(self):
        from app.bot.handlers import handle_overview
        from app.game.state import GameState, TeamState, Ship

        mock_update = create_mock_update(123)
        mock_context = create_mock_context()
        mock_db = MagicMock()

        with patch(
            "app.bot.handlers.get_player_by_chat", new_callable=AsyncMock
        ) as mock_get_player:
            with patch(
                "app.bot.handlers.get_game_events", new_callable=AsyncMock
            ) as mock_events:
                with patch.object(GameState, "from_events") as mock_from_events:
                    with patch(
                        "app.bot.handlers.send_photo", new_callable=AsyncMock
                    ) as mock_send_photo:
                        mock_player = MagicMock()
                        mock_player.color = "blue"
                        mock_get_player.return_value = mock_player

                        sunk_ship = Ship(
                            ship_type="battleship",
                            cells=[(0, 0), (0, 1), (0, 2), (0, 3)],
                            hits=4,
                        )
                        mock_team = TeamState(
                            name="Blue Team",
                            color="blue",
                            bombs=3,
                            chat_id=123,
                            ships=[sunk_ship],
                            placed_ship_types={"battleship": 1},
                        )
                        mock_state = GameState()
                        mock_state.teams = {"blue": mock_team}
                        mock_events.return_value = []
                        mock_from_events.return_value = mock_state

                        result = await handle_overview(
                            mock_db, mock_update, mock_context
                        )

                        assert result is None
                        first_call = mock_send_photo.call_args_list[0]
                        caption = first_call.kwargs.get("caption", "")
                        assert "Sunk ships: 1" in caption
