import httpx
import pytest
from tests_e2e.pages.gm_page import GameMasterPage
from tests_e2e.pages.team_page import TeamPage


def test_play_full_game(page, app_url, admin_token):
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.post(
            "/api/admin/create-game",
            params={"token": admin_token},
        )
        data = resp.json()
        gm_token = data["token"]

        locations_coords = [
            (51.590, 5.330),
            (51.585, 5.335),
            (51.580, 5.340),
            (51.575, 5.345),
            (51.570, 5.350),
        ]
        for lat, lon in locations_coords:
            client.post(
                "/api/quick/create_locations",
                params={"gm_token": gm_token},
                json={"latitude": lat, "longitude": lon, "count": 1, "radius_km": 0},
            )

        resp = client.get(
            "/api/state",
            params={"gm_token": gm_token},
        )
        state = resp.json()
        available = state.get("available_colors", [])

    gm = GameMasterPage(page, gm_token, app_url)
    gm.goto()
    gm.join_team("red", "Red Team")
    gm.join_team("blue", "Blue Team")

    with httpx.Client(base_url=app_url, timeout=30) as client:
        for color in ["red", "blue"]:
            client.post(
                "/api/quick/place_all_ships",
                params={"gm_token": gm_token},
                json={"team_color": color},
            )

        resp = client.get(
            "/api/game-status",
            params={"gm_token": gm_token},
        )
        status = resp.json()
        assert status["total_teams"] >= 2
        assert status["teams_with_all_ships"] >= 2
        assert status["locations_placed"] >= 5

    # Reload GM page to reflect updated state after API calls
    gm.goto()
    page.wait_for_timeout(2000)

    assert not gm.start_button().is_disabled()
    gm.start_game()

    status_text = gm.get_game_status()
    assert "STARTED" in status_text

    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.get(
            "/api/state",
            params={"gm_token": gm_token},
        )
        state = resp.json()

    red_token = None
    for team in state["teams"]:
        if team["color"] == "red":
            red_token = team.get("token")
            break

    if red_token:
        tp = TeamPage(page, f"/team/{red_token}", app_url)
        tp.goto()
        page.wait_for_timeout(1000)

        bomb_buttons = tp.location_bomb_buttons().all()
        if len(bomb_buttons) > 0:
            bomb_buttons[0].click()
            page.wait_for_timeout(1500)

        attackable = tp.attack_cells().all()
        if len(attackable) > 0:
            attackable[0].click()
            page.wait_for_timeout(1000)

    gm.goto()
    gm.end_game()

    status_text = gm.get_game_status()
    assert "ENDED" in status_text
    assert gm.start_button().is_disabled()
    assert gm.end_button().is_disabled()
    assert not gm.new_game_button().is_disabled()
