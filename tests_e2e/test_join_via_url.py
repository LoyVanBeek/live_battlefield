import httpx
import pytest
from tests_e2e.pages.join_page import JoinPage
from tests_e2e.pages.gm_page import GameMasterPage


def test_join_page_loads(page, app_url, seeded_game):
    """The join page shows game info and available colors."""
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.get(
            "/api/state",
            params={"gm_token": seeded_game["gm_token"]},
        )
        data = resp.json()
        invite_token = data.get("invite_token")

    assert invite_token is not None, "invite_token should be returned by /api/state"

    join_page = JoinPage(page, invite_token, app_url)
    join_page.goto()

    title = page.title()
    assert "Join Game" in title

    # Available colors should be rendered
    options = join_page.color_select().locator("option").all()
    option_values = [opt.get_attribute("value") for opt in options]
    assert "" in option_values
    assert "red" in option_values
    assert "blue" in option_values


def test_join_via_url_creates_team(page, app_url, seeded_game):
    """Joining via the invite URL creates a team and redirects."""
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.get(
            "/api/state",
            params={"gm_token": seeded_game["gm_token"]},
        )
        data = resp.json()
        invite_token = data.get("invite_token")

    join_page = JoinPage(page, invite_token, app_url)
    join_page.goto()

    join_page.join_game("red", "URL Joiner")

    # After joining, we should be redirected to the team page
    page.wait_for_url("**/team/**", timeout=5000)
    assert "/team/" in page.url

    # Verify the team exists via API
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.get(
            "/api/state",
            params={"gm_token": seeded_game["gm_token"]},
        )
        data = resp.json()
        colors = [t["color"] for t in data.get("teams", [])]
        assert "red" in colors


def test_join_via_url_duplicate_color(page, app_url, seeded_game):
    """After joining a color, it's no longer available in the dropdown."""
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.get(
            "/api/state",
            params={"gm_token": seeded_game["gm_token"]},
        )
        data = resp.json()
        invite_token = data.get("invite_token")

    # First join via API
    with httpx.Client(base_url=app_url, timeout=30) as client:
        client.post(
            "/api/join-game/" + invite_token,
            json={"team_color": "red", "name": "First Joiner"},
        )

    # Open the join page — red should no longer be in the dropdown
    join_page = JoinPage(page, invite_token, app_url)
    join_page.goto()

    options = join_page.color_select().locator("option").all()
    option_values = [opt.get_attribute("value") for opt in options]
    assert "red" not in option_values


def test_join_via_url_duplicate_color_api(page, app_url, seeded_game):
    """API rejects a join with an already-taken color."""
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.get(
            "/api/state",
            params={"gm_token": seeded_game["gm_token"]},
        )
        data = resp.json()
        invite_token = data.get("invite_token")

    # First join via API
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.post(
            "/api/join-game/" + invite_token,
            json={"team_color": "red", "name": "First Joiner"},
        )
        assert resp.json()["success"] is True

        # Second join with same color
        resp = client.post(
            "/api/join-game/" + invite_token,
            json={"team_color": "red", "name": "Second Joiner"},
        )
        data = resp.json()
        assert data["success"] is False
        assert "already exists" in data["message"] or "already" in data["message"]


def test_invite_url_shown_on_gm_page(page, app_url, seeded_game):
    """The invite URL is displayed on the GM page."""
    gm = GameMasterPage(page, seeded_game["gm_token"], app_url)
    gm.goto()

    invite_url_input = page.locator("#invite-url")
    invite_url_input.wait_for(state="visible")

    # Wait for the invite URL to be populated by JS (polls /api/state every 2s)
    page.wait_for_function(
        "document.getElementById('invite-url').value !== ''",
        timeout=10000,
    )
    value = invite_url_input.input_value()
    assert value is not None
    assert "/join/" in value

    # The invite URL should point to this server
    assert app_url in value or value.startswith("http")


def test_full_color_block(app_url, admin_token, page):
    """When all colors are taken, the join page shows 'no colors available'."""
    with httpx.Client(base_url=app_url, timeout=30) as client:
        resp = client.post(
            "/api/admin/create-game",
            params={"token": admin_token},
        )
        data = resp.json()
        gm_token = data["token"]
        invite_token = data.get("invite_token")

        assert invite_token is not None

        # Fill up all 6 colors
        colors = ["red", "blue", "green", "purple", "orange", "yellow"]
        for color in colors:
            client.post(
                "/api/join-game/" + invite_token,
                json={"team_color": color, "name": f"{color} Team"},
            )

    join_page = JoinPage(page, invite_token, app_url)
    join_page.goto()

    # The join button should be disabled
    assert join_page.join_button().is_disabled()

    # Verify the "no colors available" message
    options = join_page.color_select().locator("option").all()
    option_texts = [opt.text_content() for opt in options]
    assert any("no colors" in (t or "").lower() or "full" in (t or "").lower() or t == "" for t in option_texts)
