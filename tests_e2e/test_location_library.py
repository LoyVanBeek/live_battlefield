"""E2E coverage for the reusable location sets library.

A location set is a named layout (positions, codes, bombs, modes) plus each
location's check-in quiz. Sets are authored in the admin editor or snapshotted
from a game's locations page, then applied to any game.
"""

import httpx

from tests_e2e.config import HTTPX_TIMEOUT
from tests_e2e.pages.admin_dashboard import AdminDashboardPage
from tests_e2e.pages.location_set_editor import LocationSetEditorPage
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


def test_location_set_round_trip(app_url, admin_token):
    """Create a set (with a quiz) via the API, load it, rename it, delete it."""
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/location-sets",
            params={"token": admin_token},
            json={
                "name": "E2E Set",
                "locations": [
                    {
                        "number": 1,
                        "latitude": 52.1,
                        "longitude": 4.3,
                        "code": "",
                        "bomb_value": 5,
                        "quiz_mode": "quiz",
                        "questions": QUIZ,
                    }
                ],
            },
        )
        assert resp.json()["success"] is True, resp.text
        set_id = resp.json()["set"]["id"]
        # A blank code is generated for the set location.
        assert resp.json()["set"]["locations"][0]["code"]

        listed = client.get("/api/location-sets", params={"token": admin_token}).json()["sets"]
        assert any(s["id"] == set_id and s["name"] == "E2E Set" for s in listed)

        full = client.get(
            f"/api/location-sets/{set_id}", params={"token": admin_token}
        ).json()["set"]
        assert full["locations"][0]["questions"][0]["question_text"] == "Where are we?"
        assert full["locations"][0]["questions"][0]["answers"][0]["is_correct"] is True

        # PUT updates in place, allowing a rename.
        resp = client.put(
            f"/api/location-sets/{set_id}",
            params={"token": admin_token},
            json={
                "name": "E2E Set Renamed",
                "locations": [
                    {
                        "number": 2,
                        "latitude": 51.0,
                        "longitude": 5.0,
                        "code": "ADMIN2",
                        "bomb_value": 3,
                        "quiz_mode": "both",
                        "questions": [],
                    }
                ],
            },
        )
        assert resp.json()["success"] is True, resp.text
        assert resp.json()["set"]["id"] == set_id
        assert resp.json()["set"]["locations"][0]["code"] == "ADMIN2"

        renamed = client.get(
            f"/api/location-sets/{set_id}", params={"token": admin_token}
        ).json()["set"]
        assert renamed["name"] == "E2E Set Renamed"
        assert [loc["number"] for loc in renamed["locations"]] == [2]
        assert renamed["locations"][0]["code"] == "ADMIN2"
        assert renamed["locations"][0]["quiz_mode"] == "both"
        # The PUT payload replaces the previous locations and quiz, not merges.
        assert renamed["locations"][0]["questions"] == []


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


def test_quiz_modal_loads_from_set(page, app_url, admin_token, seeded_game_with_locations):
    """The quiz modal's Load pulls a location's quiz out of a set (number-matched)."""
    gm = seeded_game_with_locations["gm_token"]
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/location-sets",
            params={"token": admin_token},
            json={
                "name": "E2E Modal Set",
                "locations": [{
                    "number": 1,
                    "latitude": 52.1,
                    "longitude": 4.3,
                    "code": "MODAL1",
                    "bomb_value": 5,
                    "quiz_mode": "both",
                    "questions": [{
                        "question_text": "Loaded from set?",
                        "answers": [{"answer_text": "Yes", "bomb_value": 4, "is_correct": True}],
                    }],
                }],
            },
        )
        assert resp.json()["success"] is True, resp.text
        set_id = resp.json()["set"]["id"]

    lp = LocationsPage(page, gm, app_url=app_url)
    lp.goto()
    lp.open_quiz_modal(1)  # number-matched to the set's location 1

    page.wait_for_function(
        "() => document.querySelectorAll('#lq-set-select option').length >= 2"
    )
    lp.quiz_set_select().select_option(str(set_id))
    lp.load_set_quiz_button().click()
    page.wait_for_function(
        """() => {
            const i = document.querySelector("#lq-questions-list input[data-role='question-text']");
            return !!i && i.value === 'Loaded from set?';
        }"""
    )

    assert lp.quiz_question_text_input(0).input_value() == "Loaded from set?"


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


