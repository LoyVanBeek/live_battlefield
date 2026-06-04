"""E2E test for quiz mode — full flow: create questions, answer correct/wrong, verify bomb counts"""

import pytest
import httpx
from tests_e2e.config import HTTPX_TIMEOUT


@pytest.fixture
def seeded_game_with_quiz(app_url, admin_token):
    """Create a game with 2 teams, ships placed, quiz enabled with 2 questions."""
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        # 1. Create game
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        gm_token = resp.json()["token"]

        # 2. Join 2 teams
        teams = {}
        for color, name in [("red", "Red"), ("blue", "Blue")]:
            client.post("/api/execute", params={"gm_token": gm_token},
                        json={"team_color": color, "command": "join", "args": {"name": name}})

        # 3. Get team tokens
        state = client.get("/api/state", params={"gm_token": gm_token}).json()
        for t in state["teams"]:
            teams[t["color"]] = {"name": t["name"], "token": t["token"]}

        # 4. Auto-place ships (retry up to 20x)
        for _ in range(20):
            for color in teams:
                client.post("/api/quick/place_all_ships",
                            params={"team_token": teams[color]["token"]},
                            json={"team_color": color})
            gs = client.get("/api/game-status", params={"gm_token": gm_token}).json()
            if gs.get("teams_with_all_ships") == 2:
                break

        # 5. Enable quiz + create 2 questions
        client.post("/api/quick/quiz_settings", params={"gm_token": gm_token},
                    json={"enabled": True, "total_bombs": 50})
        client.post("/api/quiz/questions", params={"gm_token": gm_token},
                    json={"questions": [
                        {"question_text": "What is 2+2?",
                         "answers": [
                             {"answer_text": "4", "bomb_value": 5, "is_correct": True},
                             {"answer_text": "5", "bomb_value": 0, "is_correct": False},
                         ]},
                        {"question_text": "Capital of France?",
                         "answers": [
                             {"answer_text": "Paris", "bomb_value": 5, "is_correct": True},
                             {"answer_text": "London", "bomb_value": 0, "is_correct": False},
                         ]},
                    ]})

        yield {"gm_token": gm_token, "teams": teams}


def test_quiz_full_flow(page, app_url, seeded_game_with_quiz):
    """Full quiz flow: start game, answer correct, answer wrong, verify bombs, verify no retry."""
    data = seeded_game_with_quiz
    gm_token = data["gm_token"]
    teams = data["teams"]

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        # 1. Start game
        resp = client.post("/api/quick/start-game", params={"gm_token": gm_token})
        assert resp.json()["success"] is True, f"Failed to start game: {resp.json()}"

        # 2. Fetch questions via GM token
        qs = client.get("/api/quiz/questions", params={"gm_token": gm_token}).json()
        questions = qs["questions"]
        assert len(questions) == 2
        q1 = questions[0]
        q2 = questions[1]

        # 3. Get baseline bomb count for red
        state = client.get("/api/state", params={"gm_token": gm_token}).json()
        red_before = next(t["bombs"] for t in state["teams"] if t["color"] == "red")

        # 4. Submit CORRECT answer for q1 → expect +5 bombs
        correct_answer_id = next(a["id"] for a in q1["answers"] if a["is_correct"])
        resp = client.post("/api/execute",
                           params={"team_token": teams["red"]["token"]},
                           json={"team_color": "red", "command": "quiz",
                                 "args": {"question_id": q1["id"], "answer_id": correct_answer_id}})
        data = resp.json()
        assert data["success"] is True, f"Correct answer failed: {data}"
        assert "Correct!" in data["message"], f"Unexpected message: {data['message']}"

        state = client.get("/api/state", params={"gm_token": gm_token}).json()
        red_after_correct = next(t["bombs"] for t in state["teams"] if t["color"] == "red")
        assert red_after_correct == red_before + 5, \
            f"Expected {red_before + 5} bombs, got {red_after_correct}"

        # 5. Submit WRONG answer for q2 → expect no bombs
        wrong_answer_id = next(a["id"] for a in q2["answers"] if not a["is_correct"])
        resp = client.post("/api/execute",
                           params={"team_token": teams["red"]["token"]},
                           json={"team_color": "red", "command": "quiz",
                                 "args": {"question_id": q2["id"], "answer_id": wrong_answer_id}})
        data = resp.json()
        assert data["success"] is False, f"Wrong answer should fail: {data}"
        assert "Wrong" in data["message"], f"Unexpected message: {data['message']}"

        state = client.get("/api/state", params={"gm_token": gm_token}).json()
        red_after_wrong = next(t["bombs"] for t in state["teams"] if t["color"] == "red")
        assert red_after_wrong == red_after_correct, \
            f"Bombs changed after wrong answer: {red_after_correct} → {red_after_wrong}"

        # 6. Try answering q1 again → should be blocked
        resp = client.post("/api/execute",
                           params={"team_token": teams["red"]["token"]},
                           json={"team_color": "red", "command": "quiz",
                                 "args": {"question_id": q1["id"], "answer_id": correct_answer_id}})
        data = resp.json()
        assert data["success"] is False, f"Retry should fail: {data}"
        assert "already answered" in data["message"].lower(), \
            f"Unexpected retry message: {data['message']}"

        # 7. Verify quiz section on team page shows completion
        from tests_e2e.pages.team_page import TeamPage
        tp = TeamPage(page, teams["red"]["token"], app_url)
        tp.goto()
        page.wait_for_function(
            'document.getElementById("quiz-content") && '
            'document.getElementById("quiz-content").textContent.includes("answered")',
            timeout=10000
        )