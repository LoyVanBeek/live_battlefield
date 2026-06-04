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
    page.wait_for_timeout(500)

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
    page.wait_for_timeout(500)

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