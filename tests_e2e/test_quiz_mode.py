"""Browser-based E2E test for quiz mode — everything done through the UI like a human would."""

import pytest
import re


def test_quiz_full_flow_browser(page, app_url, admin_token):
    """Full quiz flow through the browser: join teams, place ships, create questions, answer them."""

    # Step 1: Create a game via admin API (no UI for this)
    import httpx
    from tests_e2e.config import HTTPX_TIMEOUT

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        gm_token = resp.json()["token"]

    # Step 2: Open GM page, join 2 teams via clickable cards
    from tests_e2e.pages.gm_page import GameMasterPage
    gm = GameMasterPage(page, gm_token, app_url)
    gm.goto()

    gm.join_team_inline("red", "Red Team")
    gm.join_team_inline("blue", "Blue Team")

    # Step 3: Auto-place all ships
    gm.auto_place_all_ships()

    # Step 4: Get team tokens for later
    red_token = gm.get_team_token_from_card("red")

    # Step 5: Go to settings, enable quiz, add 2 questions
    from tests_e2e.pages.game_settings_page import GameSettingsPage
    gs = GameSettingsPage(page, gm_token, app_url)
    gs.goto()
    gs.enable_quiz(50)

    gs.add_question("What is 2+2?", [
        {"text": "4", "bombs": 5, "correct": True},
        {"text": "5", "bombs": 0, "correct": False},
    ])
    gs.add_question("Capital of France?", [
        {"text": "Paris", "bombs": 5, "correct": True},
        {"text": "London", "bombs": 0, "correct": False},
    ])
    gs.save_quiz()

    # Step 6: Go back to GM page, start the game
    gm.goto()
    gm.start_game()

    # Verify game started
    status = gm.get_game_status()
    assert "STARTED" in status, f"Expected STARTED, got {status}"

    # Step 7: Open red team page
    from tests_e2e.pages.team_page import TeamPage
    tp = TeamPage(page, f"/team/{red_token}", app_url)
    tp.goto()

    # Wait for quiz section to appear
    page.wait_for_function(
        'document.getElementById("quiz-content") && '
        'document.getElementById("quiz-content").querySelector("button")',
        timeout=10000
    )

    # Step 8: Read current bomb count (initial is 3)
    bombs_before = tp.get_bomb_count()
    assert bombs_before == 3, f"Expected 3 initial bombs, got {bombs_before}"

    # Step 9: Answer Q1 correctly (first answer button = "4", worth 25 bombs)
    # 50 total / 2 questions = 25 per correct answer
    tp.answer_quiz(0)

    # The result screen appears instead of auto-advancing: verdict + Next.
    tp.quiz_next_button().wait_for(state="visible", timeout=5000)
    assert "Correct" in tp.quiz_verdict().text_content(), tp.quiz_verdict().text_content()
    tp.next_quiz_question()

    # Verify bomb count increased by 25
    bombs_after = tp.get_bomb_count()
    assert bombs_after == bombs_before + 25, f"Expected {bombs_before + 25} bombs, got {bombs_after}"

    # Step 10: Answer Q2 wrong (second answer button = "London")
    page.wait_for_function(
        'document.getElementById("quiz-content") && '
        'document.getElementById("quiz-content").querySelector("button")',
        timeout=5000
    )

    # Get bomb count before wrong answer
    bombs_before_wrong = tp.get_bomb_count()
    tp.answer_quiz(1)  # Wrong answer
    tp.quiz_next_button().wait_for(state="visible", timeout=5000)
    assert "Wrong" in tp.quiz_verdict().text_content(), tp.quiz_verdict().text_content()
    tp.next_quiz_question()

    # Verify bomb count unchanged
    bombs_after_wrong = tp.get_bomb_count()
    assert bombs_after_wrong == bombs_before_wrong, \
        f"Bombs should not change after wrong answer: {bombs_before_wrong} → {bombs_after_wrong}"

    # Step 11: Verify "All questions answered!" appears
    page.wait_for_function(
        'document.getElementById("quiz-content") && '
        'document.getElementById("quiz-content").textContent.includes("answered")',
        timeout=5000
    )
    quiz_text = tp.get_quiz_text()
    assert "answered" in quiz_text.lower(), f"Expected 'answered' in quiz, got: {quiz_text}"


