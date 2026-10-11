"""E2E: reusable quiz library.

A quiz authored once on the admin dashboard (or saved from a game) can be loaded
into any future game, which is the whole point of the feature.
"""

import httpx

from tests_e2e.config import HTTPX_TIMEOUT
from tests_e2e.pages.admin_dashboard import AdminDashboardPage
from tests_e2e.pages.game_settings_page import GameSettingsPage


def _create_game(app_url, admin_token):
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        return resp.json()["token"]


def _create_template(app_url, admin_token, name, questions):
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/quiz-templates",
            params={"token": admin_token},
            json={"name": name, "questions": questions},
        )
        assert resp.json().get("success"), resp.text
        return resp.json()["template"]


def _templates(app_url, admin_token):
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        return client.get("/api/quiz-templates", params={"token": admin_token}).json()["templates"]


def _game_questions(app_url, gm_token):
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        data = client.get("/api/quiz/questions", params={"gm_token": gm_token}).json()
    return data.get("questions") or []


def test_admin_authors_library_quiz_then_reused_in_two_games(page, app_url, admin_token):
    admin = AdminDashboardPage(page, admin_token, app_url)
    admin.goto()

    admin.open_new_library_quiz("Capitals")
    admin.add_library_question("Capital of France?", [
        {"text": "Paris", "correct": True},
        {"text": "London", "correct": False},
    ])
    admin.add_library_question("Capital of Spain?", [
        {"text": "Madrid", "correct": True},
        {"text": "Barcelona", "correct": False},
    ])
    admin.set_library_total(10)
    admin.rebalance_library()
    admin.save_library_quiz()

    admin.select_library_quiz("Capitals")
    assert "Capitals" in admin.library_quiz_list().text_content()

    # The same saved quiz is reused in two entirely separate games.
    for _ in range(2):
        gm_token = _create_game(app_url, admin_token)
        gs = GameSettingsPage(page, gm_token, app_url)
        gs.goto()
        gs.enable_quiz(10)
        gs.load_library_quiz("Capitals")
        page.wait_for_function(
            'document.getElementById("quiz-total").value === "10"', timeout=5000
        )
        assert gs.question_blocks().count() == 2

        gs.save_quiz()
        questions = _game_questions(app_url, gm_token)
        assert [q["bomb_value"] for q in questions] == [5, 5], questions
        assert questions[0]["answers"][0]["answer_text"] == "Paris"


def test_save_as_library_quiz_from_game_settings(page, app_url, admin_token):
    gm_token = _create_game(app_url, admin_token)
    gs = GameSettingsPage(page, gm_token, app_url)
    gs.goto()
    gs.enable_quiz(12)
    for i in range(2):
        gs.add_question(f"Q{i+1}", [
            {"text": "A", "correct": True},
            {"text": "B", "correct": False},
        ])
    gs.rebalance_bombs()
    page.wait_for_function('document.getElementById("quiz-total").value === "12"', timeout=5000)

    gs.save_as_library_quiz("GameMade")

    made = [t for t in _templates(app_url, admin_token) if t["name"] == "GameMade"]
    assert made, "quiz saved from game settings did not appear in the library"
    assert made[0]["question_count"] == 2
    assert made[0]["total_bombs"] == 12


def test_admin_renames_overwrites_and_deletes_library_quiz(page, app_url, admin_token):
    _create_template(app_url, admin_token, "Alpha", [
        {"question_text": "Q1", "answers": [
            {"answer_text": "A", "bomb_value": 4, "is_correct": True},
            {"answer_text": "B", "bomb_value": 0, "is_correct": False},
        ]},
    ])

    admin = AdminDashboardPage(page, admin_token, app_url)
    admin.goto()
    admin.select_library_quiz("Alpha")
    admin.edit_selected_library_quiz()
    admin.library_name_input().fill("Alpha Renamed")
    admin.save_library_quiz()

    names = [t["name"] for t in _templates(app_url, admin_token)]
    assert "Alpha Renamed" in names
    assert "Alpha" not in names, "renaming must not leave the old name behind"

    admin.select_library_quiz("Alpha Renamed")
    admin.delete_selected_library_quiz()
    names = [t["name"] for t in _templates(app_url, admin_token)]
    assert "Alpha Renamed" not in names


def test_admin_import_shows_readable_answer_text(page, app_url, admin_token):
    """Imported answers must be visible.

    Regression: the admin page's global `input { width: 100% }` rule once made the
    correct-answer radio eat the flex row, squashing the answer text inputs to ~14px
    (text present but unreadable). Assert both the value round-trips and the input
    is wide enough for a human to read.
    """
    admin = AdminDashboardPage(page, admin_token, app_url)
    admin.goto()
    admin.open_new_library_quiz("")

    admin.import_library_quiz([
        {
            "question_text": "Capital of France?",
            "bomb_value": 5,
            "answers": [
                {"answer_text": "Paris", "bomb_value": 5, "is_correct": True},
                {"answer_text": "London", "bomb_value": 0, "is_correct": False},
            ],
        },
    ])

    assert admin.library_answer_texts() == ["Paris", "London"]

    widths = admin.library_answer_widths()
    assert len(widths) == 2
    assert all(w > 100 for w in widths), f"answer inputs are too narrow to read: {widths}"


def test_quiz_library_source_round_trips(page, app_url, admin_token):
    """A question's source link survives the library: author → save → re-open in
    the editor → load into a brand-new game."""
    admin = AdminDashboardPage(page, admin_token, app_url)
    admin.goto()
    admin.open_new_library_quiz("Sourced Quiz")
    admin.add_library_question("Capital of France?", [
        {"text": "Paris", "correct": True},
        {"text": "London", "correct": False},
    ], source_url="https://en.wikipedia.org/wiki/Paris")
    admin.set_library_total(10)
    admin.rebalance_library()
    admin.save_library_quiz()

    # Re-opening the saved quiz restores the source field in the editor.
    admin.select_library_quiz("Sourced Quiz")
    admin.edit_selected_library_quiz()
    assert admin.page.input_value(
        "#library-quiz-questions-list input[data-role='source-url'][data-qi='0']"
    ) == "https://en.wikipedia.org/wiki/Paris"

    # Loading the library quiz into a real game carries the source along.
    gm_token = _create_game(app_url, admin_token)
    gs = GameSettingsPage(page, gm_token, app_url)
    gs.goto()
    gs.enable_quiz(10)
    gs.load_library_quiz("Sourced Quiz")
    gs.save_quiz()
    questions = _game_questions(app_url, gm_token)
    assert questions[0]["source_url"] == "https://en.wikipedia.org/wiki/Paris"

