"""Full flow E2E test: create game → GM sees invite URL → join via URL → place ship."""
import httpx
import pytest


def test_full_flow(page, app_url, admin_token):
    """Complete flow: create game, get invite URL, join team, place a ship."""
    # ── 1. Create game via admin API ──
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.post(
            "/api/admin/create-game",
            params={"token": admin_token},
        )
        data = resp.json()
        gm_token = data["token"]
        invite_token = data.get("invite_token")
    assert invite_token is not None

    # ── 2. Go to GM page and verify invite URL is shown ──
    page.goto(f"{app_url}/game-master/{gm_token}")
    page.wait_for_load_state("load")

    invite_btn = page.locator("#btn-copy-invite")
    invite_btn.wait_for(state="visible")

    # Wait for the JS to populate it from /api/state
    page.wait_for_function(
        "document.getElementById('btn-copy-invite').dataset.inviteUrl !== undefined && document.getElementById('btn-copy-invite').dataset.inviteUrl !== ''",
        timeout=10000,
    )
    invite_url = invite_btn.get_attribute("data-invite-url")
    assert invite_url is not None
    assert invite_url != ""
    assert "/join/" in invite_url

    # ── 3. Open the invite URL and join as red team ──
    page.goto(invite_url)
    page.wait_for_load_state("load")

    # Select red color
    color_select = page.locator("#team-color")
    color_select.wait_for(state="visible")
    color_select.select_option("red")

    # Enter team name
    name_input = page.locator("#team-name")
    name_input.fill("Full Flow Team")

    # Click Join
    join_btn = page.locator("#btn-join")
    join_btn.click()

    # Wait for redirect to team page
    page.wait_for_url("**/team/**", timeout=10000)
    assert "/team/" in page.url

    # ── 4. Place a ship via the visual ship editor ──
    from tests_e2e.pages.team_page import TeamPage

    tp = TeamPage(page, page.url)
    page.wait_for_function(
        'document.querySelectorAll(".ship-inv-item").length > 0', timeout=10000
    )
    tp.select_ship_in_inventory(0)
    tp.place_ship_on_board(0, 0)
    page.wait_for_timeout(1500)

    # ── 5. Verify ship was placed via API ──
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.get(
            "/api/state",
            params={"gm_token": gm_token},
        )
        state = resp.json()
        teams = state.get("teams", [])
        red_team = next((t for t in teams if t["color"] == "red"), None)
        assert red_team is not None, "Red team should exist"
        assert red_team["ships_placed"] >= 1, "At least one ship should be placed"
