import httpx
import pytest
from tests_e2e.config import HTTPX_TIMEOUT
from tests_e2e.pages.gm_page import GameMasterPage
from tests_e2e.pages.team_page import TeamPage


def test_team_page_loads(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    team_url = seed["team_urls"]["red"]
    tp = TeamPage(page, team_url, app_url)
    tp.goto()

    dots = tp.team_color_display().all()
    assert len(dots) > 0


def test_auto_place_ships_from_team_page(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    team_url = seed["team_urls"]["blue"]
    tp = TeamPage(page, team_url, app_url)
    tp.goto()

    page.wait_for_function(
        "document.getElementById('ship-count').textContent !== '-'",
        timeout=10000,
    )
    ships_text = tp.ships_placed_text().text_content()
    assert ships_text.isdigit()
    assert int(ships_text) == 10


def test_remove_ship_from_team_page(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    team_url = seed["team_urls"]["red"]
    gm_token = seed["gm_token"]
    tp = TeamPage(page, team_url, app_url)
    tp.goto()

    page.wait_for_function(
        "document.getElementById('ship-count').textContent !== '-'",
        timeout=10000,
    )
    ships_text_before = tp.ships_placed_text().text_content()
    placed_before = int(ships_text_before)

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.get(
            "/api/board/red/private.json",
            params={"gm_token": gm_token},
        )
        data = resp.json()
        grid = data["grid"]
        ship_coord = None
        ship_row = None
        ship_col = None
        for row_idx, row in enumerate(grid):
            for col_idx, cell in enumerate(row):
                if cell and cell.get("has_ship"):
                    ship_row, ship_col = row_idx, col_idx
                    col_letter = chr(col_idx + 65)
                    row_number = row_idx + 1
                    ship_coord = f"{col_letter}{row_number}"
                    break
            if ship_coord:
                break

    assert ship_coord is not None, "No ship found on board"

    # Try removing the ship directly via API
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/quick/remove_ship",
            params={"team_token": seed["teams"]["red"]["token"]},
            json={"team_color": "red", "row": ship_row, "col": ship_col},
        )
        api_result = resp.json()
        assert api_result.get("success"), f"API remove failed: {api_result}"
        print(f"API remove result: {api_result}")

    # Wait for SSE to update the UI with the new ship count
    page.wait_for_function(
        f"document.getElementById('ship-count').textContent !== '{placed_before}'",
        timeout=10000,
    )

    ships_text_after = tp.ships_placed_text().text_content()
    placed_after = int(ships_text_after)
    assert placed_after < placed_before


def _game_id(app_url: str, admin_token: str, gm_token: str) -> str:
    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        games = client.get(
            "/api/admin/games", params={"token": admin_token}
        ).json()["games"]
        return next(g["id"] for g in games if g["gm_token"] == gm_token)


def test_map_link_in_header(page, app_url, admin_token, seeded_game_with_teams):
    """Header row has a 🗺️ button to the Quest Locations Map (opens in a new tab)."""
    seed = seeded_game_with_teams
    game_id = _game_id(app_url, admin_token, seed["gm_token"])

    tp = TeamPage(page, seed["team_urls"]["red"], app_url)
    tp.goto()

    link = tp.map_link()
    link.wait_for(state="visible")

    assert link.get_attribute("href") == f"/map?game_id={game_id}"
    assert link.get_attribute("target") == "_blank"
    assert "noopener" in (link.get_attribute("rel") or "")
    # translated tooltip (default en: "🗺️ Quest Locations Map")
    assert "Map" in (link.get_attribute("title") or "")


def test_map_link_in_redeem_form(page, app_url, admin_token, seeded_game_with_teams):
    """Once started, the Redeem Code form carries the same map link."""
    seed = seeded_game_with_teams
    game_id = _game_id(app_url, admin_token, seed["gm_token"])

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        resp = client.post(
            "/api/quick/start-game", params={"gm_token": seed["gm_token"]}
        )
        assert resp.json().get("success") is True, resp.text

    tp = TeamPage(page, seed["team_urls"]["red"], app_url)
    tp.goto()
    # redeem form is only rendered when the game has started
    page.wait_for_selector("#code-loc", timeout=15000)

    link = tp.redeem_map_link()
    link.wait_for(state="visible")

    assert link.get_attribute("href") == f"/map?game_id={game_id}"
    assert link.get_attribute("target") == "_blank"


def _add_team_with_ships(client, gm_token: str, color: str, name: str) -> str:
    """Join a team via the API and place all of its ships; return its token."""
    client.post(
        "/api/execute",
        params={"gm_token": gm_token},
        json={"team_color": color, "command": "join", "args": {"name": name}},
    )
    state = client.get("/api/state", params={"gm_token": gm_token}).json()
    token = next(t for t in state["teams"] if t["color"] == color)["token"]
    for _ in range(20):
        client.post(
            "/api/quick/place_all_ships",
            params={"team_token": token},
            json={"team_color": color},
        )
        status = client.get("/api/game-status", params={"gm_token": gm_token}).json()
        if status.get("teams_with_all_ships", 0) >= len(state["teams"]):
            break
    return token


def _sink_team(client, gm_token: str, attacker_token: str, attacker_color: str, target_color: str) -> None:
    """Bomb every ship cell of the target team until it is eliminated."""
    grid = client.get(
        f"/api/board/{target_color}/private.json",
        params={"gm_token": gm_token},
    ).json()["grid"]
    ship_cells = [
        (ri, ci) for ri in range(10) for ci in range(10) if grid[ri][ci].get("has_ship")
    ]
    state = client.get("/api/state", params={"gm_token": gm_token}).json()
    attacker = next(t for t in state["teams"] if t["color"] == attacker_color)
    if attacker["bombs"] < len(ship_cells):
        client.post(
            "/api/quick/add_bombs",
            params={"gm_token": gm_token},
            json={"team_color": attacker_color, "count": len(ship_cells) + 5},
        )
    for ri, ci in ship_cells:
        client.post(
            "/api/execute",
            params={"team_token": attacker_token},
            json={
                "team_color": attacker_color,
                "command": "bomb",
                "args": {"target": target_color, "coordinate": f"{chr(ci + 65)}{ri + 1}"},
            },
        )


def test_eliminated_indicator_on_team_pages(page, app_url, seeded_game_with_teams):
    """A sunk team shows 💀 on its own page and on the opponents' view."""
    seed = seeded_game_with_teams
    gm_token = seed["gm_token"]

    with httpx.Client(base_url=app_url, timeout=HTTPX_TIMEOUT) as client:
        # Third team so the game keeps running after blue is eliminated.
        _add_team_with_ships(client, gm_token, "green", "Green Team")

        resp = client.post("/api/quick/start-game", params={"gm_token": gm_token})
        assert resp.json().get("success") is True, resp.text

        _sink_team(
            client,
            gm_token,
            seed["teams"]["red"]["token"],
            "red",
            "blue",
        )

    # The eliminated team's own page shows the header badge and dims its board.
    blue = TeamPage(page, seed["team_urls"]["blue"], app_url)
    blue.goto()
    self_badge = blue.self_eliminated_badge()
    self_badge.wait_for(state="visible", timeout=15000)
    assert "Eliminated" in self_badge.text_content()
    assert "eliminated" in (blue.private_board().get_attribute("class") or "")

    # An opponent sees blue badged on its public board and flagged in the target list.
    red = TeamPage(page, seed["team_urls"]["red"], app_url)
    red.goto()
    public_badge = red.public_board_eliminated_badge("blue")
    public_badge.wait_for(state="visible", timeout=15000)
    assert "Eliminated" in public_badge.text_content()
    assert "eliminated" in (red.public_board_item("blue").get_attribute("class") or "")

    option = red.target_team_option("blue")
    option.wait_for(state="attached", timeout=15000)
    assert "💀" in (option.text_content() or "")