def test_quiz_section_not_rebuilt_on_game_events(page, app_url, admin_token):
    """A game event must not rebuild the quiz DOM.

    Regression test for the flicker: every state push used to replace the whole
    #actions panel, so #quiz-content was destroyed, filled with the "loading"
    placeholder and repainted after a network round trip. We prove that DOM
    identity survives a push (the quiz button element is not re-created, and
    #quiz-content receives zero child mutations) and that the chosen bomb target
    is not reset.

    Setup goes through the UI like the other quiz test; the opponent's bomb is
    fired through the API because the point is the state push it generates, not
    the bombing UI itself.
    """

    # Step 1: Create a game via admin API (no UI for this)
    import httpx
    from tests_e2e.config import HTTPX_TIMEOUT
    from tests_e2e.pages.gm_page import GameMasterPage
    from tests_e2e.pages.game_settings_page import GameSettingsPage
    from tests_e2e.pages.team_page import TeamPage

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        gm_token = resp.json()["token"]

    # Step 2: Join 2 teams and auto-place their ships
    gm = GameMasterPage(page, gm_token, app_url)
    gm.goto()
    gm.join_team_inline("red", "Red Team")
    gm.join_team_inline("blue", "Blue Team")
    gm.auto_place_all_ships()

    red_token = gm.get_team_token_from_card("red")
    blue_token = gm.get_team_token_from_card("blue")

    # Step 3: Enable quiz with one question
    gs = GameSettingsPage(page, gm_token, app_url)
    gs.goto()
    gs.enable_quiz(50)
    gs.add_question("Capital of France?", [
        {"text": "Paris", "bombs": 5, "correct": True},
        {"text": "London", "bombs": 0, "correct": False},
    ])
    gs.save_quiz()

    # Step 4: Start the game
    gm.goto()
    gm.start_game()

    # Step 5: Open red team page and wait for the quiz to render
    tp = TeamPage(page, f"/team/{red_token}", app_url)
    tp.goto()
    page.wait_for_function(
        'document.getElementById("quiz-content") && '
        'document.getElementById("quiz-content").querySelector("button")',
        timeout=10000,
    )

    # Step 6: Tag the quiz button, watch for any quiz-DOM mutation, pick a target
    page.evaluate("""
        () => {
            const content = document.getElementById('quiz-content');
            content.querySelector('button').dataset.probe = 'alive';
            window.__quizMutations = 0;
            new MutationObserver(() => { window.__quizMutations++; })
                .observe(content, {childList: true, subtree: true});
            const select = document.getElementById('target-team');
            if (select) select.value = 'blue';
        }
    """)
    # Let any in-flight initial render settle, then count only from a clean slate
    page.wait_for_timeout(1000)
    page.evaluate("() => { window.__quizMutations = 0; }")

    # Step 7: Blue throws a bomb -> server broadcasts a state push to red's page
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        bomb = client.post(
            "/api/execute",
            params={"team_token": blue_token},
            json={"team_color": "blue", "command": "bomb", "args": {"target": "red", "coordinate": "A1"}},
        ).json()
    assert bomb.get("success"), f"Blue bomb failed: {bomb}"

    page.wait_for_timeout(2000)

    # Step 8: The push must have left the quiz DOM and the target choice untouched
    state = page.evaluate("""
        () => ({
            probe_alive: !!document.querySelector('#quiz-content button[data-probe="alive"]'),
            mutations: window.__quizMutations,
            target_value: (document.getElementById('target-team') || {}).value,
            quiz_text: document.getElementById('quiz-content').textContent,
        })
    """)
    assert state["probe_alive"], (
        "quiz button was re-created by a state push (flicker); "
        f"quiz text is now: {state['quiz_text']!r}"
    )
    assert state["mutations"] == 0, (
        f"quiz DOM mutated {state['mutations']}x on a state push (flicker)"
    )
    assert state["target_value"] == "blue", "bomb target selection was reset by a state push"


