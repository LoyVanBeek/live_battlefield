"""Tests for the reusable location libraries.

Two game-agnostic libraries let location setup be reused across games:
a location-quiz library (named check-in question sets) and location sets
(a named snapshot of a game's locations, codes, modes and quizzes).
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

GAME_ID = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# /api/location-quiz-templates — reusable location quizzes
# ---------------------------------------------------------------------------


class TestLocationQuizLibrary:
    def test_list_templates(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.list_location_quiz_templates", new_callable=AsyncMock) as mock_list:
                mock_list.return_value = [
                    {"id": 1, "name": "Museum", "question_count": 1, "total_bombs": 5, "updated_at": None},
                ]
                response = TestClient(app).get("/api/location-quiz-templates")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        templates = response.json()["templates"]
        assert templates[0]["name"] == "Museum"
        assert templates[0]["total_bombs"] == 5

    def test_get_not_found(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "gm", "game_id": GAME_ID}
        try:
            with patch("app.models.get_location_quiz_template", new_callable=AsyncMock, return_value=None):
                response = TestClient(app).get("/api/location-quiz-templates/999")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()

    def test_create_requires_name(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_quiz_template", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-quiz-templates", json={
                    "name": "   ",
                    "questions": [{"question_text": "Q", "answers": [
                        {"answer_text": "A", "bomb_value": 5, "is_correct": True}]}],
                })
            assert response.json()["success"] is False
            assert "name is required" in response.json()["message"].lower()
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_rejects_question_without_answers(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_quiz_template", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-quiz-templates", json={
                    "name": "Broken",
                    "questions": [{"question_text": "Empty Q", "answers": []}],
                })
            assert response.json()["success"] is False
            assert "has no answers" in response.json()["message"]
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_rejects_no_bomb_yielding_answer(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_quiz_template", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-quiz-templates", json={
                    "name": "ZeroBombs",
                    "questions": [{"question_text": "Capital?", "answers": [
                        {"answer_text": "Paris", "bomb_value": 0, "is_correct": True},
                    ]}],
                })
            assert response.json()["success"] is False
            assert "no bomb-yielding answer" in response.json()["message"]
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_accepts_and_forwards_id(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "gm", "game_id": GAME_ID}
        try:
            with patch("app.models.save_location_quiz_template", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = {"id": 7, "name": "Museum", "questions": []}
                response = TestClient(app).post("/api/location-quiz-templates", json={
                    "id": 7,
                    "name": "Museum",
                    "questions": [{"question_text": "Q", "answers": [
                        {"answer_text": "A", "bomb_value": 5, "is_correct": True}]}],
                })
            assert response.json()["success"] is True
            assert response.json()["template"]["id"] == 7
            assert mock_save.call_args.kwargs["template_id"] == 7
        finally:
            app.dependency_overrides.clear()

    def test_create_normalizes_source_url(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "gm", "game_id": GAME_ID}
        try:
            with patch("app.models.save_location_quiz_template", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = {"id": 1, "name": "Sourced", "questions": []}
                response = TestClient(app).post("/api/location-quiz-templates", json={
                    "name": "Sourced",
                    "questions": [
                        {"question_text": "Q1", "source_url": "example.com/wiki",
                         "answers": [{"answer_text": "A", "bomb_value": 5, "is_correct": True}]},
                        {"question_text": "Q2", "source_url": "   ",
                         "answers": [{"answer_text": "A", "bomb_value": 5, "is_correct": True}]},
                    ],
                })
            assert response.json()["success"] is True
            sent = mock_save.call_args.args[2]
            assert sent[0]["source_url"] == "https://example.com/wiki"
            assert sent[1]["source_url"] is None
        finally:
            app.dependency_overrides.clear()

    def test_delete_requires_auth(self):
        from app.api.routes import app

        admin = MagicMock()
        admin.token = "test_admin_token"
        with patch("app.models.get_admin", new_callable=AsyncMock, return_value=admin):
            with patch("app.models.get_game_by_gm_token", new_callable=AsyncMock, return_value=None):
                with patch("app.models.delete_location_quiz_template", new_callable=AsyncMock) as mock_delete:
                    response = TestClient(app).delete(
                        "/api/location-quiz-templates/1?token=wrong&gm_token=bad"
                    )
        assert response.status_code == 404
        mock_delete.assert_not_awaited()

    def test_delete_as_gm(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "gm", "game_id": GAME_ID}
        try:
            with patch("app.models.delete_location_quiz_template", new_callable=AsyncMock, return_value=True):
                response = TestClient(app).delete("/api/location-quiz-templates/1")
        finally:
            app.dependency_overrides.clear()

        assert response.json()["success"] is True


# ---------------------------------------------------------------------------
# /api/location-sets — reusable location layouts
# ---------------------------------------------------------------------------


class TestLocationSets:
    def test_list_sets(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.list_location_sets", new_callable=AsyncMock) as mock_list:
                mock_list.return_value = [
                    {"id": 1, "name": "City", "location_count": 3, "quiz_count": 1, "updated_at": None},
                ]
                response = TestClient(app).get("/api/location-sets")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 200
        sets = response.json()["sets"]
        assert sets[0]["name"] == "City"
        assert sets[0]["location_count"] == 3

    def test_get_not_found(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.get_location_set", new_callable=AsyncMock, return_value=None):
                response = TestClient(app).get("/api/location-sets/999")
        finally:
            app.dependency_overrides.clear()

        assert response.json()["success"] is False
        assert "not found" in response.json()["message"].lower()

    def test_delete_requires_auth(self):
        from app.api.routes import app

        admin = MagicMock()
        admin.token = "test_admin_token"
        with patch("app.models.get_admin", new_callable=AsyncMock, return_value=admin):
            with patch("app.models.get_game_by_gm_token", new_callable=AsyncMock, return_value=None):
                with patch("app.models.delete_location_set", new_callable=AsyncMock) as mock_delete:
                    response = TestClient(app).delete("/api/location-sets/1?token=wrong&gm_token=bad")
        assert response.status_code == 404
        mock_delete.assert_not_awaited()

    def test_save_requires_name(self):
        from app.api.routes import app, verify_gm_token

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        try:
            with patch("app.models.save_locations_as_set", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/quick/save-location-set", json={"name": "  "})
            assert response.json()["success"] is False
            assert "name is required" in response.json()["message"].lower()
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_save_without_locations(self):
        from app.api.routes import app, verify_gm_token

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        try:
            with patch("app.models.save_locations_as_set", new_callable=AsyncMock, return_value=None):
                response = TestClient(app).post("/api/quick/save-location-set", json={"name": "Empty"})
            assert response.json()["success"] is False
            assert "no locations" in response.json()["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_save_success(self):
        from app.api.routes import app, verify_gm_token

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        try:
            with patch("app.models.save_locations_as_set", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = {"id": 4, "name": "City", "locations": [{"number": 1}, {"number": 2}]}
                response = TestClient(app).post("/api/quick/save-location-set", json={"name": "City"})
            assert response.json()["success"] is True
            assert response.json()["set"]["id"] == 4
        finally:
            app.dependency_overrides.clear()

    def test_apply_not_found(self):
        from app.api.routes import app, verify_gm_token

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        try:
            with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                with patch("app.models.apply_location_set", new_callable=AsyncMock, return_value=None):
                    response = TestClient(app).post("/api/quick/apply-location-set", json={"set_id": 5})
            assert response.json()["success"] is False
            assert "not found" in response.json()["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_apply_rejected_after_start(self):
        from app.api.routes import app, verify_gm_token
        from app.game.state import GameStatusField

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        try:
            with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                with patch("app.api.routes.GameState.from_events") as mock_from_events:
                    mock_from_events.return_value = MagicMock(status=GameStatusField.STARTED)
                    with patch("app.models.apply_location_set", new_callable=AsyncMock) as mock_apply:
                        response = TestClient(app).post("/api/quick/apply-location-set", json={"set_id": 5})
            assert response.json()["success"] is False
            assert "already started" in response.json()["message"].lower()
            mock_apply.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_apply_success(self):
        from app.api.routes import app, verify_gm_token

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        try:
            with patch("app.models.get_game_events", new_callable=AsyncMock, return_value=[]):
                with patch("app.models.apply_location_set", new_callable=AsyncMock) as mock_apply:
                    mock_apply.return_value = {"id": 5, "name": "City", "locations": [{"number": 1, "code": "ABC"}]}
                    response = TestClient(app).post("/api/quick/apply-location-set", json={"set_id": 5})
            assert response.json()["success"] is True
            assert response.json()["locations"][0]["code"] == "ABC"
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# clear-locations emits removal events (event-derived codes must not go stale)
# ---------------------------------------------------------------------------


class TestClearLocationsState:
    def test_clear_locations_emits_removal_events(self):
        from app.api.routes import app, verify_gm_token

        app.dependency_overrides[verify_gm_token] = lambda: GAME_ID
        loc1 = MagicMock(number=1, bomb_value=5)
        loc2 = MagicMock(number=2, bomb_value=7)
        try:
            with patch("app.models.get_game_locations", new_callable=AsyncMock, return_value=[loc1, loc2]):
                with patch("app.models.delete_all_locations", new_callable=AsyncMock, return_value=2):
                    with patch("app.api.routes.save_event", new_callable=AsyncMock) as mock_save:
                        response = TestClient(app).post("/api/quick/clear-locations")
        finally:
            app.dependency_overrides.clear()

        assert response.json()["success"] is True
        assert mock_save.await_count == 2
        numbers = sorted(call.args[1].number for call in mock_save.await_args_list)
        assert numbers == [1, 2]
