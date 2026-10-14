"""E2E coverage for location quizzes — check-in without posting codes.

A location can be set to quiz mode, given questions on the GM Locations page,
and answered by a team from their team page (honour system, no geolocation).
"""

import httpx

from tests_e2e.config import HTTPX_TIMEOUT
from tests_e2e.pages.locations_page import LocationsPage
from tests_e2e.pages.team_page import TeamPage


def _set_quiz_and_start(client, gm_token: str) -> None:
    """Make location 1 a one-question quiz location and start the game."""
    resp = client.post(
        "/api/location-quiz/questions",
        params={"gm_token": gm_token},
        json={
            "location_number": 1,
            "questions": [
                {
                    "question_text": "What colour is a clear daytime sky?",
                    "source_url": "https://example.com/sky",
                    "answers": [
                        {"answer_text": "Blue", "bomb_value": 5, "is_correct": True},
                        {"answer_text": "Green", "bomb_value": 0, "is_correct": False},
                    ],
                }
            ],
        },
    )
    assert resp.json().get("success") is True, resp.text

    resp = client.post(
        "/api/quick/set_location_quiz_mode",
        params={"gm_token": gm_token},
        json={"location_number": 1, "mode": "quiz"},
    )
    assert resp.json().get("success") is True, resp.text

    resp = client.post("/api/quick/start-game", params={"gm_token": gm_token})
    assert resp.json().get("success") is True, resp.text


def test_location_quiz_correct_answer_reveals_source(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        _set_quiz_and_start(client, seed["gm_token"])

    tp = TeamPage(page, seed["team_urls"]["blue"], app_url)
    tp.goto()

    tp.location_quiz_section().wait_for(state="visible", timeout=15000)
    page.wait_for_function(
        "() => document.getElementById('location-quiz-content') && "
        "document.getElementById('location-quiz-content').querySelector('button.btn-primary')",
        timeout=10000,
    )
    assert "sky" in tp.location_quiz_content().text_content().lower()
    # The verifying link must not be exposed before answering.
    assert tp.location_quiz_source_link().count() == 0

    tp.answer_location_quiz(0)  # "Blue" — correct

    verdict = tp.location_quiz_verdict()
    verdict.wait_for(state="visible", timeout=10000)
    assert "Correct" in verdict.text_content()
    assert "Blue" in tp.location_quiz_correct_answer().text_content()
    link = tp.location_quiz_source_link()
    assert link.count() == 1
    assert link.get_attribute("href") == "https://example.com/sky"

    # Answering once exhausts the location; the section reports it as done.
    tp.next_location_quiz_question()
    page.wait_for_function(
        "() => document.getElementById('location-quiz-content').textContent.includes('answered')",
        timeout=10000,
    )


def test_location_quiz_wrong_answer_still_counts_as_visited(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        _set_quiz_and_start(client, seed["gm_token"])

    tp = TeamPage(page, seed["team_urls"]["red"], app_url)
    tp.goto()
    tp.location_quiz_section().wait_for(state="visible", timeout=15000)
    page.wait_for_function(
        "() => document.getElementById('location-quiz-content') && "
        "document.getElementById('location-quiz-content').querySelector('button.btn-primary')",
        timeout=10000,
    )

    tp.answer_location_quiz(1)  # "Green" — wrong

    verdict = tp.location_quiz_verdict()
    verdict.wait_for(state="visible", timeout=10000)
    assert "Wrong" in verdict.text_content()

    # Right or wrong, the attempt marks the location visited for that team.
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        locations = client.get(
            "/api/admin/locations", params={"gm_token": seed["gm_token"]}
        ).json()["locations"]
    loc1 = next(loc for loc in locations if loc["number"] == 1)
    assert "red" in loc1["visited_by"]
    assert loc1["quiz_mode"] == "quiz"
    assert loc1["question_count"] == 1


def test_deleting_a_game_with_a_location_quiz_succeeds(app_url, admin_token, seeded_game_with_teams):
    """Regression: location-quiz rows must be cleared so the game_id FK doesn't
    block game deletion."""
    seed = seeded_game_with_teams
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/location-quiz/questions",
            params={"gm_token": seed["gm_token"]},
            json={
                "location_number": 1,
                "questions": [
                    {
                        "question_text": "Delete me?",
                        "answers": [
                            {"answer_text": "Yes", "bomb_value": 1, "is_correct": True},
                            {"answer_text": "No", "bomb_value": 0, "is_correct": False},
                        ],
                    }
                ],
            },
        )
        assert resp.json().get("success") is True, resp.text

        games = client.get(
            "/api/admin/games", params={"token": admin_token}
        ).json()["games"]
        gid = next(g["id"] for g in games if g["gm_token"] == seed["gm_token"])

        resp = client.request(
            "DELETE",
            "/api/admin/games",
            params={"token": admin_token},
            json={"game_ids": [gid]},
        )
        assert resp.json()["results"][gid] is True, resp.text


def test_gm_authors_a_location_quiz_via_modal(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    lp.quiz_cell(1).wait_for(state="visible", timeout=10000)
    lp.open_quiz_modal(1)

    lp.add_quiz_question()
    lp.set_quiz_question_text(0, "Capital of France?")
    lp.set_quiz_answer_text(0, 0, "Paris")
    lp.add_quiz_answer(0)
    lp.set_quiz_answer_text(0, 1, "London")
    lp.set_quiz_answer_bombs(0, 0, 5)
    lp.set_quiz_mode("quiz")
    lp.save_quiz()

    # The row now advertises the mode and the question count.
    cell = lp.quiz_cell(1)
    cell.wait_for(state="visible", timeout=10000)
    assert "Quiz" in cell.text_content()
    assert "(1)" in cell.text_content()

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        data = client.get(
            "/api/location-quiz/questions",
            params={"gm_token": seed["gm_token"], "location_number": 1},
        ).json()

    assert data["success"] is True
    assert data["mode"] == "quiz"
    assert len(data["questions"]) == 1
    q = data["questions"][0]
    assert q["question_text"] == "Capital of France?"
    assert q["answers"][0]["is_correct"] is True
    assert q["answers"][0]["bomb_value"] == 5
