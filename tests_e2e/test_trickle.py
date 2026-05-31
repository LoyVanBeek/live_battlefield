import time
import httpx
import pytest


def test_trickle_bombs_delivered(page, app_url, admin_token):
    with httpx.Client(base_url=app_url, timeout=30) as client:
        # Create game
        resp = client.post(
            "/api/admin/create-game",
            params={"token": admin_token},
        )
        gm_token = resp.json()["token"]

        # Create a location (needed to start game)
        client.post(
            "/api/quick/create_locations",
            params={"gm_token": gm_token},
            json={"latitude": 51.590, "longitude": 5.330, "count": 1, "radius_km": 0},
        )

        # Join 2 teams
        for color in ["red", "blue"]:
            client.post(
                "/api/execute",
                params={"gm_token": gm_token},
                json={
                    "team_color": color,
                    "command": "join",
                    "args": {"name": f"{color.title()} Team"},
                },
            )

        # Fetch team tokens
        resp = client.get("/api/state", params={"gm_token": gm_token})
        state = resp.json()
        tokens = {
            t["color"]: t["token"]
            for t in state["teams"]
        }

        # Place all ships
        for color in ["red", "blue"]:
            for _ in range(10):
                client.post(
                    "/api/quick/place_all_ships",
                    params={"team_token": tokens[color]},
                    json={"team_color": color},
                )

        # Start game
        client.post(
            "/api/quick/start-game",
            params={"gm_token": gm_token},
        )

        # Check game is started
        resp = client.get("/api/game-status", params={"gm_token": gm_token})
        assert resp.json()["status"] == "started"

        # Record baseline bomb counts
        resp = client.get("/api/state", params={"gm_token": gm_token})
        state = resp.json()
        baseline = {t["color"]: t["bombs"] for t in state["teams"]}

        # Enable trickle: 1 bomb every 1 minute
        resp = client.post(
            "/api/quick/trickle_settings",
            params={"gm_token": gm_token},
            json={"enabled": True, "bombs_per_interval": 1, "interval_minutes": 1},
        )
        assert resp.json()["success"]

        # Poll for delivery — the trickle fires on the first check
        # when last_trickle_at is None, so should arrive within 35s (30s check + margin)
        deadline = time.time() + 90
        delivered = False

        while time.time() < deadline:
            time.sleep(5)
            resp = client.get("/api/state", params={"gm_token": gm_token})
            state = resp.json()

            all_increased = True
            for color in ["red", "blue"]:
                team = next(t for t in state["teams"] if t["color"] == color)
                if team["bombs"] <= baseline[color]:
                    all_increased = False
                    break

            if all_increased:
                delivered = True
                final_bombs = {
                    t["color"]: t["bombs"] for t in state["teams"]
                }
                break

        assert delivered, (
            f"Trickle bombs not delivered within 90s. "
            f"Baseline: {baseline}, Final: {final_bombs if 'final_bombs' in dir() else 'N/A'}"
        )

        # Verify each team got at least 1 bomb
        for color in ["red", "blue"]:
            assert final_bombs[color] > baseline[color], (
                f"Team {color} bomb count did not increase: {baseline[color]} -> {final_bombs[color]}"
            )

        # Verify the API reflects trickle settings
        assert state["trickle_enabled"] is True
        assert state["trickle_bombs_per_interval"] == 1
        assert state["trickle_interval_minutes"] == 1

    # Navigate to GM page and verify bomb count renders
    from tests_e2e.pages.gm_page import GameMasterPage

    gm = GameMasterPage(page, gm_token, app_url)
    gm.goto()
    page.wait_for_timeout(3000)

    for color in ["red", "blue"]:
        card = gm.team_card(color)
        bombs_text = card.locator(".bombs-count").text_content()
        assert bombs_text == str(final_bombs[color]), (
            f"GM page shows {bombs_text} bombs for {color}, expected {final_bombs[color]}"
        )