def test_quiz_manual_bombs_and_rebalance(page, app_url, admin_token):
    import httpx
    from tests_e2e.config import HTTPX_TIMEOUT
    from tests_e2e.pages.game_settings_page import GameSettingsPage

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        gm_token = resp.json()["token"]

    gs = GameSettingsPage(page, gm_token, app_url)
    gs.goto()
    gs.enable_quiz(10)
    for i in range(2):
        gs.add_question(f"Q{i+1}", [
            {"text": "A", "correct": True},
            {"text": "B", "correct": False},
        ])

    gs.rebalance_bombs()
    page.wait_for_function('document.getElementById("quiz-total").value === "10"', timeout=5000)

    gs.save_quiz()
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        data = client.get("/api/quiz/questions", params={"gm_token": gm_token}).json()
    questions = data.get("questions") or []
    assert len(questions) == 2
    assert questions[0].get("bomb_value") == 5
    assert questions[1].get("bomb_value") == 5


def test_quiz_import_uses_json_bomb_values(page, app_url, admin_token, tmp_path):
    """Import keeps the JSON's per-answer bomb values (wrong answers included),
    auto-fixes zero-yield questions to 1, derives the total from each question's
    max yield, and lays the manage buttons out above the questions list
    (Add Question stays below)."""
    import json
    import httpx
    from tests_e2e.config import HTTPX_TIMEOUT
    from tests_e2e.pages.game_settings_page import GameSettingsPage

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        gm_token = resp.json()["token"]

    quiz_json = [
        {
            "question_text": "Q1",
            "answers": [
                {"answer_text": "A", "bomb_value": 7, "is_correct": True},
                # Wrong answer keeps its JSON bomb value as-is (no flattening).
                {"answer_text": "B", "bomb_value": 2, "is_correct": False},
            ],
        },
        {
            "question_text": "Q2",
            "answers": [
                {"answer_text": "C", "bomb_value": 3, "is_correct": True},
                {"answer_text": "D", "bomb_value": 0, "is_correct": False},
            ],
        },
        {
            # No answer yields >= 1 -> auto-fixed to 1 on import.
            "question_text": "Q3",
            "answers": [{"answer_text": "E", "bomb_value": 0, "is_correct": True}],
        },
    ]
    import_file = tmp_path / "quiz.json"
    import_file.write_text(json.dumps(quiz_json), encoding="utf-8")

    gs = GameSettingsPage(page, gm_token, app_url)
    gs.goto()
    gs.enable_quiz()
    gs.import_quiz(str(import_file))
    # Total = sum of each question's max yield: 7 + 3 + 1
    page.wait_for_function('document.getElementById("quiz-total").value === "11"', timeout=5000)
    assert gs.question_blocks().count() == 3

    # Manage buttons above the questions, Add Question below.
    layout = page.evaluate("""() => {
        const list = document.getElementById('quiz-questions-list');
        const findBtn = (text) => Array.from(document.querySelectorAll('#quiz-questions-area button'))
            .find(b => b.textContent.includes(text));
        const above = (el) => el.getBoundingClientRect().bottom <= list.getBoundingClientRect().top;
        return {
            save_above: above(findBtn('Save Quiz Settings')),
            rebalance_above: above(findBtn('Rebalance')),
            export_above: above(findBtn('Export JSON')),
            import_above: above(findBtn('Import JSON')),
            add_below: findBtn('Add Question').getBoundingClientRect().top >= list.getBoundingClientRect().bottom,
        };
    }""")
    assert all(layout.values()), layout

    gs.save_quiz()
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        data = client.get("/api/quiz/questions", params={"gm_token": gm_token}).json()
    questions = data.get("questions") or []
    assert [q.get("bomb_value") for q in questions] == [7, 3, 1], questions
    assert questions[0]["answers"][0]["bomb_value"] == 7
    assert questions[0]["answers"][1]["bomb_value"] == 2, "wrong answer must keep its JSON bomb value"
    assert questions[2]["answers"][0]["bomb_value"] == 1, "zero-yield question auto-fixed to 1"


