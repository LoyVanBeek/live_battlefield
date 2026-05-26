import pytest
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

    tp.auto_place_ships()
    ships_text = tp.ships_placed_text().text_content()
    placed, total = ships_text.split("/")
    assert int(placed) >= 1
    assert int(total) == 10


def test_remove_ship_from_team_page(page, app_url, seeded_game_with_teams):
    seed = seeded_game_with_teams
    team_url = seed["team_urls"]["red"]
    tp = TeamPage(page, team_url, app_url)
    tp.goto()

    tp.auto_place_ships()
    page.wait_for_timeout(1000)

    ships_text_before = tp.ships_placed_text().text_content()
    placed_before = int(ships_text_before.split("/")[0])

    # Click the remove ship button and provide a coordinate
    remove_btn = page.locator("button.btn-danger", has_text="Remove Ship")
    if remove_btn.count() > 0:
        remove_btn.click()
        page.wait_for_timeout(500)
        # Type a coordinate to remove
        page.locator("#remove-coord").fill("A1")
        remove_btn.click()
        page.wait_for_timeout(1000)

        ships_text_after = tp.ships_placed_text().text_content()
        placed_after = int(ships_text_after.split("/")[0])
        assert placed_after < placed_before
