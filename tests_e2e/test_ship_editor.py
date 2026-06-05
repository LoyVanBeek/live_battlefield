"""E2E test for the visual ship placement editor on the team page."""

import pytest
import httpx
from tests_e2e.config import HTTPX_TIMEOUT


@pytest.fixture
def game_with_teams_joined(app_url, admin_token):
    """Create a game with 2 teams joined, NO ships placed."""
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post("/api/admin/create-game", params={"token": admin_token})
        gm_token = resp.json()["token"]

        teams = {}
        for color, name in [("red", "Red Team"), ("blue", "Blue Team")]:
            client.post("/api/execute", params={"gm_token": gm_token},
                        json={"team_color": color, "command": "join", "args": {"name": name}})

        state = client.get("/api/state", params={"gm_token": gm_token}).json()
        for t in state["teams"]:
            teams[t["color"]] = {"name": t["name"], "token": t["token"]}

    return {"gm_token": gm_token, "teams": teams, "team_urls": {c: f"/team/{teams[c]['token']}" for c in teams}}


def test_visual_ship_editor(page, app_url, game_with_teams_joined):
    """Full visual ship placement flow through the browser."""
    data = game_with_teams_joined
    team_url = data["team_urls"]["red"]

    from tests_e2e.pages.team_page import TeamPage
    tp = TeamPage(page, team_url, app_url)
    tp.goto()

    # Wait for the page to render and ship inventory to appear
    page.wait_for_function(
        'document.querySelectorAll(".ship-inv-item").length > 0',
        timeout=10000
    )

    # Step 1: Count initial inventory — should be 10 ships
    initial_count = tp.ship_inventory_count()
    assert initial_count == 10, f"Expected 10 ships in inventory, got {initial_count}"

    # Step 2: Select first ship (Patrol Boat) and place it at A1 (row 0, col 0)
    tp.select_ship_in_inventory(0)

    # Verify hint text changes to show placement instructions
    hint = tp.get_ship_hint_text()
    assert "horizontal" in hint or "vertical" in hint

    # Place at A1
    tp.place_ship_on_board(0, 0)
    page.wait_for_timeout(300)

    # Step 3: Inventory should now have 9 items (1 placed)
    count_after_1 = tp.ship_inventory_count()
    assert count_after_1 == 9, f"Expected 9 ships after placing 1, got {count_after_1}"

    # Step 4: Select another ship and place at C3 (row 2, col 2)
    tp.select_ship_in_inventory(0)
    tp.place_ship_on_board(2, 2)
    page.wait_for_timeout(300)

    count_after_2 = tp.ship_inventory_count()
    assert count_after_2 == 8, f"Expected 8 ships after placing 2, got {count_after_2}"

    # Step 5: Test rotate button — click it to switch direction
    initial_hint = tp.get_ship_hint_text()
    tp.click_rotate()
    page.wait_for_timeout(300)
    rotated_hint = tp.get_ship_hint_text()
    # Direction should have changed
    assert rotated_hint != initial_hint, "Rotate did not change hint text"

    # Step 6: Click Clear All Ships — verify confirmation and ships return
    tp.clear_all_ships()
    page.wait_for_timeout(500)

    # All ships should be back in inventory
    count_after_clear = tp.ship_inventory_count()
    assert count_after_clear == 10, f"Expected 10 ships after clear, got {count_after_clear}"

    # Step 7: Place a ship then remove it by clicking on the board
    tp.select_ship_in_inventory(0)
    tp.place_ship_on_board(0, 0)
    page.wait_for_timeout(300)

    # Deselect any active ship by clicking the ✕ cancel link in the hint
    page.locator("#ship-hint a", has_text="✕").click()
    page.wait_for_timeout(200)

    # Click the placed ship on the board to remove it
    page.once("dialog", lambda dialog: dialog.accept())
    tp.private_board_cell(0, 0).click()
    page.wait_for_timeout(500)

    # Verify ship returned to inventory
    count_back = tp.ship_inventory_count()
    assert count_back == 10, f"Expected all 10 ships back after remove, got {count_back}"

    # Step 8: Quick sanity — auto-place all ships
    tp.auto_place_ships()
    page.wait_for_timeout(500)

    # After auto-place, inventory should be empty
    count_after_auto = tp.ship_inventory_count()
    assert count_after_auto == 0, f"Expected 0 ships after auto-place, got {count_after_auto}"