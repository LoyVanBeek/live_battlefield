"""E2E coverage for the reusable location libraries.

Two game-agnostic libraries let location setup be reused across games:
a location-quiz library (named check-in question sets) and location sets
(a named snapshot of a game's locations, codes, modes and quizzes).
"""

import httpx

from tests_e2e.config import HTTPX_TIMEOUT
from tests_e2e.pages.locations_page import LocationsPage

QUIZ = [
    {
        "question_text": "Where are we?",
        "answers": [
            {"answer_text": "The museum", "bomb_value": 5, "is_correct": True},
            {"answer_text": "The station", "bomb_value": 0, "is_correct": False},
        ],
    }
]


def _locations(client, gm_token):
    return client.get(
        "/api/admin/locations", params={"gm_token": gm_token}
    ).json()["locations"]


def test_location_quiz_library_round_trip(app_url, seeded_game_with_locations):
    """Save a location quiz, list/load it, overwrite by name, then delete it."""
    gm = seeded_game_with_locations["gm_token"]
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/location-quiz-templates",
            params={"gm_token": gm},
            json={"name": "E2E Check-in", "questions": QUIZ},
        )
        assert resp.json()["success"] is True, resp.text
        template_id = resp.json()["template"]["id"]

        listed = client.get(
            "/api/location-quiz-templates", params={"gm_token": gm}
        ).json()["templates"]
        assert any(t["id"] == template_id and t["name"] == "E2E Check-in" for t in listed)

        full = client.get(
            f"/api/location-quiz-templates/{template_id}", params={"gm_token": gm}
        ).json()["template"]
        assert full["questions"][0]["question_text"] == "Where are we?"
        assert full["questions"][0]["answers"][0]["is_correct"] is True

        # Saving under the same name overwrites rather than duplicating.
        resp = client.post(
            "/api/location-quiz-templates",
            params={"gm_token": gm},
            json={
                "name": "E2E Check-in",
                "questions": [
                    {
                        "question_text": "Replaced?",
                        "answers": [
                            {"answer_text": "Yes", "bomb_value": 3, "is_correct": True}
                        ],
                    }
                ],
            },
        )
        assert resp.json()["success"] is True, resp.text

        listed = client.get(
            "/api/location-quiz-templates", params={"gm_token": gm}
        ).json()["templates"]
        matches = [t for t in listed if t["name"] == "E2E Check-in"]
        assert len(matches) == 1
        # Overwriting by name replaces the row, so the id changes.
        new_id = matches[0]["id"]

        resp = client.delete(
            f"/api/location-quiz-templates/{new_id}", params={"gm_token": gm}
        )
        assert resp.json()["success"] is True, resp.text


def test_location_set_apply_restores_codes_modes_and_quiz(
    app_url, admin_token, seeded_game_with_locations
):
    """Snapshot a layout, then apply it to another game (replace-all, 1:1)."""
    gm_a = seeded_game_with_locations["gm_token"]
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        # Author a quiz on location 1 and make it offer both code and quiz.
        resp = client.post(
            "/api/location-quiz/questions",
            params={"gm_token": gm_a},
            json={"location_number": 1, "questions": QUIZ},
        )
        assert resp.json()["success"] is True, resp.text
        client.post(
            "/api/quick/set_location_quiz_mode",
            params={"gm_token": gm_a},
            json={"location_number": 1, "mode": "both"},
        )

        before = {loc["number"]: loc for loc in _locations(client, gm_a)}

        resp = client.post(
            "/api/quick/save-location-set",
            params={"gm_token": gm_a},
            json={"name": "E2E Layout"},
        )
        assert resp.json()["success"] is True, resp.text
        set_id = resp.json()["set"]["id"]

        # A fresh game with a junk location that must be replaced.
        gm_b = client.post(
            "/api/admin/create-game", params={"token": admin_token}
        ).json()["token"]
        client.post(
            "/api/quick/create_locations",
            params={"gm_token": gm_b},
            json={"latitude": 1.0, "longitude": 1.0, "count": 1, "radius_km": 0},
        )

        resp = client.post(
            "/api/quick/apply-location-set",
            params={"gm_token": gm_b},
            json={"set_id": set_id},
        )
        assert resp.json()["success"] is True, resp.text

        after = _locations(client, gm_b)
        assert len(after) == len(before)
        for loc in after:
            src = before[loc["number"]]
            assert loc["code"] == src["code"]
            assert loc["quiz_mode"] == src["quiz_mode"]
            assert loc["question_count"] == src["question_count"]
            assert loc["bomb_value"] == src["bomb_value"]
            assert round(loc["latitude"], 6) == round(src["latitude"], 6)
            assert round(loc["longitude"], 6) == round(src["longitude"], 6)

        # The quiz itself came across.
        quiz = client.get(
            "/api/location-quiz/questions",
            params={"gm_token": gm_b, "location_number": 1},
        ).json()
        assert quiz["success"] is True
        assert quiz["mode"] == "both"
        assert quiz["questions"][0]["question_text"] == "Where are we?"
        assert quiz["questions"][0]["answers"][0]["is_correct"] is True


