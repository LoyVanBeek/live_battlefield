"""Tests for the location quiz — a per-location check-in without a printed code.

A location can be proved either by its code, by answering a location-scoped
multiple-choice question, or both. Answering the quiz is an honour-system
check-in: any attempt (right or wrong) marks the location visited for that team,
and each question can only be answered once.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

GAME_ID = "00000000-0000-0000-0000-000000000000"


def create_mock_team(name="Red", color="red", bombs=0):
    from app.game.state import TeamState

    return TeamState(name=name, color=color, chat_id=123, bombs=bombs)


# ---------------------------------------------------------------------------
# Event apply / factory
# ---------------------------------------------------------------------------


class TestLocationQuizEvent:
    def test_apply_awards_bombs(self):
        from app.events.models import LocationQuizAnsweredEvent
        from app.game.state import GameState

        state = GameState()
        state.teams["red"] = create_mock_team(bombs=3)

        new_state, applied = LocationQuizAnsweredEvent(color="red", bombs_earned=7).apply(state)

        assert new_state.teams["red"].bombs == 10
        assert applied.success is True

    def test_apply_unknown_team_is_a_noop(self):
        from app.events.models import LocationQuizAnsweredEvent
        from app.game.state import GameState

        state = GameState()
        new_state, applied = LocationQuizAnsweredEvent(color="red", bombs_earned=7).apply(state)

        assert new_state.teams == {}
        assert applied.success is False

    def test_factory_round_trips_the_event(self):
        from app.database import GameEvent
        from app.events.factory import create_event
        from app.events.models import LocationQuizAnsweredEvent

        import uuid

        original = LocationQuizAnsweredEvent(
            color="blue", location_number=4, question_id=12, answer_id=34,
            bombs_earned=5, success=True,
        )
        db_event = original.to_game_event(game_id=uuid.UUID(GAME_ID))

        assert isinstance(db_event, GameEvent)
        rebuilt = create_event(db_event)

        assert isinstance(rebuilt, LocationQuizAnsweredEvent)
        assert rebuilt.color == "blue"
        assert rebuilt.location_number == 4
        assert rebuilt.question_id == 12
        assert rebuilt.answer_id == 34
        assert rebuilt.bombs_earned == 5


# ---------------------------------------------------------------------------
# /api/execute — location_quiz command
# ---------------------------------------------------------------------------


class TestLocationQuizCommand:
    def _run(self, *, quiz_mode="quiz", answer_bomb_value=5, answer_question_id=1,
             question_location=3, question_game_id=GAME_ID, status_started=True,
             events=None, args=None, team_bombs=0):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": GAME_ID, "color": "red",
        }
        try:
            state = GameState()
            if status_started:
                state.status = GameStatusField.STARTED
            state.teams["red"] = create_mock_team(bombs=team_bombs)

            location = MagicMock()
            location.quiz_mode = quiz_mode
            location.bomb_value = 10

            answer = MagicMock()
            answer.bomb_value = answer_bomb_value
            answer.question_id = answer_question_id
            answer.is_correct = answer_bomb_value > 0

            question = MagicMock()
            question.game_id = __import__("uuid").UUID(question_game_id)
            question.id = 1
            question.location_number = question_location
            question.source_url = "https://example.com/source"

            game = MagicMock()
            game.paused_until = None
            game.max_bombs = 100

            payload = args or {
                "location_number": 3, "question_id": 1, "answer_id": 1,
            }

            import uuid as _uuid

            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=events or []):
                    with patch("app.api.routes.save_event") as mock_save:
                        with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute:
                            mock_execute.side_effect = [
                                MagicMock(scalar_one_or_none=MagicMock(return_value=location)),
                                MagicMock(scalar_one_or_none=MagicMock(return_value=answer)),
                                MagicMock(scalar_one_or_none=MagicMock(return_value=question)),
                            ]
                            with patch("app.models.get_game", return_value=game):
                                response = TestClient(app).post("/api/execute", json={
                                    "team_color": "red",
                                    "command": "location_quiz",
                                    "args": payload,
                                })
            assert response.status_code == 200
            return response.json(), mock_save
        finally:
            app.dependency_overrides.clear()

    def test_correct_answer_awards_bombs(self):
        data, mock_save = self._run(answer_bomb_value=5)
        assert data["success"] is True
        assert data["message"] == "Correct! +5 bombs."
        assert data["source_url"] == "https://example.com/source"
        from app.events.models import LocationQuizAnsweredEvent

        saved = mock_save.call_args[0][1]
        assert isinstance(saved, LocationQuizAnsweredEvent)
        assert saved.bombs_earned == 5
        assert saved.location_number == 3

    def test_wrong_answer_earns_nothing_but_is_recorded(self):
        data, mock_save = self._run(answer_bomb_value=0)
        assert data["success"] is False
        assert data["message"] == "Wrong answer! No bombs earned."
        # The attempt is still recorded so the question is burned (visited).
        assert mock_save.called
        saved = mock_save.call_args[0][1]
        assert saved.bombs_earned == 0
        assert saved.success is False

    def test_code_only_location_has_no_quiz(self):
        data, mock_save = self._run(quiz_mode="code")
        assert data["success"] is False
        assert data["message"] == "This location has no quiz!"
        assert not mock_save.called

    def test_both_mode_location_offers_the_quiz(self):
        data, _ = self._run(quiz_mode="both", answer_bomb_value=5)
        assert data["success"] is True

    def test_question_from_another_location_is_rejected(self):
        data, _ = self._run(question_location=99)
        assert data["success"] is False
        assert data["message"] == "Invalid question!"

    def test_answer_from_another_question_is_rejected(self):
        data, _ = self._run(answer_question_id=999)
        assert data["success"] is False
        assert data["message"] == "Invalid answer!"

    def test_already_answered_question_is_rejected(self):
        from app.database import EventType

        ev = MagicMock()
        ev.event_type = EventType.LOCATION_QUIZ_ANSWERED
        ev.payload = {"color": "red", "question_id": 1, "location_number": 3}

        data, mock_save = self._run(events=[ev])
        assert data["success"] is False
        assert data["message"] == "You've already answered this question!"
        assert not mock_save.called

    def test_cannot_answer_before_the_game_starts(self):
        data, mock_save = self._run(status_started=False)
        assert data["success"] is False
        assert data["message"] == "Cannot answer quiz - game hasn't started yet!"
        assert not mock_save.called

    def test_bombs_are_capped_at_max(self):
        data, mock_save = self._run(answer_bomb_value=5, team_bombs=98)
        assert data["success"] is True
        # 100 max - 98 held = 2 available, even though the answer is worth 5.
        assert data["message"] == "Correct! +2 bombs."
        assert mock_save.call_args[0][1].bombs_earned == 2


# ---------------------------------------------------------------------------
# /api/execute — code command mode gating
# ---------------------------------------------------------------------------


class TestCodeCommandModeGating:
    def _run(self, *, quiz_mode):
        from app.api.routes import app, verify_team_or_gm
        from app.game.state import GameState, GameStatusField

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": GAME_ID, "color": "red",
        }
        try:
            state = GameState()
            state.status = GameStatusField.STARTED
            state.teams["red"] = create_mock_team(bombs=0)
            state.location_codes[3] = "ABC123"

            location = MagicMock()
            location.quiz_mode = quiz_mode
            location.bomb_value = 10

            game = MagicMock()
            game.paused_until = None
            game.max_bombs = 100

            with patch("app.api.routes.GameState.from_events", return_value=state):
                with patch("app.models.get_game_events", return_value=[]):
                    with patch("app.api.routes.save_event") as mock_save:
                        with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute:
                            mock_execute.side_effect = [
                                MagicMock(scalar_one_or_none=MagicMock(return_value=location)),
                            ]
                            with patch("app.models.get_game", return_value=game):
                                response = TestClient(app).post("/api/execute", json={
                                    "team_color": "red",
                                    "command": "code",
                                    "args": {"location_number": 3, "code": "ABC123"},
                                })
            assert response.status_code == 200
            return response.json(), mock_save
        finally:
            app.dependency_overrides.clear()

    def test_quiz_only_location_rejects_the_code(self):
        data, mock_save = self._run(quiz_mode="quiz")
        assert data["success"] is False
        assert "quiz-only" in data["message"]
        assert not mock_save.called

    def test_both_mode_location_accepts_the_code(self):
        data, mock_save = self._run(quiz_mode="both")
        assert data["success"] is True
        assert mock_save.called

    def test_code_mode_location_accepts_the_code(self):
        data, mock_save = self._run(quiz_mode="code")
        assert data["success"] is True
        assert mock_save.called


# ---------------------------------------------------------------------------
# /api/location-quiz/state — team view hides answers until answered
# ---------------------------------------------------------------------------


class TestLocationQuizState:
    def _get(self, *, events):
        from app.api.routes import app, verify_team_or_gm

        app.dependency_overrides[verify_team_or_gm] = lambda: {
            "role": "team", "game_id": GAME_ID, "color": "red",
        }
        try:
            location = MagicMock()
            location.number = 3
            location.bomb_value = 10
            location.quiz_mode = "quiz"

            questions = [
                {
                    "id": 11,
                    "location_number": 3,
                    "question_text": "Where are we?",
                    "order": 0,
                    "bomb_value": 5,
                    "source_url": "https://example.com",
                    "answers": [
                        {"id": 1, "answer_text": "Here", "bomb_value": 5, "is_correct": True},
                        {"id": 2, "answer_text": "There", "bomb_value": 0, "is_correct": False},
                    ],
                }
            ]

            with patch("app.models.get_game_locations", new=AsyncMock(return_value=[location])):
                with patch("app.models.get_location_quiz_questions", new=AsyncMock(return_value=questions)):
                    with patch("app.models.get_game_events", new=AsyncMock(return_value=events)):
                        response = TestClient(app).get("/api/location-quiz/state")
            assert response.status_code == 200
            return response.json()
        finally:
            app.dependency_overrides.clear()

    def test_unanswered_question_hides_correct_answer_and_source(self):
        data = self._get(events=[])
        loc = data["locations"][0]
        assert loc["number"] == 3
        assert loc["question_count"] == 1
        assert loc["answered_count"] == 0

        q = loc["questions"][0]
        assert q["answered"] is False
        assert q["source_url"] is None
        assert all("is_correct" not in a for a in q["answers"])
        assert all("bomb_value" not in a for a in q["answers"])

    def test_answered_question_reveals_correct_answer_and_source(self):
        ev = MagicMock()
        ev.event_type = MagicMock(value="location_quiz_answered")
        ev.payload = {"color": "red", "question_id": 11, "location_number": 3}

        data = self._get(events=[ev])
        loc = data["locations"][0]
        assert loc["answered_count"] == 1

        q = loc["questions"][0]
        assert q["answered"] is True
        assert q["source_url"] == "https://example.com"
        correct = [a for a in q["answers"] if a.get("is_correct")]
        assert len(correct) == 1
        assert correct[0]["id"] == 1


# ---------------------------------------------------------------------------
# GM endpoints
# ---------------------------------------------------------------------------


class TestLocationQuizGmEndpoints:
    def test_save_rejects_all_zero_bomb_answers(self):
        from app.api.routes import app, verify_gm_token

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        try:
            client = TestClient(app)
            response = client.post("/api/location-quiz/questions", json={
                "location_number": 3,
                "questions": [
                    {
                        "question_text": "Where?",
                        "answers": [
                            {"answer_text": "A", "bomb_value": 0, "is_correct": True},
                            {"answer_text": "B", "bomb_value": 0, "is_correct": False},
                        ],
                    }
                ],
            })
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "no bomb-yielding answer" in data["message"]

    def test_set_mode_rejects_an_invalid_mode(self):
        from app.api.routes import app, verify_gm_token

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        try:
            client = TestClient(app)
            response = client.post("/api/quick/set_location_quiz_mode", json={
                "location_number": 3, "mode": "geofence",
            })
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Mode" in data["message"]


# ---------------------------------------------------------------------------
# /api/admin/locations overview
# ---------------------------------------------------------------------------


class TestAdminLocationsQuizColumns:
    def test_includes_mode_counts_and_counts_quiz_attempts_as_visits(self):
        from app.api.routes import app, verify_admin_or_gm
        from app.database import EventType

        app.dependency_overrides[verify_admin_or_gm] = lambda: {
            "role": "gm", "game_id": GAME_ID,
        }
        try:
            location = MagicMock()
            location.number = 3
            location.code = "ABC123"
            location.latitude = 51.5
            location.longitude = 5.3
            location.bomb_value = 10
            location.quiz_mode = "both"

            quiz_event = MagicMock()
            quiz_event.event_type = EventType.LOCATION_QUIZ_ANSWERED
            quiz_event.payload = {"color": "red", "location_number": 3, "question_id": 1}

            game = MagicMock()
            game.default_location_bombs = 10

            with patch("app.models.get_game_locations", new=AsyncMock(return_value=[location])):
                with patch("app.models.get_game_events", new=AsyncMock(return_value=[quiz_event])):
                    with patch("app.models.get_location_quiz_question_counts", new=AsyncMock(return_value={3: 2})):
                        with patch("app.models.get_game", new=AsyncMock(return_value=game)):
                            response = TestClient(app).get("/api/admin/locations")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        loc = response.json()["locations"][0]
        assert loc["quiz_mode"] == "both"
        assert loc["question_count"] == 2
        # A quiz attempt (right or wrong) marks the location visited.
        assert loc["visited_by"] == ["red"]