def test_quiz_edit_answer_bombs(page, app_url, admin_token):
    """Per-answer bomb values are editable in the editor; the total tracks each
    question's max yield, and editing bombs never changes which answer is correct."""
    import httpx
    from tests_e2e.config import HTTPX_TIMEOUT
    from tests_e2e.pages.game_settings_page import GameSettingsPage

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        gm_token = resp.json()["token"]

    gs = GameSettingsPage(page, gm_token, app_url)
    gs.goto()
    gs.enable_quiz(10)
    for i in range(2):
        gs.add_question(f"Q{i+1}", [
            {"text": "A", "correct": True},
            {"text": "B", "correct": False},
        ])
    gs.rebalance_bombs()
    # 10 / 2 questions -> 5 bombs on each correct answer
    page.wait_for_function('document.getElementById("quiz-total").value === "10"', timeout=5000)

    # Raise the correct answer (Q1/A) to 8 -> total = 8 + 5 = 13
    gs.set_answer_bombs(0, 0, 8)
    page.wait_for_function('document.getElementById("quiz-total").value === "13"', timeout=5000)

    # A wrong answer (Q1/B) below the max leaves the total unchanged
    gs.set_answer_bombs(0, 1, 3)
    page.wait_for_function('document.getElementById("quiz-total").value === "13"', timeout=5000)

    # Raising the wrong answer above the correct one -> total follows the max (9 + 5 = 14),
    # and the radio must NOT move to that answer (correctness is independent).
    gs.set_answer_bombs(0, 1, 9)
    page.wait_for_function('document.getElementById("quiz-total").value === "14"', timeout=5000)
    radio0_checked = page.evaluate(
        '() => document.querySelector(\'input[name="correct-0"]\').checked'
    )
    assert radio0_checked is True, "editing bombs must not re-mark the correct answer"

    gs.save_quiz()
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        data = client.get("/api/quiz/questions", params={"gm_token": gm_token}).json()
    questions = data.get("questions") or []
    assert questions[0].get("bomb_value") == 9, questions  # max yield
    a0, a1 = questions[0]["answers"]
    assert (a0["bomb_value"], a0["is_correct"]) == (8, True), a0
    assert (a1["bomb_value"], a1["is_correct"]) == (9, False), a1
    assert questions[1].get("bomb_value") == 5, questions


def test_quiz_source_revealed_after_answer(page, app_url, admin_token):
    """A question's source link stays hidden until that team answers, then the
    result screen shows the correct answer plus a clickable source link, and the
    team moves on via the Next button."""
    import httpx
    from tests_e2e.config import HTTPX_TIMEOUT
    from tests_e2e.pages.gm_page import GameMasterPage
    from tests_e2e.pages.game_settings_page import GameSettingsPage
    from tests_e2e.pages.team_page import TeamPage

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        gm_token = resp.json()["token"]

    gm = GameMasterPage(page, gm_token, app_url)
    gm.goto()
    gm.join_team_inline("red", "Red Team")
    gm.join_team_inline("blue", "Blue Team")
    gm.auto_place_all_ships()
    red_token = gm.get_team_token_from_card("red")

    gs = GameSettingsPage(page, gm_token, app_url)
    gs.goto()
    gs.enable_quiz(50)
    gs.add_question(
        "Capital of France?",
        [
            {"text": "Paris", "bombs": 5, "correct": True},
            {"text": "London", "bombs": 0, "correct": False},
        ],
        source_url="https://en.wikipedia.org/wiki/Paris",
    )
    gs.save_quiz()

    gm.goto()
    gm.start_game()

    tp = TeamPage(page, f"/team/{red_token}", app_url)
    tp.goto()
    page.wait_for_function(
        'document.getElementById("quiz-content") && '
        'document.getElementById("quiz-content").querySelector("button")',
        timeout=10000,
    )

    # The link must not be visible (or in the payload) before answering.
    assert tp.quiz_source_link().count() == 0, "source link leaked before answering"

    tp.answer_quiz(0)
    tp.quiz_next_button().wait_for(state="visible", timeout=5000)
    assert "Correct" in tp.quiz_verdict().text_content(), tp.quiz_verdict().text_content()
    assert "Paris" in tp.quiz_correct_answer().text_content(), tp.quiz_correct_answer().text_content()

    link = tp.quiz_source_link()
    assert link.count() == 1, "source link missing on the result screen"
    assert link.get_attribute("href") == "https://en.wikipedia.org/wiki/Paris"
    assert link.get_attribute("target") == "_blank"

    tp.next_quiz_question()
    page.wait_for_function(
        'document.getElementById("quiz-content") && '
        'document.getElementById("quiz-content").textContent.includes("answered")',
        timeout=5000,
    )