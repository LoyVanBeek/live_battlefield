import pytest
from tests_e2e.pages.locations_page import LocationsPage
from tests_e2e.pages.gm_page import GameMasterPage


def test_locations_page_loads(page, app_url, seeded_game_with_locations):
    seed = seeded_game_with_locations
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    count = lp.get_location_count()
    assert count > 0

    map_el = lp.map_element()
    assert map_el.is_visible()

    back_link = lp.back_link()
    href = back_link.get_attribute("href")
    assert "game-master" in href or href != "#"


def test_add_location_via_form(page, app_url, seeded_game):
    seed = seeded_game
    lp = LocationsPage(page, seed["gm_token"], app_url=app_url)
    lp.goto()

    lp.add_location(51.59, 5.33, count=1, radius=0)
    lp.page.wait_for_timeout(1000)

    count = lp.get_location_count()
    assert count >= 1
