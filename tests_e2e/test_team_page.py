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