def test_admin_set_editor(page, app_url, admin_token):
    """Author a set, with a per-location quiz, on the full-page editor."""
    se = LocationSetEditorPage(page, admin_token, app_url=app_url)
    se.goto()

    se.set_name_input().fill("E2E Admin Set")
    se.add_location("52.1", "4.3")

    se.edit_cell("code", 1, "ADMINSET1")
    se.edit_cell("bombs", 1, "7")

    se.open_quiz_modal(1)
    se.set_quiz_mode("both")
    se.add_quiz_question()
    se.set_quiz_question_text(0, "Admin authored?")
    se.set_quiz_answer_text(0, 0, "Yes")
    se.set_quiz_answer_bombs(0, 0, 3)
    # Saving the quiz only closes the modal; the set itself is saved next.
    page.locator("#lq-modal button", has_text="Save Quiz").click()
    page.wait_for_function(
        "() => document.getElementById('lq-modal').style.display === 'none'"
    )

    se.save()
    page.wait_for_function("() => window.location.search.startsWith('?id=')")

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        sets = client.get(
            "/api/location-sets", params={"token": admin_token}
        ).json()["sets"]
        mine = next(s for s in sets if s["name"] == "E2E Admin Set")
        assert mine["location_count"] == 1
        assert mine["quiz_count"] == 1
        full = client.get(
            f"/api/location-sets/{mine['id']}", params={"token": admin_token}
        ).json()["set"]
        loc = full["locations"][0]
        assert loc["code"] == "ADMINSET1"
        assert loc["bomb_value"] == 7
        assert loc["quiz_mode"] == "both"
        assert loc["questions"][0]["question_text"] == "Admin authored?"
        assert loc["questions"][0]["answers"][0]["is_correct"] is True

    # Reloading the saved set restores the draft (name, code, quiz).
    se.goto(set_id=mine["id"])
    assert se.set_name_input().input_value() == "E2E Admin Set"
    assert se.code_cell(1).inner_text().strip() == "ADMINSET1"
    assert se.get_location_count() == 1

    # Delete from the editor and land back on the dashboard.
    se.delete()
    page.wait_for_url(f"{app_url}/admin/{admin_token}")


def test_dashboard_edit_set_opens_editor(page, app_url, admin_token):
    """The dashboard's Edit button navigates to the full-page set editor."""
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/location-sets",
            params={"token": admin_token},
            json={
                "name": "E2E Nav Set",
                "locations": [{
                    "number": 1,
                    "latitude": 52.0,
                    "longitude": 4.0,
                    "code": "NAV1",
                    "bomb_value": 2,
                    "quiz_mode": "code",
                    "questions": [],
                }],
            },
        )
        assert resp.json()["success"] is True, resp.text
        set_id = resp.json()["set"]["id"]

    ap = AdminDashboardPage(page, admin_token, app_url=app_url)
    ap.goto()
    ap.edit_set("E2E Nav Set")
    page.wait_for_url(f"{app_url}/admin/{admin_token}/location-sets?id={set_id}")
    assert page.locator("#set-name").input_value() == "E2E Nav Set"
    assert page.locator("#cell-code-1").inner_text().strip() == "NAV1"


def test_set_editor_map_click_adds_location(page, app_url, admin_token):
    """Clicking the map adds a pin to the draft (nothing saved yet)."""
    se = LocationSetEditorPage(page, admin_token, app_url=app_url)
    se.goto()
    assert se.get_location_count() == 0

    se.map_element().click(position={"x": 300, "y": 200})
    page.wait_for_function(
        "() => document.querySelectorAll('#locations-body tr').length === 1"
    )
    assert se.get_location_count() == 1
    assert se.pins().count() == 1
    assert "Unsaved" in se.status_text().inner_text()


def test_set_editor_requires_name_and_a_location(page, app_url, admin_token):
    """The editor blocks a nameless or empty set client-side."""
    se = LocationSetEditorPage(page, admin_token, app_url=app_url)
    se.goto()

    se.save()
    page.wait_for_function(
        "() => document.getElementById('toast').classList.contains('error')"
    )
    assert "name" in se.toast().text_content().lower()

    se.set_name_input().fill("E2E Empty Set")
    se.save()
    page.wait_for_function(
        "() => document.getElementById('toast').classList.contains('error')"
    )
    assert "location" in se.toast().text_content().lower()
