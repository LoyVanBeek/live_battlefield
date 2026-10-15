"""Tests for the reusable location library.

One game-agnostic library lets a whole location layout be reused across games:
a location set (a named snapshot of locations, codes, modes and each location's
check-in quiz). Sets can be authored in the admin editor or snapshotted from a
game's locations page.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

GAME_ID = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# /api/location-sets (POST/PUT) — authoring a set directly
# ---------------------------------------------------------------------------


class TestLocationSetEditor:
    """POST/PUT /api/location-sets — authoring a set (with quizzes) directly."""

    def _location(self, **overrides):
        loc = {
            "number": 1,
            "latitude": 52.1,
            "longitude": 4.3,
            "code": "ABC123",
            "bomb_value": 5,
            "quiz_mode": "both",
            "questions": [],
        }
        loc.update(overrides)
        return loc

    def test_create_requires_name(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-sets", json={
                    "name": "   ", "locations": [self._location()],
                })
            assert response.json()["success"] is False
            assert "name is required" in response.json()["message"].lower()
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_requires_a_location(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-sets", json={"name": "Empty", "locations": []})
            assert response.json()["success"] is False
            assert "at least one location" in response.json()["message"].lower()
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_rejects_missing_coordinates(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-sets", json={
                    "name": "Nowhere", "locations": [self._location(latitude=None)],
                })
            assert response.json()["success"] is False
            assert "valid latitude and longitude" in response.json()["message"]
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_rejects_unknown_mode(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-sets", json={
                    "name": "Weird", "locations": [self._location(quiz_mode="telepathy")],
                })
            assert response.json()["success"] is False
            assert "invalid quiz mode" in response.json()["message"]
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_rejects_duplicate_numbers(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-sets", json={
                    "name": "Dupes",
                    "locations": [self._location(number=1), self._location(number=1)],
                })
            assert response.json()["success"] is False
            assert "unique" in response.json()["message"].lower()
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_rejects_quiz_without_bombs(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock) as mock_save:
                response = TestClient(app).post("/api/location-sets", json={
                    "name": "NoBombs",
                    "locations": [self._location(questions=[{
                        "question_text": "Capital?", "answers": [
                            {"answer_text": "Paris", "bomb_value": 0, "is_correct": True}],
                    }])],
                })
            assert response.json()["success"] is False
            assert "Location 1: Question 1" in response.json()["message"]
            mock_save.assert_not_awaited()
        finally:
            app.dependency_overrides.clear()

    def test_create_forwards_locations_and_normalizes_source_url(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "gm", "game_id": GAME_ID}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = {"id": 7, "name": "City", "locations": []}
                response = TestClient(app).post("/api/location-sets", json={
                    "name": "City",
                    "locations": [self._location(questions=[
                        {"question_text": "Q1", "source_url": "example.com/wiki", "answers": [
                            {"answer_text": "A", "bomb_value": 5, "is_correct": True}]},
                        {"question_text": "Q2", "source_url": "   ", "answers": [
                            {"answer_text": "A", "bomb_value": 5, "is_correct": True}]},
                    ])],
                })
            assert response.json()["success"] is True
            assert response.json()["set"]["id"] == 7
            assert mock_save.call_args.kwargs["set_id"] is None
            sent = mock_save.call_args.args[2]
            assert sent[0]["questions"][0]["source_url"] == "https://example.com/wiki"
            assert sent[0]["questions"][1]["source_url"] is None
        finally:
            app.dependency_overrides.clear()

    def test_update_forwards_set_id(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock) as mock_save:
                mock_save.return_value = {"id": 7, "name": "Renamed", "locations": []}
                response = TestClient(app).put("/api/location-sets/7", json={
                    "name": "Renamed", "locations": [self._location()],
                })
            assert response.json()["success"] is True
            assert mock_save.call_args.kwargs["set_id"] == 7
        finally:
            app.dependency_overrides.clear()

    def test_update_not_found(self):
        from app.api.routes import app, verify_admin_or_gm

        app.dependency_overrides[verify_admin_or_gm] = lambda: {"role": "admin"}
        try:
            with patch("app.models.save_location_set", new_callable=AsyncMock, return_value=None):
                response = TestClient(app).put("/api/location-sets/999", json={
                    "name": "Ghost", "locations": [self._location()],
                })
            assert response.json()["success"] is False
            assert "not found" in response.json()["message"].lower()
        finally:
            app.dependency_overrides.clear()


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