def test_reused_code_redeems_after_applying_set(
    app_url, seeded_game_with_locations, seeded_game_with_teams
):
    """A saved set remembers its codes; re-applying them keeps them redeemable."""
    gm_a = seeded_game_with_locations["gm_token"]
    seed_b = seeded_game_with_teams
    gm_b = seed_b["gm_token"]
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        codes = {loc["number"]: loc["code"] for loc in _locations(client, gm_a)}

        resp = client.post(
            "/api/quick/save-location-set",
            params={"gm_token": gm_a},
            json={"name": "E2E Redeem"},
        )
        assert resp.json()["success"] is True, resp.text
        set_id = resp.json()["set"]["id"]

        resp = client.post(
            "/api/quick/apply-location-set",
            params={"gm_token": gm_b},
            json={"set_id": set_id},
        )
        assert resp.json()["success"] is True, resp.text

        resp = client.post("/api/quick/start-game", params={"gm_token": gm_b})
        assert resp.json().get("success") is True, resp.text

        after = _locations(client, gm_b)
        loc1 = next(loc for loc in after if loc["number"] == 1)
        assert loc1["code"] == codes[1], "applied set must reuse the saved code"

        resp = client.post(
            "/api/execute",
            params={"team_token": seed_b["teams"]["red"]["token"]},
            json={
                "team_color": "red",
                "command": "code",
                "args": {"location_number": 1, "code": codes[1]},
            },
        )
        assert resp.json().get("success") is True, resp.text

        loc1 = next(loc for loc in _locations(client, gm_b) if loc["number"] == 1)
        assert "red" in loc1["visited_by"]


def test_apply_set_rejected_after_start(app_url, seeded_game_with_teams):
    gm = seeded_game_with_teams["gm_token"]
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        set_id = client.post(
            "/api/quick/save-location-set",
            params={"gm_token": gm},
            json={"name": "E2E Started"},
        ).json()["set"]["id"]

        client.post("/api/quick/start-game", params={"gm_token": gm})
        resp = client.post(
            "/api/quick/apply-location-set",
            params={"gm_token": gm},
            json={"set_id": set_id},
        )
        assert resp.json()["success"] is False
        assert "already started" in resp.json()["message"].lower()


def test_quiz_modal_loads_from_library(page, app_url, seeded_game_with_locations):
    gm = seeded_game_with_locations["gm_token"]
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/location-quiz-templates",
            params={"gm_token": gm},
            json={"name": "E2E Modal Quiz", "questions": QUIZ},
        )
        assert resp.json()["success"] is True, resp.text
        template_id = resp.json()["template"]["id"]

    lp = LocationsPage(page, gm, app_url=app_url)
    lp.goto()
    lp.open_quiz_modal(3)  # a location without a quiz yet

    # The library select fills with the saved quiz.
    page.wait_for_function(
        "() => document.querySelectorAll('#lq-library-select option').length >= 2"
    )
    # Select this test's quiz by id (the library is shared across tests).
    lp.quiz_library_select().select_option(str(template_id))
    lp.load_library_quiz_button().click()
    page.wait_for_function(
        "() => document.querySelectorAll('#lq-questions-list .quiz-question').length >= 1"
    )

    assert lp.quiz_question_text_input(0).input_value() == "Where are we?"


def test_save_current_as_set_from_ui(page, app_url, seeded_game_with_locations):
    gm = seeded_game_with_locations["gm_token"]
    lp = LocationsPage(page, gm, app_url=app_url)
    lp.goto()

    page.once("dialog", lambda dialog: dialog.accept("E2E UI Set"))
    lp.save_set_button().click()
    page.wait_for_function(
        "() => Array.from(document.querySelectorAll('#location-set-select option'))"
        ".some(o => o.textContent.includes('E2E UI Set'))"
    )

    # Delete it again (confirm dialog).
    options = lp.location_set_select().locator("option")
    # select the option whose text contains the name
    for i in range(options.count()):
        if "E2E UI Set" in options.nth(i).text_content():
            lp.location_set_select().select_option(index=i)
            break

    page.once("dialog", lambda dialog: dialog.accept())
    lp.delete_set_button().click()
    page.wait_for_function(
        "() => !Array.from(document.querySelectorAll('#location-set-select option'))"
        ".some(o => o.textContent.includes('E2E UI Set'))"
    )
