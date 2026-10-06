import httpx
from tests_e2e.config import HTTPX_TIMEOUT


def _start_game(app_url: str, admin_token: str, gm_token: str) -> str:
    """Start the game via API and return its game_id."""
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        games = client.get(
            "/api/admin/games", params={"token": admin_token}
        ).json()["games"]
        game_id = next(g["id"] for g in games if g["gm_token"] == gm_token)

        resp = client.post(
            "/api/quick/start-game", params={"gm_token": gm_token}
        )
        data = resp.json()
        assert data.get("success") is True, data

        return game_id


def test_map_page_renders_numbered_pins(
    page, app_url, admin_token, seeded_game_with_teams
):
    """Player map shows each location's number inside its pin (and keeps the title)."""
    seed = seeded_game_with_teams
    game_id = _start_game(app_url, admin_token, seed["gm_token"])

    page.goto(f"{app_url}/map?game_id={game_id}")

    pins = page.locator(".location-pin")
    pins.first.wait_for(state="visible")

    # seeded_game_with_teams creates locations 1 and 2
    numbers = {pins.nth(i).inner_text().strip() for i in range(pins.count())}
    assert {"1", "2"} <= numbers

    titles = [
        page.locator(".leaflet-marker-icon").nth(i).get_attribute("title")
        for i in range(page.locator(".leaflet-marker-icon").count())
    ]
    assert any(t and "Location #" in t for t in titles)


def test_map_page_shows_no_pins_before_start(
    page, app_url, admin_token, seeded_game_with_teams
):
    """Regression: pins stay hidden while the game is waiting."""
    seed = seeded_game_with_teams
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        games = client.get(
            "/api/admin/games", params={"token": admin_token}
        ).json()["games"]
        game_id = next(g["id"] for g in games if g["gm_token"] == seed["gm_token"])

    page.goto(f"{app_url}/map?game_id={game_id}")

    # wait until public state has loaded — pins must still be absent pre-start
    badge = page.locator("#game-status-badge")
    badge.wait_for(state="visible")
    page.wait_for_function(
        "() => document.getElementById('game-status-badge').textContent.includes('WAITING')"
    )

    assert page.locator(".location-pin").count() == 0
